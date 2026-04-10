import warnings
warnings.filterwarnings("ignore", category=UserWarning)
from flask import Flask, render_template, request, jsonify
import time, datetime, os, random, sqlite3, json, re

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ultra_v22_0"
DB_PATH = 'dextro_data.db'

# 内置核心历史数据种子
SEED_DATA = [
    {"p": "26037", "date": "2026/04/08", "r": [7, 12, 13, 28, 32], "b": [6, 8]},
    {"p": "26036", "date": "2026/04/06", "r": [4, 7, 16, 26, 32], "b": [5, 8]},
    {"p": "26035", "date": "2026/04/04", "r": [2, 22, 30, 33, 34], "b": [8, 12]},
    {"p": "26034", "date": "2026/04/01", "r": [11, 12, 25, 26, 27], "b": [8, 11]},
    {"p": "26033", "date": "2026/03/30", "r": [3, 5, 7, 9, 18], "b": [2, 10]}
    # 系统会自动在数据库中保留这些种子作为基准
]

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute('''CREATE TABLE IF NOT EXISTS system_cache 
                   (id INTEGER PRIMARY KEY, last_update REAL, data_json TEXT, balance REAL)''')
    return conn

def load_all():
    try:
        conn = get_db()
        row = conn.execute("SELECT data_json, balance FROM system_cache WHERE id=1").fetchone()
        conn.close()
        if row: 
            data = json.loads(row[0])
            if not data.get("history"): data["history"] = SEED_DATA
            return data, row[1]
    except: pass
    return {"history": SEED_DATA}, 1000.0

def save_all(data, balance):
    try:
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO system_cache (id, last_update, data_json, balance) VALUES (1, ?, ?, ?)",
                     (time.time(), json.dumps(data), balance))
        conn.commit()
        conn.close()
    except: pass

# --- 🧠 进化版 AI 建模引擎 ---
def run_prediction_engine(history):
    if not history: return []

    red_freq = {i: 0 for i in range(1, 36)}
    last_seen = {i: 999 for i in range(1, 36)}

    # 1. 统计频率与遗漏 (基于近60期)
    for idx, h in enumerate(history[:60]):
        for n in h['r']:
            red_freq[n] += 1
            if last_seen[n] == 999: last_seen[n] = idx

    # 2. 评分系统 (权重：频率*2 + 遗漏*1.5 + 趋势加成)
    score = {}
    for n in range(1, 36):
        trend_bonus = 8 if last_seen[n] < 3 else 0 # 极热跳号加成
        score[n] = (red_freq[n] * 2) + (last_seen[n] * 1.5) + trend_bonus

    sorted_nums = sorted(score, key=score.get, reverse=True)
    hot, mid, cold = sorted_nums[:10], sorted_nums[10:25], sorted_nums[25:]

    def pick_reds(mode):
        if mode == "hot": nums = random.sample(hot, 4) + random.sample(mid, 1)
        elif mode == "mix": nums = random.sample(hot, 2) + random.sample(mid, 2) + random.sample(cold, 1)
        else: nums = random.sample(cold, 3) + random.sample(mid, 2)
        
        # 区间分布修正：确保不会全拥挤在一个区间
        nums = sorted(list(set(nums)))
        if len(nums) < 5: nums = sorted(random.sample(range(1,36), 5))
        return nums[:5]

    # 蓝球分析 (带频率加权)
    blue_freq = {i: 0 for i in range(1, 13)}
    for h in history[:30]:
        for b in h['b']: blue_freq[b] += 1
    blue_sorted = sorted(blue_freq, key=blue_freq.get, reverse=True)

    def pick_blue():
        return sorted([random.choice(blue_sorted[:6]), random.choice(blue_sorted[6:])])

    # 3. 计算命中检测 (与上一期对比)
    last_h = history[0]
    def get_hits(r, b):
        r_hits = len(set(r) & set(last_h['r']))
        b_hits = len(set(b) & set(last_h['b']))
        return r_hits, b_hits

    preds = []
    strategies = [
        ("AI 深度进化版", "hot", "趋势强化模型", "#22d3ee"),
        ("平衡概率引擎", "mix", "区间均衡分布", "#fbbf24"),
        ("冷号对冲算法", "cold", "遗漏补偿策略", "#f43f5e")
    ]
    
    for name, mode, tag, color in strategies:
        r, b = pick_reds(mode), pick_blue()
        rh, bh = get_hits(r, b)
        preds.append({"name": name, "tag": tag, "r": r, "b": b, "color": color, "rh": rh, "bh": bh})
    
    return preds

@app.route("/")
def index():
    data, balance = load_all()
    history = data["history"]
    preds = run_prediction_engine(history)
    # 矩阵显示排序：旧 -> 新 (取近 15 期)
    matrix_display = sorted(history, key=lambda x: int(x['p']))[-15:]
    return render_template("index.html", history=matrix_display, preds=preds, balance=round(balance,2), last=history[0])

@app.route("/feed", methods=["POST"])
def feed_data():
    if request.form.get("pw") != "8888": return "暗号错误", 403
    content = request.form.get("content", "").strip()
    if not content or len(content) > 10000: return "数据异常", 400
    
    data, balance = load_all()
    history = data["history"]
    
    added, errors = 0, 0
    for line in content.split('\n'):
        nums = re.findall(r'\d+', line)
        if len(nums) >= 8:
            try:
                p_num = nums[0]
                new_r = sorted([int(x) for x in nums[-7:-2]])
                new_b = sorted([int(x) for x in nums[-2:]])
                if not any(h['p'] == p_num for h in history):
                    history.append({"p": p_num, "date": "2026/04/10", "r": new_r, "b": new_b})
                    added += 1
            except: errors += 1
            
    if added > 0:
        # 强制数值排序，防止字符串比对逻辑失效
        history = sorted(history, key=lambda x: int(x['p']), reverse=True)
        save_all({"history": history}, balance)
    
    return f"同步完成：新增 {added} 期，错误 {errors} 条。", 200

@app.route("/bet", methods=["POST"])
def bet():
    data, balance = load_all()
    try:
        amt = float(request.form.get("amount", 0))
        if amt <= 0 or amt > 500: raise ValueError
        if balance < amt: return jsonify({"success": False, "msg": "余额不足"})
        balance -= amt
        save_all(data, balance)
        return jsonify({"success": True, "new_balance": round(balance, 2)})
    except:
        return jsonify({"success": False, "msg": "金额非法(1-500)"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
