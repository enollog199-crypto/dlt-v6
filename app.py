from flask import Flask, render_template, request, redirect, url_for, session
import requests, re, random, sqlite3, json, os, datetime
import numpy as np
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ultra_secure_v9"

def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT PRIMARY KEY, red TEXT, blue TEXT, hit TEXT, confidence REAL, prob_data TEXT)''')
    conn.commit()
    conn.close()

def fetch_realtime_crowd_hot():
    """模拟抓取当前全网最热门号码（实时避热事实数据）"""
    hot_red = [1, 5, 8, 12, 18, 22, 29, 33] 
    hot_blue = [6, 12]
    return {"red": hot_red, "blue": hot_blue, "update_time": datetime.datetime.now().strftime("%H:%M:%S")}

def autonomous_engine(history):
    if len(history) < 5:
        return [1,2,3,4,5], [1,2], 50.0, {str(i):0.1 for i in range(1,36)}, "初始化"
    df = pd.DataFrame(0, index=range(len(history)), columns=range(1,36))
    for i, h in enumerate(history): df.loc[i, h['red']] = 1
    data, weights = df.values[::-1], np.exp(np.linspace(-1.0, 1.0, len(df)))
    prob = np.dot(weights, data) + np.random.normal(0, 0.04, 35)
    red_res = (np.argsort(prob)[-5:] + 1).tolist()
    blue_df = pd.DataFrame(0, index=range(len(history)), columns=range(1,13))
    for i, h in enumerate(history): blue_df.loc[i, h['blue']] = 1
    blue_prob = np.dot(weights, blue_df.values[::-1]) + np.random.normal(0, 0.04, 12)
    blue_res = (np.argsort(blue_prob)[-2:] + 1).tolist()
    p_dict = {str(i+1): round(float(prob[i]), 2) for i in range(35)}
    return sorted(red_res), sorted(blue_res), round(float(np.std(prob)*20),2), p_dict, "完成"

def sync_system():
    try:
        res = requests.get("https://datachart.500.com/dlt/history/newinc/history.php", timeout=5)
        res.encoding = 'utf-8'
        rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
        sa = [{"period": t[0], "red": sorted(list(map(int, t[2:7]))), "blue": sorted(list(map(int, t[7:9])))} 
                for t in [re.findall(r'<td.*?>(.*?)</td>', r) for r in rows[:30]]]
    except: return
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    for h in sa:
        row = c.execute("SELECT red, blue FROM predict WHERE period=?", (h['period'],)).fetchone()
        if row and not c.execute("SELECT 1 FROM predict WHERE period=? AND hit!='/'",(h['period'],)).fetchone():
            hr, hb = len(set(json.loads(row[0]))&set(h['red'])), len(set(json.loads(row[1]))&set(h['blue']))
            c.execute("UPDATE predict SET hit=? WHERE period=?", (f"{hr}+{hb}", h['period']))
    next_p = str(int(sa[0]['period']) + 1)
    if not c.execute("SELECT 1 FROM predict WHERE period=?", (next_p,)).fetchone():
        r, b, conf, pdict, exp = autonomous_engine(sa)
        c.execute("INSERT INTO predict VALUES (?,?,?,?,?,?)", (next_p, json.dumps(r), json.dumps(b), "/", conf, json.dumps({"prob":pdict,"exp":exp})))
    conn.commit(); conn.close()

@app.route("/")
def index():
    init_db(); sync_system()
    conn = sqlite3.connect("ai.db")
    rows = conn.execute("SELECT period, red, blue, hit, confidence, prob_data FROM predict ORDER BY period DESC LIMIT 15").fetchall()
    conn.close()
    records, l_list, v_list = [], [], []
    if not rows:
        records.append({"period": "N/A", "red": [0]*5, "blue": [0]*2, "hit": "/", "conf": 0, "exp": "..."})
        p_data = {}
    else:
        for r in rows:
            pj = json.loads(r[5]) if r[5] else {}
            records.append({"period":str(r[0]),"red":json.loads(r[1]),"blue":json.loads(r[2]),"hit":str(r[3]),"conf":r[4],"exp":pj.get("exp","")})
            if str(r[3]) != "/":
                l_list.append(str(r[0])); v_list.append(sum(map(int, str(r[3]).split('+'))))
        p_data = json.loads(rows[0][5]).get("prob", {})
    # 实时博弈引擎
    crowd = fetch_realtime_crowd_hot()
    core_res = {"red": records[0]["red"], "blue": records[0]["blue"]}
    game_prob = {k: float(v) for k, v in p_data.items()}
    for hn in crowd["red"]:
        if str(hn) in game_prob: game_prob[str(hn)] *= 0.1 # 对热门号降权打击
    anti_red = sorted([int(k) for k in sorted(game_prob.items(), key=lambda x:x[1], reverse=True)[:5]])
    anti_blue = [b for b in [1,2,3,4,5,7,8,9,10,11] if b not in crowd["blue"]][:2]
    return render_template("index.html", records=records, core=core_res, anti={"red":anti_red, "blue":sorted(anti_blue)}, 
                           crowd=crowd, top_numbers=sorted(p_data.items(), key=lambda x:x[1], reverse=True)[:10],
                           chart_data={"lab": l_list[::-1], "val": v_list[::-1]}, logged_in=('user' in session))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        conn = sqlite3.connect("ai.db")
        user = conn.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
        conn.close()
        if user and check_password_hash(user[2], p):
            session['user'] = u; return redirect(url_for('index'))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('user', None); return redirect(url_for('index'))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
