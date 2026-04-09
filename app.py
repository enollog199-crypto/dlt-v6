from flask import Flask, render_template
import requests, re, time, datetime, os
import numpy as np
from sklearn.ensemble import RandomForestClassifier

app = Flask(__name__, template_folder="web")
app.secret_key = os.environ.get("SECRET_KEY", "dextro_ultra_secure_v14")

# =========================
# 1️⃣ 增强型数据引擎 (含安全解析)
# =========================
class DataEngine:
    def __init__(self):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    # 【修改 1】：引入安全解析函数，过滤非法数字和 0
    def _safe_nums(self, arr, min_v, max_v):
        out = []
        for x in arr:
            try:
                # 过滤掉非数字、0 以及超出范围的数字
                n = int(re.sub(r'<.*?>', '', str(x)).strip()) 
                if min_v <= n <= max_v:
                    out.append(n)
            except:
                continue
        # 去重并排序，确保返回的是纯净的数字列表
        return sorted(list(set(out)))

    def fetch(self):
        data = self._sina()
        if not data:
            data = self._500()
        # 过滤掉不完整的期号
        return [item for item in data if len(item['r']) == 5 and len(item['b']) == 2]

    def _sina(self):
        try:
            url = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?gameNo=85&pageSize=50"
            res = requests.get(url, timeout=5, headers=self.headers)
            js = res.json()
            data = []
            for i in js['value']['list']:
                nums = i['lotteryDrawResult'].split()
                # 【修改 2】：使用 _safe_nums 处理新浪数据
                data.append({
                    "p": i['lotteryDrawNum'],
                    "date": i['lotteryDrawTime'],
                    "r": self._safe_nums(nums[:5], 1, 35),
                    "b": self._safe_nums(nums[5:], 1, 12)
                })
            return data
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
                    # 【修改 3】：使用 _safe_nums 处理 500 网数据
                    data.append({
                        "p": tds[0].strip(),
                        "date": tds[14].strip() if len(tds)>14 else "-",
                        "r": self._safe_nums(tds[2:7], 1, 35),
                        "b": self._safe_nums(tds[7:9], 1, 12)
                    })
            return data
        except: return []

# =========================
# 2️⃣ AI 预测引擎
# =========================
def train_and_predict(history):
    # 【修改 6】：训练前过滤掉任何损坏的行
    history = [h for h in history if len(h.get('r', [])) == 5]
    
    if len(history) < 15: 
        return [1,2,3,4,5], [1,2], {i:0 for i in range(1,36)}
    
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
            clf = RandomForestClassifier(n_estimators=25, max_depth=5)
            clf.fit(X, Y[n])
            probs[n] = float(clf.predict_proba([last_feat])[0][1])
        except: probs[n] = 0.0
        
    reds = sorted(probs, key=probs.get, reverse=True)[:5]
    # 蓝球依然采用安全的随机逻辑
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
        history, ai_res = CACHE["data"], CACHE["preds"]
    else:
        history = DataEngine().fetch()
        if not history: return "数据计算中，请稍后刷新...", 503
        ai_res = train_and_predict(history)
        CACHE["data"], CACHE["preds"], CACHE["time"] = history, ai_res, now

    reds, blues, probs = ai_res
    
    # 最终防御：初始化所有字典，确保不存在 KeyError
    r_omission = {i: 0 for i in range(1, 36)}
    red_freq = {i: 0 for i in range(1, 36)}

    # 【修改 4】：在遍历历史数据时增加最终兜底
    for h in history:
        if not h.get('r') or len(h['r']) != 5:
            continue
        # 计算遗漏
        for n in range(1, 36):
            # 如果号码在这一期没出，且之前也没出过，遗漏+1
            # 这里逻辑稍微调整以确保准确
            pass 

    # 重新梳理遗漏逻辑
    for n in range(1, 36):
        count = 0
        for h in history:
            if n in h['r']: break
            count += 1
        r_omission[n] = count

    # 【修改 5】：彻底防 KeyError 的频率统计
    for h in history[:12]:
        for n in h['r']:
            if n in red_freq:
                red_freq[n] += 1
    
    hot_red = sorted(red_freq, key=red_freq.get, reverse=True)[:8]

    return render_template("index.html", 
                           reds=reds, blues=blues, 
                           probs=sorted(probs.items(), key=lambda x:x[1], reverse=True),
                           history=history, r_omission=r_omission,
                           hot_red=hot_red, last=history[0])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
