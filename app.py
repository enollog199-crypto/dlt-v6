import warnings
warnings.filterwarnings("ignore", category=UserWarning)

from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests, re, time, datetime, os, random
import numpy as np
from sklearn.ensemble import RandomForestClassifier

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_quantum_v16_final"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dextro_game.db'
db = SQLAlchemy(app)

# =========================
# 1. 数据库
# =========================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    balance = db.Column(db.Float, default=1000.0)

with app.app_context():
    db.create_all()

# =========================
# 2. 数据抓取引擎
# =========================
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
                data = [d for d in data if len(d['r']) == 5 and len(d['b']) == 2]
                if data: return data
        except: pass
        return []

# =========================
# 3. AI 预测逻辑 (已降负)
# =========================
def get_three_predictions(history, hot_red, hot_blue):
    if len(history) < 20: return []
    h_rev = history[::-1]
    X = [[1 if n in h['r'] else 0 for n in range(1, 36)] for h in h_rev[:-1]]
    last_feat = [[1 if n in history[0]['r'] else 0 for n in range(1, 36)]]
    
    probs = {}
    for n in range(1, 36):
        y = [1 if n in h_rev[i+1]['r'] else 0 for i in range(len(h_rev)-1)]
        if len(set(y)) < 2:
            probs[n] = 0.0
            continue
        try:
            # 修改 2：降低估算器数量，强制单线程运行防止卡死
            clf = RandomForestClassifier(n_estimators=6, max_depth=5, n_jobs=1)
            clf.fit(X, y)
            probs[n] = clf.predict_proba(last_feat)[0][1]
        except:
            probs[n] = 0.0

    p1_r = sorted(probs, key=probs.get, reverse=True)[:5]
    p1_b = sorted(random.sample(range(1, 13), 2))
    
    cool_pool = [n for n in range(1, 36) if n not in hot_red]
    cool_blue = [n for n in range(1, 13) if n not in hot_blue]
    p2_r = sorted(random.sample(cool_pool, min(5, len(cool_pool))))
    p2_b = sorted(random.sample(cool_blue, min(2, len(cool_blue)))) if cool_blue else [1,2]

    omissions = {i: 0 for i in range(1,36)}
    for n in range(1,36):
        for h in history:
            if n in h['r']: break
            omissions[n]+=1
    p3_r = sorted(omissions, key=omissions.get, reverse=True)[:5]

    return [
        {"name": "机器学习回归组", "method": "随机森林轻量化模型拟合趋势。", "r": sorted(p1_r), "b": p1_b, "color": "#22d3ee"},
        {"name": "事实避热对冲组", "method": "剔除高频号，博取冷码反弹机会。", "r": sorted(p2_r), "b": p2_b, "color": "#f43f5e"},
        {"name": "极大遗漏回补组", "method": "当前遗漏峰值号码筛选。", "r": sorted(p3_r), "b": [1, 12], "color": "#fbbf24"}
    ]

# =========================
# 4. 路由与缓存 (核心修改)
# =========================
CACHE = {"time": 0, "data": None}

@app.route("/")
def index():
    now = time.time()
    
    # 修改 1：5分钟内只抓取和计算一次
    if CACHE["data"] and (now - CACHE["time"] < 300):
        history, preds, hot_red, hot_blue, r_omission = CACHE["data"]
    else:
        history = DataEngine().fetch_all()
        if not history or len(history) < 10:
            return "数据源响应超时，请稍后刷新重试", 503
        
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
                r_omission[n]+=1
        
        # 存入缓存
        CACHE["data"] = (history, preds, hot_red, hot_blue, r_omission)
        CACHE["time"] = now

    return render_template("index.html", 
                           history=history, preds=preds, 
                           hot_red=hot_red, hot_blue=hot_blue, 
                           r_omission=r_omission, last=history[0])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
