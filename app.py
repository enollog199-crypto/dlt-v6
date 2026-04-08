from flask import Flask, render_template, request, redirect, url_for, session, flash
import requests, re, random, sqlite3, json, os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_v9_secret_key"

PRIZE_MAP = {"5+2":10000000,"5+1":800000,"5+0":10000,"4+2":3000,"4+1":300,"4+0":100,"3+2":200,"3+1":15,"3+0":5,"2+2":15,"1+2":5,"2+1":5,"0+2":5}

def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    # 用户表：增加金币(credits)和最后签到日期(last_checkin)
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, credits REAL DEFAULT 100.0, last_checkin TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS predict 
                 (period TEXT PRIMARY KEY, draw_date TEXT, red TEXT, blue TEXT, 
                  hit_red INT, hit_blue INT, cost REAL, winnings REAL, source_type TEXT)''')
    c.execute('CREATE TABLE IF NOT EXISTS weights (num INT PRIMARY KEY, score REAL)')
    for i in range(1, 48): c.execute("INSERT OR IGNORE INTO weights VALUES (?,?)", (i, 10.0))
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        try:
            conn = sqlite3.connect("ai.db")
            conn.execute("INSERT INTO users (username, password, credits) VALUES (?,?,?)", (u, generate_password_hash(p), 100.0))
            conn.commit()
            return redirect(url_for('login'))
        except: return "用户名已存在"
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        user = sqlite3.connect("ai.db").execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
        if user and check_password_hash(user[2], p):
            session['user'] = u
            return redirect(url_for('index'))
        return "账号或密码错误"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# --- 新增功能：修改密码 ---
@app.route("/change_password", methods=["POST"])
@login_required
def change_password():
    new_p = request.form.get("new_password")
    hashed = generate_password_hash(new_p)
    conn = sqlite3.connect("ai.db")
    conn.execute("UPDATE users SET password=? WHERE username=?", (hashed, session['user']))
    conn.commit()
    return redirect(url_for('index'))

# --- 新增功能：每日签到 ---
@app.route("/checkin", methods=["POST"])
@login_required
def checkin():
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect("ai.db")
    user = conn.execute("SELECT last_checkin FROM users WHERE username=?", (session['user'],)).fetchone()
    if user[0] != today:
        reward = random.randint(10, 50)
        conn.execute("UPDATE users SET credits = credits + ?, last_checkin = ? WHERE username=?", (reward, today, session['user']))
        conn.commit()
    return redirect(url_for('index'))

@app.route("/")
@login_required
def index():
    init_db()
    conn = sqlite3.connect("ai.db")
    
    # 获取用户信息
    user_info = conn.execute("SELECT credits, last_checkin FROM users WHERE username=?", (session['user'],)).fetchone()
    today = datetime.now().strftime('%Y-%m-%d')
    can_checkin = user_info[1] != today

    # 数据抓取与同步 (逻辑维持V8.0)
    try:
        res = requests.get("https://datachart.500.com/dlt/history/newinc/history.php", timeout=5)
        res.encoding = 'utf-8'
        rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
        history = [{"period": t[0], "date": t[1], "red": [int(x) for x in t[2:7]], "blue": [int(x) for x in t[7:9]]} 
                   for t in [re.findall(r'<td.*?>(.*?)</td>', r) for r in rows[:15]]]
        
        for h in history:
            row = conn.execute("SELECT red, blue, hit_red FROM predict WHERE period=?", (h['period'],)).fetchone()
            if row and row[2] == -1:
                hr = len(set(json.loads(row[0])) & set(h['red']))
                hb = len(set(json.loads(row[1])) & set(h['blue']))
                win = PRIZE_MAP.get(f"{hr}+{hb}", 0)
                conn.execute("UPDATE predict SET draw_date=?, hit_red=?, hit_blue=?, winnings=? WHERE period=?",
                             (h['date'], hr, hb, win, h['period']))
        conn.commit()

        # 下期预测生成
        next_p = str(int(history[0]['period']) + 1)
        if not conn.execute("SELECT 1 FROM predict WHERE period=?", (next_p,)).fetchone():
            src = random.choice(["神经网络流", "热号频率流", "冷态补漏流"])
            weights = {r[0]:r[1] for r in conn.execute("SELECT * FROM weights").fetchall()}
            def pick(s,e,c,wd,off=0):
                p = []
                for n in range(s,e+1): p.extend([n]*int(wd.get(n+off,10)*10))
                return sorted(random.sample(p,c))
            red, blue = pick(1,35,5,weights), pick(1,12,2,weights,35)
            conn.execute("INSERT INTO predict VALUES (?,?,?,?,?,?,?,?,?)", (next_p,"待开奖",str(red),str(blue),-1,-1,2.0,0.0,src))
            conn.commit()
    except: pass

    # 获取数据展示
    recs
