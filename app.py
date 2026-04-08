from flask import Flask, render_template, request, redirect, url_for, session
import requests, re, random, sqlite3, json, os
import numpy as np
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ultra_secret_key"

# ===== 数据库初始化 =====
def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT PRIMARY KEY, red TEXT, blue TEXT, hit TEXT, confidence REAL, prob_data TEXT)''')
    conn.commit()
    conn.close()

# ===== 认证装饰器 =====
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ===== AI 引擎 (V63 增强版) =====
def autonomous_engine(history, boost=1.0):
    if len(history) < 15:
        return sorted(random.sample(range(1,36),5)), sorted(random.sample(range(1,13),2)), 50.0, {}, "初始化中"

    df = pd.DataFrame(0, index=range(len(history)), columns=range(1,36))
    for i, h in enumerate(history): df.loc[i, h['red']] = 1
    data = df.values[::-1]

    # 动态学习因子
    trend_weights = np.exp(np.linspace(-1, 0.5, len(data))) * boost
    gap_bonus = np.zeros(35)
    for col in range(35):
        idx = np.where(data[:, col] == 1)[0]
        gap_bonus[col] = (len(data) - idx[-1]) * 0.15 if len(idx) > 0 else len(data) * 0.2

    prob = np.dot(trend_weights, data) + gap_bonus
    prob = np.maximum(prob, 0) + np.random.normal(0, 0.1, 35)

    # 置信度：基于激活强度
    confidence = round(min(float(np.std(prob) * 15), 99.8), 2)
    explain = "趋势爆发期" if confidence > 75 else ("冷号活跃期" if np.mean(gap_bonus) > 2.5 else "周期平衡期")

    red = (np.argsort(prob)[-5:] + 1).tolist()
    
    # 蓝球逻辑
    blue_df = pd.DataFrame(0, index=range(len(history)), columns=range(1,13))
    for i,h in enumerate(history): blue_df.loc[i, h['blue']] = 1
    blue_prob = np.dot(trend_weights, blue_df.values[::-1]) + np.random.normal(0, 0.1, 12)
    blue = (np.argsort(blue_prob)[-2:] + 1).tolist()

    prob_dict = {str(i+1): round(float(prob[i]), 2) for i in range(35)}
    return sorted(red), sorted(blue), confidence, prob_dict, explain

# ===== 核心同步逻辑 =====
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
            if pred and pred[2] == "/":
                hit_r = len(set(json.loads(pred[0])) & set(h['red']))
                hit_b = len(set(json.loads(pred[1])) & set(h['blue']))
                c.execute("UPDATE predict SET hit=? WHERE period=?", (f"{hit_r}+{hit_b}", h['period']))
                # 强化学习因子更新
                boost = 1.1 if (hit_r + hit_b) >= 3 else 0.95

        next_p = str(int(history[0]['period']) + 1)
        if not c.execute("SELECT 1 FROM predict WHERE period=?", (next_p,)).fetchone():
            r, b, conf, pdict, exp = autonomous_engine(history, boost)
            c.execute("INSERT INTO predict VALUES (?,?,?,?,?,?)", (next_p, json.dumps(r), json.dumps(b), "/", conf, json.dumps({"prob":pdict,"exp":exp})))
        
        conn.commit(); conn.close()
        return history[0], history
    except: return None, []

# ===== 路由逻辑 =====
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
            conn.commit()
            return redirect(url_for('login'))
        except: return "用户已存在"
        finally: conn.close()
    return render_template("register.html")

@app.route("/")
@login_required
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
            chart_labels.append(r[0])
            chart_values.append(sum(map(int, r[3].split('+'))))

    prob_data = json.loads(rows[0][5])["prob"] if rows else {}
    top_numbers = sorted(prob_data.items(), key=lambda x:x[1], reverse=True)[:10]

    return render_template("index.html", latest=latest, records=records, top_numbers=top_numbers, chart_data={"labels":chart_labels[::-1],"values":chart_values[::-1]})

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
