import warnings
warnings.filterwarnings("ignore", category=UserWarning)

from flask import Flask, render_template, request, jsonify
import time, os, random, sqlite3, json

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_v28_final"
DB_PATH = 'dextro_data.db'

# ======================
# 数据库
# ======================
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS sys_status (id INTEGER PRIMARY KEY, data_json TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS users (uid TEXT PRIMARY KEY, balance REAL)')
    conn.execute('''CREATE TABLE IF NOT EXISTS bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uid TEXT, target_p TEXT,
        red_nums TEXT, blue_nums TEXT,
        amount REAL, status TEXT, win_amt REAL)''')
    return conn

# ======================
# 数据读写
# ======================
def load_data():
    conn = get_db()
    row = conn.execute("SELECT data_json FROM sys_status WHERE id=1").fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return {
        "history": [{"p":"26037","r":[7,12,13,28,32],"b":[6,8]}],
        "hot_cache": [],
        "last_hot_time": 0
    }

def save_data(d):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO sys_status VALUES (1, ?)", (json.dumps(d),))
    conn.commit()
    conn.close()

# ======================
# 时间控制
# ======================
def is_locked():
    h = time.localtime().tm_hour
    return 15 <= h < 22

# ======================
# 模拟第三方
# ======================
def fetch_api():
    return {"p":"26038","r":[3,11,15,23,30],"b":[4,9]}

# ======================
# 自动抓取（核心）
# ======================
def auto_fetch():
    if is_locked(): return

    official = fetch_api()
    data = load_data()

    if official['p'] != data['history'][0]['p']:
        data['history'].insert(0, official)
        save_data(data)
        settle(official)

# ======================
# AI预测（修复版）
# ======================
def ai(history):
    reds = [n for h in history[:50] for n in h['r']]
    hot = sorted(set(reds), key=reds.count, reverse=True)
    cold = list(set(range(1,36)) - set(hot[:15]))

    def pick(pool):
        r = sorted(random.sample(pool, 3) + random.sample(range(1,36),2))
        b = sorted(random.sample(range(1,13),2))
        return r,b

    data = load_data()

    # 修复热号缓存
    if not data['hot_cache']:
        data['hot_cache'] = [
            sorted(random.sample(range(1,36),5)),
            sorted(random.sample(range(1,13),2))
        ]

    if time.time() - data['last_hot_time'] > 3600:
        data['hot_cache'] = [
            sorted(random.sample(range(1,36),5)),
            sorted(random.sample(range(1,13),2))
        ]
        data['last_hot_time'] = time.time()
        save_data(data)

    r1,b1 = pick(hot[:12])
    r2,b2 = pick(cold[:15])
    r3,b3 = pick(hot[:15])

    return [
        {"name":"🔥热号","desc":"高频策略","r":r1,"b":b1},
        {"name":"❄️冷号","desc":"低频反弹","r":r2,"b":b2},
        {"name":"⚖️均衡","desc":"冷热混合","r":r3,"b":b3},
        {"name":"🌐热榜","desc":"每小时更新","r":data['hot_cache'][0],"b":data['hot_cache'][1]}
    ]

# ======================
# 结算
# ======================
def settle(res):
    conn = get_db()
    rows = conn.execute(
        "SELECT id,uid,red_nums,blue_nums,amount FROM bets WHERE target_p=? AND status='pending'",
        (res['p'],)
    ).fetchall()

    for bid,uid,r_s,b_s,amt in rows:
        r = json.loads(r_s)
        b = json.loads(b_s)

        hr = len(set(r)&set(res['r']))
        hb = len(set(b)&set(res['b']))

        win = 0
        if hr==5 and hb==2: win = amt*5000
        elif hr==5: win = amt*200
        elif hr>=3: win = amt*5

        status = "win" if win>0 else "lose"

        conn.execute("UPDATE bets SET status=?, win_amt=? WHERE id=?", (status,win,bid))
        if win>0:
            conn.execute("UPDATE users SET balance = balance + ? WHERE uid=?", (win,uid))

    conn.commit()
    conn.close()

# ======================
# 路由
# ======================
@app.route("/")
def index():
    auto_fetch()
    d = load_data()
    return render_template("index.html",
        history=d['history'][:20],
        last=d['history'][0],
        preds=ai(d['history']),
        locked=is_locked()
    )

# 投喂
@app.route("/admin/feed", methods=["POST"])
def feed():
    if is_locked():
        return jsonify({"success":False,"msg":"当前时间禁止更新"})

    req = request.json
    p = req['p']
    r = sorted(req['r'])
    b = sorted(req['b'])

    off = fetch_api()

    if p != off['p']:
        return jsonify({"success":False,"msg":"期号不一致"})
    if r != off['r'] or b != off['b']:
        return jsonify({"success":False,"msg":"数据不一致"})

    d = load_data()
    if any(x['p']==p for x in d['history']):
        return jsonify({"success":True,"msg":"已存在"})

    d['history'].insert(0, {"p":p,"r":r,"b":b})
    save_data(d)
    settle({"p":p,"r":r,"b":b})

    return jsonify({"success":True,"msg":"成功"})

# 登录
@app.route("/api/auth", methods=["POST"])
def auth():
    uid = request.json['uid']
    conn = get_db()
    u = conn.execute("SELECT balance FROM users WHERE uid=?", (uid,)).fetchone()

    if not u:
        conn.execute("INSERT INTO users VALUES (?,?)", (uid,1000))
        conn.commit()
        bal=1000
    else:
        bal=u[0]

    conn.close()
    return jsonify({"success":True,"uid":uid,"balance":bal})

# 投注
@app.route("/submit_bet", methods=["POST"])
def bet():
    if is_locked():
        return jsonify({"success":False,"msg":"封盘中"})

    d = request.json
    conn = get_db()

    u = conn.execute("SELECT balance FROM users WHERE uid=?", (d['uid'],)).fetchone()
    if not u or u[0] < d['amount']:
        return jsonify({"success":False,"msg":"余额不足"})

    conn.execute("UPDATE users SET balance=balance-? WHERE uid=?", (d['amount'],d['uid']))
    conn.execute("INSERT INTO bets VALUES (NULL,?,?,?,?,?,?,?)",
        (d['uid'],d['target_p'],json.dumps(d['red']),json.dumps(d['blue']),d['amount'],"pending",0)
    )

    conn.commit()
    conn.close()
    return jsonify({"success":True})

# 查询记录
@app.route("/my_bets", methods=["POST"])
def my_bets():
    uid = request.json['uid']
    conn = get_db()
    rows = conn.execute(
        "SELECT target_p,red_nums,blue_nums,amount,status,win_amt FROM bets WHERE uid=? ORDER BY id DESC LIMIT 10",
        (uid,)
    ).fetchall()
    conn.close()

    return jsonify([
        {"p":r[0],"r":json.loads(r[1]),"b":json.loads(r[2]),"amt":r[3],"status":r[4],"win":r[5]}
        for r in rows
    ])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
