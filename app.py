import warnings
warnings.filterwarnings("ignore", category=UserWarning) # 忽略掉所有的用户警告

from flask import Flask, render_template, request # 后面保持不变...
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests, re, time, datetime, os, random
import numpy as np
from sklearn.ensemble import RandomForestClassifier

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_quantum_v16_final"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dextro_game.db'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    balance = db.Column(db.Float, default=1000.0)

with app.app_context():
    db.create_all()

class DataEngine:
    def __init__(self):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    def _safe_nums(self, arr, min_v, max_v):
        out = []
        for x in arr:
            try:
                n = int(re.sub(r'<.*?>', '', str(x)).strip())
                if min_v <= n <= max_v: out.append(n)
            except: continue
        return sorted(list(set(out)))

    def fetch_all(self):
        # 方案 A: 官方接口
        try:
            url = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?gameNo=85&pageSize=50"
            res = requests.get(url, timeout=8, headers=self.headers)
            if res.status_code == 200:
                js = res.json()
                data = []
                for i in js['value']['list']:
                    nums = i['lotteryDrawResult'].split()
                    data.append({
                        "p": i['lotteryDrawNum'],
                        "date": i['lotteryDrawTime'], 
                        "r": self._safe_nums(nums[:5], 1, 35),
                        "b": self._safe_nums(nums[5:], 1, 12)
                    })
                # 【补丁 1】：强制过滤无效行，确保 R=5, B=2
                data = [d for d in data if len(d['r']) == 5 and len(d['b']) == 2]
                if data: return data
        except: pass

        # 方案 B: 500网备用
        try:
            res = requests.get("https://datachart.500.com/dlt/history/newinc/history.php", timeout=8)
            res.encoding = 'utf-8'
            rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
            data = []
            for r in rows[:50]:
                tds = re.findall(r'<td.*?>(.*?)</td>', r)
                if len(tds) >= 9:
                    data.append({
                        "p": tds[0].strip(),
                        "date": tds[14].strip() if len(tds)>14 else "-",
                        "r": self._safe_nums(tds[2:7], 1, 35),
                        "b": self._safe_nums(tds[7:9], 1, 12)
                    })
            # 【补丁 1 再次加强】：对备用源也进行清洗
            data = [d for d in data if len(d['r']) == 5 and len(d['b']) == 2]
            return data
        except: return []

def get_three_predictions(history, hot_red, hot_blue):
    if len(history) < 20: return []
    h_rev = history[::-1]
    X = [[1 if n in h['r'] else 0 for n in range(1, 36)] for h in h_rev[:-1]]
    last_feat = [[1 if n in history[0]['r'] else 0 for n in range(1, 36)]]
    
    probs = {}
    for n in range(1, 36):
        y = [1 if n in h_rev[i+1]['r'] else 0 for i in range(len(h_rev)-1)]
        # 【补丁 2】：处理单一类别异常 (只有 0 或只有 1)
        if len(set(y)) < 2:
            probs[n] = 0.0
            continue
        try:
            clf = RandomForestClassifier(n_estimators=15, max_depth=5)
            clf.fit(X, y)
            probs[n] = clf.predict_proba(last_feat)[0][1]
        except:
            probs[n] = 0.0

    p1_r = sorted(probs, key=probs.get, reverse=True)[:5]
    p1_b = sorted(random.sample(range(1, 13), 2))
    
    # 2. 事实避热组
    cool_pool = [n for n in range(1, 36) if n not in hot_red]
    cool_blue = [n for n in range(1, 13) if n not in hot_blue]
    # 【补丁 3】：防止采样溢出 (使用 min 确保不超过池子大小)
    p2_r = sorted(random.sample(cool_pool, min(5, len(cool_pool))))
    p2_b = sorted(random.sample(cool_blue, min(2, len(cool_blue)))) if cool_blue else [1,2]

    # 3. 极大遗漏组
    omissions = {i: 0 for i in range(1,36)}
    for n in range(1,36):
        for h in history:
            if n in h['r']: break
            omissions[n]+=1
    p3_r = sorted(omissions, key=omissions.get, reverse=True)[:5]

    return [
        {"name": "机器学习回归组", "method": "基于 RandomForest 模型拟合百期非线性规律。", "r": sorted(p1_r), "b": p1_b, "color": "#22d3ee"},
        {"name": "事实避热对冲组", "method": "避开近 10 期红蓝热号，强制切入冷码区。", "r": sorted(p2_r), "b": p2_b, "color": "#f43f5e"},
        {"name": "极大遗漏回补组", "method": "捕捉当前遗漏峰值号码，博取反弹机会。", "r": sorted(p3_r), "b": [1, 12], "color": "#fbbf24"}
    ]

@app.route("/")
def index():
    history = DataEngine().fetch_all()
    # 【补丁 4】：严格判定历史数据量，防止 history[0] 越界炸裂
    if not history or len(history) < 10: 
        return "数据源响应超时或数据量不足，请稍后刷新重试 (503 Fallback)", 503
    
    red_freq = {i: 0 for i in range(1, 36)}
    blue_freq = {i: 0 for i in range(1, 13)}
    for h in history[:10]:
        for n in h['r']: red_freq[n] += 1
        for n in h['b']: blue_freq[n] += 1
    hot_red = sorted(red_freq, key=red_freq.get, reverse=True)[:6]
    hot_blue = sorted(blue_freq, key=blue_freq.get, reverse=True)[:2]

    preds = get_three_predictions(history, hot_red, hot_blue)
    r_omission = {i: 0 for i in range(1,36)}
    for n in range(1,36):
        for h in history:
            if n in h['r']: break
            r_omission[n] += 1

    return render_template("index.html", history=history, preds=preds, hot_red=hot_red, hot_blue=hot_blue, r_omission=r_omission, last=history[0])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
