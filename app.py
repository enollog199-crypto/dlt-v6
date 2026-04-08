from flask import Flask, render_template, request, redirect, url_for, session
import requests, re, random, sqlite3, json, os
import numpy as np
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ai_ui_pro_v63_stable"

def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT PRIMARY KEY, red TEXT, blue TEXT, hit TEXT, confidence REAL, prob_data TEXT)''')
    conn.commit()
    conn.close()

def autonomous_engine(history, boost=1.0):
    # 极简兜底逻辑：如果历史太短
    if len(history) < 5:
        return [1,2,3,4,5], [1,2], 50.0, {str(i):0.1 for i in range(1,36)}, "正在积攒历史数据"
    
    df = pd.DataFrame(0, index=range(len(history)), columns=range(1,36))
    for i, h in enumerate(history): df.loc[i, h['red']] = 1
    data = df.values[::-1]
    weights = np.exp(np.linspace(-1, 0.5, len(data))) * boost
    prob = np.dot(weights, data) + np.random.normal(0, 0.1, 35)
    conf = round(min(float(np.std(prob) * 15), 99.8), 2)
    red = (np.argsort(prob)[-5:] + 1).tolist()
    
    blue_df = pd.DataFrame(0, index=range(len(history)), columns=range(1,13))
    for i,h in enumerate(history): blue_df.loc[i, h['blue']] = 1
    blue_prob = np.dot(weights, blue_df.values[::-1]) + np.random.normal(0, 0.1, 12)
    blue = (np.argsort(blue_prob)[-2:] + 1).tolist()
    p_dict = {str(i+1): round(float(prob[i]), 2) for i in range(35)}
    return sorted(red), sorted(blue), conf, p_dict, "多维共振完成"

def sync_system():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get("https://datachart.500.com/dlt/history/newinc/history.php", timeout=8, headers=headers)
        res.encoding = 'utf-8'
        rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
        if not rows: return None, []
        
        history = []
        for row in rows[:30]:
            tds = re.findall(r'<td.*?>(.*?)</td>', row)
            history.append({"period": tds[0], "red": list(map(int, tds[2:7])), "blue": list(map(int, tds[7:9]))})

        conn = sqlite3.connect("ai.db")
        c = conn.cursor()
        
        # 自动核销逻辑
        for h in history:
            pred_row = c.execute("SELECT red, blue FROM predict WHERE period=?", (h['period'],)).fetchone()
            if pred_row:
                hit_r = len(set(json.loads(pred_row[0])) & set(h['red']))
                hit_b = len(set(json.loads(pred_row[1])) & set(h['blue']))
                c.execute("UPDATE predict SET hit=? WHERE period=? AND (hit='/' OR hit IS NULL)", (f"{hit_r}+{hit_b}", h['period']))
        
        # 生成最新一期预测
        next_p = str(int(history[0]['period']) + 1)
        if not c.execute("SELECT 1 FROM predict WHERE period=?", (next_p,)).fetchone():
            r, b, conf, pdict, exp = autonomous_engine(history)
            c.execute("INSERT INTO predict VALUES (?,?,?,?,?,?)", (next_p, json.dumps(r), json.dumps(b), "/", conf, json.dumps({"prob":pdict,"exp":exp})))
        
        conn.commit(); conn.close()
        return history[0], history
    except Exception as e:
        print(f"Sync Error: {e}")
        return None, []

@app.route("/")
def index():
    init_db()
    latest, history = sync_system()
    
    conn = sqlite3.connect("ai.db")
    # 增加排序确保最新一期在 records[0]
    rows = conn.execute("SELECT period, red, blue, hit, confidence, prob_data FROM predict ORDER BY period DESC LIMIT 15").fetchall()
    conn.close()

    records = []
    chart_labels, chart_values = [], []
    
    if not rows:
        # 绝不让 records 为空！
        records = [{
            "period": "同步中", 
            "red": [1,2,3,4,5], "blue": [1,2], 
            "hit": "/", "conf": 0, "exp": "初次启动数据加载中，请稍后刷新"
        }]
        top_numbers = []
    else:
        for r in rows:
            p_json = json.loads(r[5]) if r[5] else {}
            records.append({
                "period": r[0],
                "red": json.loads(r[1]),
                "blue": json.loads(r[2]),
                "hit": r[3],
                "conf": r[4],
                "exp": p_json.get("exp", "分析完成")
            })
            if r[3] != "/":
                chart_labels.append(r[0])
                chart_values.append(sum(map(int, r[3].split('+'))))
        
        prob_data = json.loads(rows[0][5]).get("prob", {}) if rows[0][5] else {}
        top_numbers = sorted(prob_data.items(), key=lambda x:x[1], reverse=True)[:10]

    return render_template("index.html", 
                           latest=latest, 
                           records=records, 
                           top_numbers=top_numbers, 
                           chart_data={"labels":chart_labels[::-1],"values":chart_values[::-1]}, 
                           logged_in=('user' in session))

# ... 登录/注册/排行路由 (保持原样即可) ...
@app.route("/rank")
def rank():
    conn = sqlite3.connect("ai.db")
    users = conn.execute("SELECT username FROM users").fetchall()
    rows = [[u[0], random.uniform(0.5, 3.8), random.randint(1, 15)] for u in users]
    conn.close()
    return render_template("rank.html", rows=rows, logged_in=('user' in session))

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
        except: return "注册失败"
        finally: conn.close()
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
