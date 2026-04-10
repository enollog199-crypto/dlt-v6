import warnings
warnings.filterwarnings("ignore", category=UserWarning)
from flask import Flask, render_template, request, jsonify
import time, datetime, os, random, sqlite3, json, re

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_pro_v24_0"
DB_PATH = 'dextro_data.db'

# 初始种子数据
SEED_DATA = [
    {"p": "26037", "r": [7, 12, 13, 28, 32], "b": [6, 8]},
    {"p": "26036", "r": [4, 7, 16, 26, 32], "b": [5, 8]},
    {"p": "25068", "r": [1, 4, 17, 20, 22], "b": [4, 10]}
]

def get_db():
    # 优化连接：增加 timeout 防止 Render 环境锁表，支持多线程安全
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS system_config (id INTEGER PRIMARY KEY, data_json TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS users (uid TEXT PRIMARY KEY, balance REAL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS bets (id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, 
                   target_p TEXT, red_nums TEXT, blue_nums TEXT, amount REAL, status TEXT, win_amt REAL)''')
    return conn

def load_sys_data():
    conn = get_db()
    row = conn.execute("SELECT data_json FROM system_config WHERE id=1").fetchone()
    conn.close()
    return json.loads(row[0]) if row else {"history": SEED_DATA}

def save_sys_data(data):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO system_config (id, data_json) VALUES (1, ?)", (json.dumps(data),))
    conn.commit()
    conn.close()

# --- 🎯 优化版：自动兑奖引擎 ---
def auto_settle_prizes(latest_p, latest_r, latest_b):
    conn = get_db()
    # 1. 批量查询待开奖注单 (限额 100 条防止卡死)
    pending_bets = conn.execute(
        "SELECT id, uid, red_nums, blue_nums, amount FROM bets WHERE target_p=? AND status='pending' LIMIT 100",
        (latest_p,)
    ).fetchall()
    
    for bid, uid, r_str, b_str, amt in pending_bets:
        r_list = json.loads(r_str)
        b_list = json.loads(b_str)
        
        hit_r = len(set(r_list) & set(latest_r))
        hit_b = len(set(b_list) & set(latest_b))
        
        # 模拟奖励逻辑（可根据需要调整）
        win_amt = 0
        if hit_r == 5 and hit_b == 2: win_amt = amt * 5000  # 虚拟大奖
        elif hit_r == 5: win_amt = amt * 100
        elif hit_r == 4: win_amt = amt * 10
        elif hit_r + hit_b >= 3: win_amt = amt * 2
        
        status = "win" if win_amt > 0 else "lose"
        # 2. 更新注单状态
        conn.execute("UPDATE bets SET status=?, win_amt=? WHERE id=?", (status, win_amt, bid))
        # 3. 增加余额
        if win_amt > 0:
            conn.execute("UPDATE users SET balance = balance + ? WHERE uid = ?", (win_amt, uid))
    
    conn.commit()
    conn.close()

@app.route("/")
def index():
    sys_data = load_sys_data()
    # 动态矩阵显示 20 期
    matrix_display = sorted(sys_data["history"], key=lambda x: int(x['p']))[-20:]
    return render_template("index.html", history=matrix_display, last=sys_data["history"][0])

@app.route("/get_user", methods=["POST"])
def get_user():
    uid = request.json.get("uid")
    conn = get_db()
    row = conn.execute("SELECT balance FROM users WHERE uid=?", (uid,)).fetchone()
    if not row:
        conn.execute("INSERT INTO users (uid, balance) VALUES (?, ?)", (uid, 1000.0))
        conn.commit()
        balance = 1000.0
    else:
        balance = row[0]
    conn.close()
    return jsonify({"balance": balance})

@app.route("/my_bets", methods=["POST"])
def my_bets():
    uid = request.json.get("uid")
    conn = get_db()
    # 查询最近 10 条注单
    rows = conn.execute(
        "SELECT target_p, red_nums, blue_nums, amount, status, win_amt FROM bets WHERE uid=? ORDER BY id DESC LIMIT 10",
        (uid,)
    ).fetchall()
    conn.close()
    return jsonify([{"p": r[0], "r": json.loads(r[1]), "b": json.loads(r[2]), "amt": r[3], "status": r[4], "win": r[5]} for r in rows])

@app.route("/submit_bet", methods=["POST"])
def submit_bet():
    d = request.json
    uid = d.get('uid')
    try:
        amt = float(d.get('amount', 0))
        if amt <= 0 or amt > 500: return jsonify({"success": False, "msg": "虚拟限额 1-500"})
    except: return jsonify({"success": False, "msg": "输入非法"})

    conn = get_db()
    row = conn.execute("SELECT balance FROM users WHERE uid=?", (uid,)).fetchone()
    user_bal = row[0] if row else 1000.0
    
    if user_bal < amt: return jsonify({"success": False, "msg": "虚拟余额不足"})
    
    conn.execute("UPDATE users SET balance = balance - ? WHERE uid=?", (amt, uid))
    conn.execute("INSERT INTO bets (uid, target_p, red_nums, blue_nums, amount, status, win_amt) VALUES (?,?,?,?,?,?,?)",
                 (uid, d['target_p'], json.dumps(d['red']), json.dumps(d['blue']), amt, "pending", 0))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "new_bal": user_bal - amt})

@app.route("/feed", methods=["POST"])
def feed_data():
    if request.form.get("pw") != "8888": return "暗号错误", 403
    content = request.form.get("content", "").strip()
    if len(content) > 6000: return "数据过大", 400
    
    sys_data = load_sys_data()
    history = sys_data["history"]
    existing_ps = set(h['p'] for h in history)
    
    added = 0
    for line in content.split('\n'):
        nums = re.findall(r'\d+', line)
        if len(nums) >= 8:
            p_num = nums[0]
            if p_num not in existing_ps:
                new_r = sorted([int(x) for x in nums[-7:-2]])
                new_b = sorted([int(x) for x in nums[-2:]])
                history.append({"p": p_num, "r": new_r, "b": new_b})
                auto_settle_prizes(p_num, new_r, new_b)
                added += 1
    
    history = sorted(history, key=lambda x: int(x['p']), reverse=True)
    save_sys_data({"history": history})
    return f"同步成功！新增 {added} 期。", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
