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
# 数据库与数据处理
# =========================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    balance = db.Column(db.Float, default=1000.0)

class DataEngine:
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
            url = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?gameNo=85&pageSize=100"
            res = requests.get(url, timeout=5)
            js = res.json()
            data = []
            for i in js['value']['list']:
                nums = i['lotteryDrawResult'].split()
                data.append({
                    "p": i['lotteryDrawNum'],
                    "date": i['lotteryDrawTime'], # 修复日期抓取
                    "r": self._safe_nums(nums[:5], 1, 35),
                    "b": self._safe_nums(nums[5:], 1, 12)
                })
            return data
        except: return []

# =========================
# AI 三组预测逻辑
# =========================
def get_three_predictions(history, hot_red, hot_blue):
    if len(history) < 20: return []
    
    # 基础特征准备
    h_rev = history[::-1]
    X = [[1 if n in h['r'] else 0 for n in range(1, 36)] for h in h_rev[:-1]]
    last_feat = [[1 if n in history[0]['r'] else 0 for n in range(1, 36)]]
    
    # 预训练模型获取概率
    probs = {}
    for n in range(1, 36):
        y = [1 if n in h_rev[i+1]['r'] else 0 for i in range(len(h_rev)-1)]
        clf = RandomForestClassifier(n_estimators=20, max_depth=5)
        clf.fit(X, y)
        probs[n] = clf.predict_proba(last_feat)[0][1]

    # 1. 机器学习回归组 (基于 AI 概率最高)
    p1_r = sorted(probs, key=probs.get, reverse=True)[:5]
    p1_b = sorted(np.random.choice(range(1,13), 2, replace=False).tolist())

    # 2. 事实避热组 (剔除热号后重随机)
    cool_pool = [n for n in range(1, 36) if n not in hot_red]
    p2_r = sorted(random.sample(cool_pool, 5))
    cool_blue = [n for n in range(1, 13) if n not in hot_blue]
    p2_b = sorted(random.sample(cool_blue, 2)) if len(cool_blue)>=2 else [1,2]

    # 3. 极速遗漏组 (取遗漏值最高的号码)
    omissions = {i: 0 for i in range(1,36)}
    for n in range(1,36):
        for h in history:
            if n in h['r']: break
            omissions[n]+=1
    p3_r = sorted(omissions, key=omissions.get, reverse=True)[:5]
    p3_b = [1, 12] # 边界示例

    return [
        {"name": "机器学习回归组", "method": "RandomForest 随机森林模型对近百期数据进行特征拟合，捕捉非线性时序规律。", "r": sorted(p1_r), "b": p1_b, "color": "#22d3ee"},
        {"name": "事实避热对冲组", "method": "强制剔除近 10 期内高频出现的“过热”号码，在大数定律回归压力下寻找冷区切入。", "r": sorted(p2_r), "b": p2_b, "color": "#f43f5e"},
        {"name": "极大遗漏回补组", "method": "基于热力学遗漏模型，筛选当前遗漏值处于峰值的号码，博取反弹机会。", "r": sorted(p3_r), "b": p3_b, "color": "#fbbf24"}
    ]

@app.route("/")
def index():
    engine = DataEngine()
    history = engine.fetch_all()
    if not history: return "数据同步中...", 503
    
    # 计算避热池
    red_freq = {i: 0 for i in range(1, 36)}
    blue_freq = {i: 0 for i in range(1, 13)}
    for h in history[:10]:
        for n in h['r']: red_freq[n] += 1
        for n in h['b']: blue_freq[n] += 1
    hot_red = sorted(red_freq, key=red_freq.get, reverse=True)[:6]
    hot_blue = sorted(blue_freq, key=blue_freq.get, reverse=True)[:2]

    preds = get_three_predictions(history, hot_red, hot_blue)
    
    # 遗漏值（用于趋势图）
    r_omission = {i: 0 for i in range(1,36)}
    for n in range(1,36):
        for h in history:
            if n in h['r']: break
            r_omission[n] += 1

    return render_template("index.html", 
                           history=history, 
                           preds=preds, 
                           hot_red=hot_red, 
                           hot_blue=hot_blue, 
                           r_omission=r_omission,
                           last=history[0])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
