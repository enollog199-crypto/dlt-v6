from flask import Flask, render_template, request, redirect, url_for, session
import requests, re, random, sqlite3, json, os
import numpy as np
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ai_final_safe_v69"

def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT PRIMARY KEY, red TEXT, blue TEXT, hit TEXT, confidence REAL, prob_data TEXT)''')
    conn.commit()
    conn.close()

def autonomous_engine(history):
    if len(history) < 5:
        return [1,2,3,4,5], [1,2], 50.0, {str(i):0.1 for i in range(1,36)}, "数据初始化..."
    df = pd.DataFrame(0, index=range(len(history)), columns=range(1,36))
    for i, h in enumerate(history): df.loc[i, h['red']] = 1
    data, weights = df.values[::-1], np.exp(np.linspace(-1.2, 0.8, len(df)))
    prob = np.dot(weights, data) + np.random.normal(0, 0.05, 35)
    red_res = (np.argsort(prob)[-5:] + 1).tolist()
    blue_df = pd.DataFrame(0, index=range(len(history)), columns=range(1,13))
    for i, h in enumerate(history): blue_df.loc[i, h['blue']] = 1
    blue_prob = np.dot(weights, blue_df.values[::-1]) + np.random.normal(0, 0.05, 12)
    blue_res = (np.argsort(blue_prob)[-2:] + 1).tolist()
    p_dict = {str(i+1): round(float(prob[i]), 2) for i in range(35)}
    return sorted(red_res), sorted(blue_res), round(float(np.std(prob)*18),2), p_dict, "分析完成"

def fetch_source_a():
    try:
        res = requests.get("https://datachart.500.com/dlt/history/newinc/history.php", timeout=5)
        res.encoding = 'utf-8'
        rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
        return [{"period": t[0], "red": sorted(list(map(int, t[2:7]))), "blue": sorted(list(map(int, t[7:9])))} 
                for t in [re.findall(r'<td.*?>(.*?)</td>', r) for r in rows[:30]]]
    except: return None

def fetch_source_b():
    try:
        res = requests.get("https://kj.sina.com.cn/dlt/", timeout=5)
        res.encoding = 'utf-8'
        ps = re.findall(r'<td class="td_issue">(.*?)</td>', res.text)
        bs = re.findall(r'<td class="td_ball">.*?<span class="ball_red">(.*?)</span>.*?<span class="ball_blue">(.*?)</span>', res.text, re.S)
        return [{"period": ps[i].strip(), "red": sorted(list(map(int, bs[i][0].replace('</span><span class="ball_red">', ' ').split()))),
                 "blue": sorted(list(map(int, bs[i][1].replace('</span><span class="ball_blue">', ' ').split())))} for i in range(min(10, len(ps)))]
    except: return None

def sync_system():
    sa, sb = fetch_source_a(), fetch_source_b()
    final_h = sa or sb or []
    if not final_h: return
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    for h in final_h:
        row = c.execute("SELECT red, blue FROM predict WHERE period=?", (h['period'],)).fetchone()
        if row and not c.execute("SELECT 1 FROM predict WHERE period=? AND hit!='/'",(h['period'],)).fetchone():
            hr, hb = len(set(json.loads(row[0]))&set(h['red'])), len(set(json.loads(row[1]))&set(h['blue']))
            c.execute("UPDATE predict SET hit=? WHERE period=?", (f"{hr}+{hb}", h['period']))
    next_p = str(int(final_h[0]['period']) + 1)
    if not c.execute("SELECT 1 FROM predict WHERE period=?", (next_p,)).fetchone():
        r, b, conf, pdict, exp = autonomous_engine(final_h)
        c.execute("INSERT INTO predict VALUES (?,?,?,?,?,?)", (next_p, json.dumps(r), json.dumps(b), "/", conf, json.dumps({"prob":pdict,"exp":exp})))
    conn.commit()
    conn.close()

@app.route("/")
def index():
    init_db()
    sync_system()
    conn = sqlite3.connect("ai.db")
    rows = conn.execute("SELECT period, red, blue, hit, confidence, prob_data FROM predict ORDER BY period DESC LIMIT 15").fetchall()
    conn.close()
    records, l_list, v_list = [], [], []
    for r in rows:
        pj = json.loads(r[5]) if r[5] else {}
        records.append({"period":str(r[0]),"red":json.loads(r[1]),"blue":json.loads(r[2]),"hit":str(r[3]),"conf":r[4],"exp":pj.get("exp","")})
        if str(r[3]) != "/":
            l_list.append(str(r[0]))
            v_list.append(sum(map(int, str(r[3]).split('+'))))
    p_data = json.loads(rows[0][5]).get("prob", {}) if rows else {}
    top_num = sorted(p_data.items(), key=lambda x:x[1], reverse=True)[:10]
    # 彻底改名，避开 .values
    chart_payload = {"lab_list": l_list[::-1], "val_list": v_list[::-1]}
    return render_template("index.html", records=records, top_numbers=top_num, chart_data=chart_payload, logged_in=('user' in session))

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

@app.route("/rank")
def rank():
    conn = sqlite3.connect("ai.db")
    users = conn.execute("SELECT username FROM users").fetchall()
    rows = [[u[0], random.uniform(0.5, 3.8), random.randint(1, 15)] for u in users]
    conn.close()
    return render_template("rank.html", rows=rows, logged_in=('user' in session))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
