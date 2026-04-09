from flask import Flask, render_template
import requests, re, time, datetime, os
import numpy as np
from sklearn.ensemble import RandomForestClassifier

app = Flask(__name__, template_folder="web")
app.secret_key = os.environ.get("SECRET_KEY", "dextro_armor_v13")

# =========================
# 1️⃣ 增强型数据引擎
# =========================
class DataEngine:
    def __init__(self):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    def fetch_stable(self):
        data = self._sina()
        if not data:
            data = self._500()
        return self._clean_data(data)

    def _clean_data(self, raw_data):
        """核心修复：强制清洗所有非法号码，确保只有 1-35 和 1-12"""
        clean_list = []
        for item in raw_data:
            try:
                r_nums = sorted([int(x) for x in item['r'] if str(x).isdigit() and 1 <= int(x) <= 35])
                b_nums = sorted([int(x) for x in item['b'] if str(x).isdigit() and 1 <= int(x) <= 12])
                if len(r_nums) == 5 and len(b_nums) == 2:
                    clean_list.append({
                        "p": str(item['p']),
                        "date": str(item.get('date', '-')),
                        "r": r_nums,
                        "b": b_nums
                    })
            except: continue
        return clean_list

    def _sina(self):
        try:
            url = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?gameNo=85&pageSize=50"
            res = requests.get(url, timeout=5, headers=self.headers)
            js = res.json()
            return [{
                "p": i['lotteryDrawNum'],
                "date": i['lotteryDrawTime'],
                "r": i['lotteryDrawResult'].split()[:5],
                "b": i['lotteryDrawResult'].split()[5:]
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
                    data.append({"p": tds[0].strip(), "date": tds[14] if len(tds)>14 else "-", "r": tds[2:7], "b": tds[7:9]})
            return data
        except: return []

# =========================
# 2️⃣ AI 预测引擎
# =========================
def train_and_predict(history):
    if len(history) < 15: return [1,2,3,4,5], [1,2], {i:0 for i in range(1,36)}
    
    h_rev = history[::-1]
    X, Y = [], {i: [] for i in range(1, 36)}
    
    for i in range(len(h_rev)-1):
        X.append([1 if n in h_rev[i]['r'] else 0 for n in range(1, 36)])
        for n in range(1, 36):
            Y[n].append(1 if n in h_rev[i+1]['r'] else 0)

    last_feat = [1 if n in history[0]['r'] else 0 for n in range(1, 36)]
    probs = {}
    for n in range(1, 36):
        try:
            clf = RandomForestClassifier(n_estimators=20, max_depth=5)
            clf.fit(X, Y[n])
            probs[n] = float(clf.predict_proba([last_feat])[0][1])
        except: probs[n] = 0.0
        
    reds = sorted(probs, key=probs.get, reverse=True)[:5]
    blues = sorted(np.random.choice(range(1, 13), 2, replace=False).tolist())
    return sorted(reds), blues, {k: round(v*100, 2) for k, v in probs.items()}

# =========================
# 3️⃣ 路由逻辑
# =========================
CACHE = {"data": None, "preds": None, "time": 0}

@app.route("/")
def index():
    now = time.time()
    if CACHE["data"] and (now - CACHE["time"] < 300):
        history = CACHE["data"]
        ai_res = CACHE["preds"]
    else:
        history = DataEngine().fetch_stable()
        if not history: return "数据源正在同步，请刷新重试", 503
        ai_res = train_and_predict(history)
        CACHE["data"], CACHE["preds"], CACHE["time"] = history, ai_res, now

    reds, blues, probs = ai_res
    
    # 计算遗漏值（带安全检查）
    r_omission = {i: 0 for i in range(1, 36)}
    for n in range(1, 36):
        for h in history:
            if n in h['r']: break
            r_omission[n] += 1
            
    # 计算事实避热池
    red_freq = {i: 0 for i in range(1, 36)}
    for h in history[:10]:
        for n in h['r']:
            if n in red_freq: red_freq[n] += 1 # 再次双重检查
    hot_red = sorted(red_freq, key=red_freq.get, reverse=True)[:8]

    return render_template("index.html", 
                           reds=reds, blues=blues, 
                           probs=sorted(probs.items(), key=lambda x:x[1], reverse=True),
                           history=history, r_omission=r_omission,
                           hot_red=hot_red, last=history[0])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
