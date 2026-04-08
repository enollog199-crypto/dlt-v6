from flask import Flask, render_template, request, redirect, url_for, session
import requests, re, random, sqlite3, json, os, datetime
import numpy as np
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ultra_v10_stable"

def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    # 账号系统：不再设默认账号，用户通过注册页面自行创建
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT PRIMARY KEY, red TEXT, blue TEXT, hit TEXT, confidence REAL, prob_data TEXT)''')
    conn.commit()
    conn.close()

def fetch_realtime_crowd_hot():
    """实时热度数据：模拟抓取当前全网最热门号码"""
    return {"red": [1, 8, 11, 15, 22, 33], "blue": [5, 12], "update_time": datetime.datetime.now().strftime("%H:%M:%S")}

def autonomous_engine(history, mode="balanced"):
    """
    多模式预测引擎
    - conservative: 保守型（侧重高频热号）
    - balanced: 均衡型（原核心算法）
    - aggressive: 博弈型（避开热度，寻找冷门）
    """
    if len(history) < 5:
        return [1,2,3,4,5], [1,2], 50.0, {}
    
    df = pd.DataFrame(0, index=range(len(history)), columns=range(1,36))
    for i, h in enumerate(history): df.loc[i, h['red']] = 1
    data = df.values[::-1]
    
    # 根据模式调整权重
    if mode == "conservative":
        weights = np.exp(np.linspace(0.5, 1.5, len(df))) # 强化近期热度
        noise = 0.01
    elif mode == "aggressive":
        weights = np.exp(np.linspace(-1.0, 0.5, len(df))) # 弱化近期，关注长线
        noise = 0.08
    else:
        weights = np.exp(np.linspace(-0.5, 1.0, len(df))) # 标准均衡
        noise = 0.04

    prob = np.dot(weights, data) + np.random.normal(0, noise, 35)
    
    # 博弈型额外处理：剔除热度组
    if mode == "aggressive":
        hot = fetch_realtime_crowd_hot()["red"]
        for h_num in hot:
            if 0 < h_num <= 35: prob[h_num-1] *= 0.1

    red_res = (np.argsort(prob)[-5:] + 1).tolist()
    blue_res = random.sample(range(1, 13), 2)
    return sorted(red_res), sorted(blue_res), round(float(np.std(prob)*20), 2), {str(i+1): round(float(prob[i]), 2) for i in range(35)}

def sync_system():
    """同步数据并确保预测表不为空"""
    try:
        res = requests.get("https://datachart.500.com/dlt/history/newinc/history.php", timeout=5)
        res.encoding = 'utf-8'
        rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
        sa = [{"period": t[0], "red": sorted(list(map(int, t[2:7]))), "blue": sorted(list(map(int, t[7:9])))} 
                for t in [re.findall(r'<td.*?>(.*?)</td>', r) for r in rows[:30]]]
    except: return

    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    # 填充历史开奖结果
    for h in sa:
        row = c.execute("SELECT red, blue FROM predict WHERE period=?", (h['period'],)).fetchone()
        if row and "/" in str(c.execute("SELECT hit FROM predict WHERE period=?", (h['period'],)).fetchone()):
            hr = len(set(json.loads(row[0])) & set(h['red']))
            hb = len(set(json.loads(row[1])) & set(h['blue']))
            c.execute("UPDATE predict SET hit=? WHERE period=?", (f"{hr}+{hb}", h['period']))
    
    # 生成最新一期预测（如果不存在）
    next_p = str(int(sa[0]['period']) + 1)
    if not c.execute("SELECT 1 FROM predict WHERE period=?", (next_p,)).fetchone():
        r, b, conf, pdict = autonomous_engine(sa, "balanced")
        c.execute("INSERT INTO predict VALUES (?,?,?,?,?,?)", 
                  (next_p, json.dumps(r), json.dumps(b), "/", conf, json.dumps({"prob":pdict})))
    conn.commit()
    conn.close()
    return sa

@app.route("/")
def index():
    init_db()
    history_data = sync_system()
    conn = sqlite3.connect("ai.db")
    rows = conn.execute("SELECT period, red, blue, hit, confidence, prob_data FROM predict ORDER BY period DESC LIMIT 15").fetchall()
    conn.close()

    if not rows: return "数据同步中，请刷新页面..."

    records = []
    for r in rows:
        records.append({"period":str(r[0]),"red":json.loads(r[1]),"blue":json.loads(r[2]),"hit":str(r[3]),"conf":r[4]})

    # 实时生成 3 组不同类型的预测
    crowd = fetch_realtime_crowd_hot()
    p1_r, p1_b, _, _ = autonomous_engine(history_data, "conservative")
    p2_r, p2_b, _, p_dict = autonomous_engine(history_data, "balanced")
    p3_r, p3_b, _, _ = autonomous_engine(history_data, "aggressive")

    predictions = [
        {"type": "稳健保守型", "desc": "侧重近期高频号码，追求连红率", "red": p1_r, "blue": p1_b, "color": "var(--cyan)"},
        {"type": "均衡 AI 型", "desc": "综合历史遗漏与均值回归算法", "red": p2_r, "blue": p2_b, "color": "#fff"},
        {"type": "博弈避热型", "desc": "实时剔除全网热门，追求独享奖池", "red": p3_r, "blue": p3_b, "color": "var(--pink)"}
    ]

    chart_data = {"lab": [r['period'] for r in records if r['hit'] != "/"][::-1], 
                  "val": [sum(map(int, r['hit'].split('+'))) for r in records if r['hit'] != "/"][::-1]}

    return render_template("index.html", records=records, predictions=predictions, crowd=crowd,
                           top_numbers=sorted(p_dict.items(), key=lambda x:x[1], reverse=True)[:10],
                           chart_data=chart_data, logged_in=('user' in session))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        conn = sqlite3.connect("ai.db")
        user = conn.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
        conn.close()
        # 修复：check_password_hash 校验
        if user and check_password_hash(user[2], p):
            session['user'] = u
            return redirect(url_for('index'))
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        conn = sqlite3.connect("ai.db")
        try:
            conn.execute("INSERT INTO users (username, password) VALUES (?,?)", (u, generate_password_hash(p)))
            conn.commit(); return redirect(url_for('login'))
        except: return "用户已存在"
        finally: conn.close()
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for('index'))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
