from flask import Flask, render_template, request, redirect, url_for, session
import requests, re, random, sqlite3, json, os
import numpy as np
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ai_v63_open_key"

# ===== 数据库：自愈式初始化 =====
def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT PRIMARY KEY, red TEXT, blue TEXT, hit TEXT, confidence REAL, prob_data TEXT)''')
    conn.commit()
    conn.close()

# ===== AI 引擎：V63 自主进化版 =====
def autonomous_engine(history, boost=1.0):
    if len(history) < 15:
        return sorted(random.sample(range(1,36),5)), sorted(random.sample(range(1,13),2)), 50.0, {}, "数据预热中"
    
    df = pd.DataFrame(0, index=range(len(history)), columns=range(1,36))
    for i, h in enumerate(history): df.loc[i, h['red']] = 1
    data = df.values[::-1]

    # 动态权重计算
    trend_weights = np.exp(np.linspace(-1, 0.5, len(data))) * boost
    gap_bonus = np.zeros(35)
    for col in range(35):
        idx = np.where(data[:, col] == 1)[0]
        gap_bonus[col] = (len(data) - idx[-1]) * 0.15 if len(idx) > 0 else len(data) * 0.2

    prob = np.dot(trend_weights, data) + gap_bonus
    prob = np.maximum(prob, 0) + np.random.normal(0, 0.1, 35)
    
    confidence = round(min(float(np.std(prob) * 15), 99.8), 2)
    red = (np.argsort(prob)[-5:] + 1).tolist()
    
    # 蓝球逻辑
    blue_df = pd.DataFrame(0, index=range(len(history)), columns=range(1,13))
    for i,h in enumerate(history): blue_df.loc[i, h['blue']] = 1
    blue_prob = np.dot(trend_weights, blue_df.values[::-1]) + np.random.normal(0, 0.1, 12)
    blue = (np.argsort(blue_prob)[-2:] + 1).tolist()

    prob_dict = {str(i+1): round(float(prob[i]), 2) for i in range(35)}
    return sorted(red), sorted(blue), confidence, prob_dict, "模型自学完成"

# ===== 自动核销与数据同步 =====
def sync_system():
    try:
        res = requests.get("https://datachart.500.com/dlt/history/newinc/history.php", timeout=8)
        res.encoding = 'utf-8'
        rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
        history = []
        for row in rows[:30]:
            tds = re.findall(r'<td.*?>(.*?)</td>', row)
            history.append({"period": tds[0], "red": list(map(int, tds[2:7])), "blue": list(map(int, tds[7:9]))})

        conn = sqlite3.connect("ai.db")
        c = conn.cursor()
        boost = 1.0

        for h in history:
            pred = c.execute("SELECT red, blue, hit FROM predict WHERE period=?", (h['period'],)).fetchone()
            if pred and (pred[2] == "/" or pred[2] is None):
                hit_r = len(set(json.loads(pred[0])) & set(h['red']))
                hit_b = len(set(json.loads(pred[1])) & set(h['blue']))
                c.execute("UPDATE predict SET hit=? WHERE period=?", (f"{hit_r}+{hit_b}", h['period']))
                boost = 1.12 if (hit_r + hit_b) >= 2 else 0.95

        next_p = str(int(history[0]['period']) + 1)
        if not c.execute("SELECT 1 FROM predict WHERE period=?", (next_p,)).fetchone():
            r, b, conf, pdict, exp = autonomous_engine(history, boost)
            c.execute("INSERT INTO predict VALUES (?,?,?,?,?,?)", (next_p, json.dumps(r), json.dumps(b), "/", conf, json.dumps({"prob":pdict,"exp":exp})))
        
        conn.commit(); conn.close()
        return history[0], history
    except: return None, []

# ===== 路由：首页 (公开浏览) =====
@app.route("/")
def index():
    init_db()
    latest, history = sync_system()
    conn = sqlite3.connect("ai.db")
    rows = conn.execute("SELECT * FROM predict ORDER BY period DESC LIMIT 15").fetchall()
    conn.close()

    records = []
    chart_labels, chart_values = [], []
    for r in rows:
        p_data = json.loads(r[5]) if r[5] else {}
        records.append({"period":r[0],"red":json.loads(r[1]),"blue":json.loads(r[2]),"hit":r[3],"conf":r[4],"exp":p_data.get("exp","")})
        if r[3] != "/":
            chart_labels.append(r[0]); chart_values.append(sum(map(int, r[3].split('+'))))

    prob_data = json.loads(rows[0][5])["prob"] if rows and rows[0][5] else {}
    top_numbers = sorted(prob_data.items(), key=lambda x:x[1], reverse=True)[:10]

    return render_template("index.html", 
                           latest=latest, 
                           records=records, 
                           top_numbers=top_numbers, 
                           chart_data={"labels":chart_labels[::-1],"values":chart_values[::-1]},
                           logged_in=('user' in session))

# ===== 路由：排行榜 =====
@app.route("/rank")
def rank():
    conn = sqlite3.connect("ai.db")
    users = conn.execute("SELECT username FROM users").fetchall()
    # 模拟数据供展示
    rows = [[u[0], random.uniform(0.5, 3.8), random.randint(1, 15)] for u in users]
    conn.close()
    return render_template("rank.html", rows=rows, logged_in=('user' in session))

# ===== 管理员：登录/注册/退出 =====
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        conn = sqlite3.connect("ai.db")
        user = conn.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
        conn.close()
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
        except: return "管理员创建失败"
        finally: conn.close()
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
