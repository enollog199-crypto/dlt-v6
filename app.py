from flask import Flask, render_template
import requests, re, time, datetime, os
import numpy as np
from sklearn.ensemble import RandomForestClassifier

app = Flask(__name__, template_folder="web")
app.secret_key = os.environ.get("SECRET_KEY", "dextro_quantum_ai_v12")

# =========================
# 1️⃣ 数据引擎（多源自动切换）
# =========================
class DataEngine:
    def __init__(self):
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def fetch(self):
        # 优先尝试新浪 API (速度快)
        data = self._sina()
        if not data:
            data = self._500()
        return data

    def _sina(self):
        try:
            url = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?gameNo=85&pageSize=50"
            res = requests.get(url, timeout=5, headers=self.headers)
            js = res.json()
            return [{
                "p": i['lotteryDrawNum'],
                "date": i['lotteryDrawTime'],
                "r": sorted([int(x) for x in i['lotteryDrawResult'].split()[:5]]),
                "b": sorted([int(x) for x in i['lotteryDrawResult'].split()[5:]])
            } for i in js['value']['list']]
        except: return []

    def _500(self):
        try:
            res = requests.get("https://datachart.500.com/dlt/history/newinc/history.php", timeout=5)
            res.encoding = 'utf-8'
            rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
            data = []
            for r in rows[:50]:
                tds = re.findall(r'<td.*?>(.*?)</td>', r)
                if len(tds) >= 9:
                    data.append({
                        "p": tds[0].strip(),
                        "date": tds[14].strip() if len(tds)>14 else "-",
                        "r": sorted([int(x) for x in tds[2:7]]),
                        "b": sorted([int(x) for x in tds[7:9]])
                    })
            return data
        except: return []

# =========================
# 2️⃣ AI 核心：随机森林动态训练
# =========================
def train_and_predict(history):
    if len(history) < 20: return [], [], {}
    
    # 准备特征 (X: 当前期, Y: 下一期是否出现)
    X, Y_red = [], {i: [] for i in range(1, 36)}
    # 我们按时间正序训练 (history[::-1])
    h_reversed = history[::-1]
    
    for i in range(len(h_reversed)-1):
        current = h_reversed[i]
        nxt = h_reversed[i+1]
        X.append([1 if n in current['r'] else 0 for n in range(1, 36)])
        for n in range(1, 36):
            Y_red[n].append(1 if n in nxt['r'] else 0)

    # 训练并预测
    last_feat = [1 if n in history[0]['r'] else 0 for n in range(1, 36)]
    probs = {}
    
    for n in range(1, 36):
        # 使用轻量级森林减少 CPU 占用
        clf = RandomForestClassifier(n_estimators=30, max_depth=5)
        clf.fit(X, Y_red[n])
        probs[n] = round(clf.predict_proba([last_feat])[0][1] * 100, 2)

    # 策略选取
    # 1. AI 概率最高的前 5
    reds = sorted(probs, key=probs.get, reverse=True)[:5]
    # 2. 蓝球保留随机+频率逻辑
    blues = sorted(np.random.choice(range(1, 13), 2, replace=False).tolist())
    
    return sorted(reds), blues, probs

# =========================
# 3️⃣ 路由逻辑
# =========================
CACHE = {"data": None, "preds": None, "time": 0}

@app.route("/")
def index():
    now = time.time()
    # 5分钟内不重复计算 AI，保护服务器
    if CACHE["data"] and (now - CACHE["time"] < 300):
        history = CACHE["data"]
        ai_res = CACHE["preds"]
    else:
        history = DataEngine().fetch()
        if not history: return "数据同步中...", 503
        ai_res = train_and_predict(history)
        CACHE["data"], CACHE["preds"], CACHE["time"] = history, ai_res, now

    reds, blues, probs = ai_res
    
    # 增加遗漏值计算用于矩阵
    r_omission = {i: 0 for i in range(1, 36)}
    for n in range(1, 36):
        for h in history:
            if n in h['r']: break
            r_omission[n] += 1

    return render_template(
        "index.html",
        reds=reds, blues=blues, 
        probs=sorted(probs.items(), key=lambda x:x[1], reverse=True),
        history=history,
        r_omission=r_omission,
        last=history[0]
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
