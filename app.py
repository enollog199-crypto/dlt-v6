from flask import Flask, render_template, request, redirect, url_for, session
import requests, re, random, sqlite3, json, os
import numpy as np
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

app = Flask(__name__, template_folder="web")
app.secret_key = os.environ.get("SECRET_KEY", "dextro_v10_deep_tech")

PRIZE_MAP = {"5+2":10000000,"5+1":800000,"5+0":10000,"4+2":3000,"4+1":300,"4+0":100,"3+2":200,"3+1":15,"3+0":5,"2+2":15,"1+2":5,"2+1":5,"0+2":5}

def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, credits REAL DEFAULT 100.0, last_checkin TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS predict (period TEXT PRIMARY KEY, draw_date TEXT, red TEXT, blue TEXT, hit_red INT, hit_blue INT, cost REAL, winnings REAL, source_type TEXT, confidence REAL)''')
    conn.commit()
    conn.close()

def deep_autoregressive_engine(history_data):
    """深度自回归预测引擎：基于时间序列权重预测"""
    if len(history_data) < 5:
        return sorted(random.sample(range(1, 36), 5)), sorted(random.sample(range(1, 13), 2)), 50.0
    
    # 构建历史矩阵
    df = pd.DataFrame(0, index=range(len(history_data)), columns=range(1, 36))
    for i, h in enumerate(history_data):
        df.loc[i, h['red']] = 1
    
    # 权重衰减：越近的数据对预测未来影响越大
    data_array = df.values[::-1]
    decay_weights = np.exp(np.linspace(-1, 0, len(data_array))) 
    prob_vector = np.dot(decay_weights, data_array)
    
    # 引入噪声扰动 (模拟感知机 Dropout)
    prob_vector += np.random.normal(0, 0.2, 35)
    
    # 取概率最高的5个
    red_indices = (np.argsort(prob_vector)[-5:] + 1).tolist()
    blue_indices = (np.argsort(np.random.dirichlet(np.ones(12), k=1)[0])[-2:] + 1).tolist()
    
    # 计算置信度 (基于概率分布的集中度)
    conf = float(np.min([99.9, 60.0 + np.std(prob_vector) * 10]))
    
    return sorted(red_indices), sorted(blue_indices), conf

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route("/checkin", methods=["POST"])
@login_required
def checkin():
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect("ai.db")
    user = conn.execute("SELECT last_checkin FROM users WHERE username=?", (session['user'],)).fetchone()
    if user[0] != today:
        reward = random.randint(30, 100)
        conn.execute("UPDATE users SET credits = credits + ?, last_checkin = ? WHERE username=?", (reward, today, session['user']))
        conn.commit()
    return redirect(url_for('index'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        user = sqlite3.connect("ai.db").execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
        if user and check_password_hash(user[2], p):
            session['user'] = u
            return redirect(url_for('index'))
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        try:
            conn = sqlite3.connect("ai.db")
            conn.execute("INSERT INTO users (username, password) VALUES (?,?)", (u, generate_password_hash(p)))
            conn.commit()
            return redirect(url_for('login'))
        except: return "用户已存在"
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop('user', None); return redirect(url_for('login'))

@app.route("/")
@login_required
def index():
    init_db()
    conn = sqlite3.connect("ai.db")
    user_data = conn.execute("SELECT credits, last_checkin FROM users WHERE username=?", (session['user'],)).fetchone()
    
    try:
        res = requests.get("https://datachart.500.com/dlt/history/newinc/history.php", timeout=5)
        res.encoding = 'utf-8'
        rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
        history = [{"period": t[0], "date": t[1], "red": [int(x) for x in t[2:7]], "blue": [int(x) for x in t[7:9]]} for t in [re.findall(r'<td.*?>(.*?)</td>', r) for r in rows[:15]]]
        
        # 自动核销开奖结果
        for h in history:
            row = conn.execute("SELECT red, blue, hit_red FROM predict WHERE period=?", (h['period'],)).fetchone()
            if row and row[2] == -1:
                hr, hb = len(set(json.loads(row[0])) & set(h['red'])), len(set(json.loads(row[1])) & set(h['blue']))
                conn.execute("UPDATE predict SET draw_date=?, hit_red=?, hit_blue=?, winnings=? WHERE period=?", (h['date'], hr, hb, PRIZE_MAP.get(f"{hr}+{hb}", 0), h['period']))
        conn.commit()

        # 生成深度学习预测
        next_p = str(int(history[0]['period']) + 1)
        if not conn.execute("SELECT 1 FROM predict WHERE period=?", (next_p,)).fetchone():
            r, b, conf = deep_autoregressive_engine(history)
            conn.execute("INSERT INTO predict VALUES (?,?,?,?,?,?,?,?,?,?)", (next_p, "待开奖", str(r), str(b), -1, -1, 2.0, 0.0, "深度自回归 V10", conf))
            conn.commit()
    except Exception as e: print(f"Error: {e}")

    recs = conn.execute("SELECT * FROM predict ORDER BY period DESC LIMIT 12").fetchall()
    top_users = conn.execute("SELECT username, credits FROM users ORDER BY credits DESC LIMIT 5").fetchall()
    
    formatted = [{"p":r[0],"d":r[1],"r":json.loads(r[2]),"b":json.loads(r[3]),"hr":r[4],"hb":r[5],"win":r[7],"src":r[8], "conf": r[9]} for r in recs]
    chart = {"labels": [r[0] for r in recs if r[4]!=-1][::-1], "hits": [r[4]+r[5] for r in recs if r[4]!=-1][::-1]}

    return render_template("index.html", user=session['user'], credits=user_data[0], can_checkin=(user_data[1]!=datetime.now().strftime('%Y-%m-%d')), records=formatted, chart=chart, top_users=top_users)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
