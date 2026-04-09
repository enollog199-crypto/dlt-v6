from flask import Flask, render_template, request, redirect, url_for, session
import requests, re, random, sqlite3, json, os, datetime
import numpy as np
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ultra_v11_pro"

def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT PRIMARY KEY, red TEXT, blue TEXT, hit TEXT, confidence REAL, prob_data TEXT)''')
    conn.commit(); conn.close()

def fetch_realtime_crowd_hot():
    # 模拟事实避热数据
    return {"red": [1, 8, 11, 15, 22, 33], "blue": [5, 12]}

def autonomous_engine(history, mode="balanced"):
    if not history: return [1,2,3,4,5], [1,2], 0, {}
    df = pd.DataFrame(0, index=range(len(history)), columns=range(1,36))
    for i, h in enumerate(history): df.loc[i, h['red']] = 1
    data = df.values[::-1]
    
    # 权重逻辑
    w_map = {"conservative": [0.8, 1.8], "balanced": [-0.5, 1.2], "aggressive": [-1.2, 0.6]}
    l, r_val = w_map.get(mode, w_map["balanced"])
    weights = np.exp(np.linspace(l, r_val, len(df)))
    
    prob = np.dot(weights, data) + np.random.normal(0, 0.04, 35)
    
    # 事实避热逻辑（针对第4组）
    if mode == "anti_hot":
        hot = fetch_realtime_crowd_hot()["red"]
        for h_num in hot: 
            if 0 < h_num <= 35: prob[h_num-1] *= 0.05

    red_res = (np.argsort(prob)[-5:] + 1).tolist()
    blue_res = sorted(random.sample(range(1, 13), 2))
    p_dict = {str(i+1): round(float(prob[i]), 2) for i in range(35)}
    return sorted(red_res), blue_res, round(float(np.std(prob)*20), 2), p_dict

def sync_system():
    try:
        res = requests.get("https://datachart.500.com/dlt/history/newinc/history.php", timeout=5)
        res.encoding = 'utf-8'
        rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
        sa = [{"period": t[0], "red": sorted(list(map(int, t[2:7]))), "blue": sorted(list(map(int, t[7:9])))} 
                for t in [re.findall(r'<td.*?>(.*?)</td>', r) for r in rows[:60]]] # 拉取60期
    except: return []

    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    for h in sa:
        row = c.execute("SELECT red, blue FROM predict WHERE period=?", (h['period'],)).fetchone()
        if row:
            hr, hb = len(set(json.loads(row[0]))&set(h['red'])), len(set(json.loads(row[1]))&set(h['blue']))
            c.execute("UPDATE predict SET hit=? WHERE period=?", (f"{hr}+{hb}", h['period']))
    
    next_p = str(int(sa[0]['period']) + 1)
    if not c.execute("SELECT 1 FROM predict WHERE period=?", (next_p,)).fetchone():
        r, b, conf, pdict = autonomous_engine(sa, "balanced")
        c.execute("INSERT INTO predict VALUES (?,?,?,?,?,?)", (next_p, json.dumps(r), json.dumps(b), "/", conf, json.dumps({"prob":pdict})))
    conn.commit(); conn.close()
    return sa

@app.route("/")
def index():
    init_db()
    sa = sync_system()
    conn = sqlite3.connect("ai.db")
    rows = conn.execute("SELECT period, red, blue, hit, confidence, prob_data FROM predict ORDER BY period DESC LIMIT 50").fetchall()
    conn.close()

    if not rows: return "数据初始化中..."
    
    # 提取最新的预测数据和权值
    last_prob = json.loads(rows[0][5]).get("prob", {}) if rows[0][5] else {}
    
    # 生成 4 组预测
    p1 = autonomous_engine(sa, "conservative")
    p2 = autonomous_engine(sa, "balanced")
    p3 = autonomous_engine(sa, "aggressive")
    p4 = autonomous_engine(sa, "anti_hot")

    preds = [
        {"n": "保守稳健型", "r": p1[0], "b": p1[1], "d": "侧重近期高频号", "c": "var(--cyan)"},
        {"n": "AI 均衡型", "r": p2[0], "b": p2[1], "d": "标准数学建模预测", "c": "#fff"},
        {"n": "冷门博弈型", "r": p3[0], "b": p3[1], "d": "侧重长线遗漏补位", "c": "var(--amber)"},
        {"n": "事实避热型", "r": p4[0], "b": p4[1], "d": "已剔除全网热门投注", "c": "var(--pink)"}
    ]

    # 历史记录转换
    history_rows = []
    for r in sa[::-1]: # 从旧到新排列
        history_rows.append({"p": r['period'], "r": r['red'], "b": r['blue']})

    chart_data = {"lab": [str(r[0]) for r in rows if r[3]!="/"][::-1], "val": [sum(map(int, str(r[3]).split('+'))) for r in rows if r[3]!="/"][::-1]}

    return render_template("index.html", history=history_rows, preds=preds, crowd=fetch_realtime_crowd_hot(),
                           top_nums=sorted(last_prob.items(), key=lambda x:x[1], reverse=True)[:10],
                           chart_data=chart_data, last_period=sa[0], logged_in=('user' in session))

@app.route("/register", methods=["POST"])
def register():
    u, p = request.form.get("u"), request.form.get("p")
    conn = sqlite3.connect("ai.db")
    try:
        conn.execute("INSERT INTO users (username, password) VALUES (?,?)", (u, generate_password_hash(p)))
        conn.commit(); return "注册成功，请登录"
    except: return "用户已存在"
    finally: conn.close()

@app.route("/login", methods=["POST"])
def login():
    u, p = request.form.get("u"), request.form.get("p")
    conn = sqlite3.connect("ai.db")
    user = conn.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
    conn.close()
    if user and check_password_hash(user[2], p):
        session['user'] = u; return redirect(url_for('index'))
    return "登录失败"

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for('index'))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=10000)
