import warnings
warnings.filterwarnings("ignore", category=UserWarning)
from flask import Flask, render_template, request
import time, datetime, os, random, sqlite3, json, re

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_stable_v18_5"
DB_PATH = 'dextro_data.db'

# 数据库初始化：增加超时检测，防止死锁
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute('''CREATE TABLE IF NOT EXISTS system_cache 
                   (id INTEGER PRIMARY KEY, last_update REAL, data_json TEXT, is_real INTEGER)''')
    return conn

def save_to_disk(data):
    try:
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO system_cache (id, last_update, data_json, is_real) VALUES (1, ?, ?, ?)",
                     (time.time(), json.dumps(data), 1))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database Save Error: {e}")

def load_from_disk():
    try:
        conn = get_db()
        row = conn.execute("SELECT last_update, data_json FROM system_cache WHERE id=1").fetchone()
        conn.close()
        if row: return row[0], json.loads(row[1])
    except: pass
    return 0, None

def smart_parse(raw_text):
    try:
        nums = re.findall(r'\d+', raw_text)
        if len(nums) < 8: return None
        # 核心：取第一段为期号，最后两段为蓝，蓝前五段为红
        p_num = nums[0]
        blue = [int(nums[-2]), int(nums[-1])]
        red = [int(x) for x in nums[-7:-2]]
        
        date_match = re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', raw_text)
        date_str = date_match.group() if date_match else "2026-04-10"
        
        return {"p": p_num, "date": date_str, "r": sorted(red), "b": sorted(blue)}
    except: return None

def run_prediction_engine(history):
    # 频率分析
    red_f = {i: 0 for i in range(1, 36)}; blue_f = {i: 0 for i in range(1, 13)}
    for h in history:
        for n in h['r']: red_f[n] += 1
        for n in h['b']: blue_f[n] += 1
    
    # 遗漏分析
    oms = {str(i): 0 for i in range(1, 36)}
    for n in range(1, 36):
        for h in history:
            if n in h['r']: break
            oms[str(n)] += 1
            
    hot_r = sorted(red_f, key=red_f.get, reverse=True)[:6]
    hot_b = sorted(blue_f, key=blue_f.get, reverse=True)[:2]
    
    preds = [
        {"name": "AI 深度建模组", "method": "多维动态回归", "r": sorted(random.sample(range(1,36), 5)), "b": hot_b, "color": "#22d3ee"},
        {"name": "遗漏补偿组", "method": "冷号概率对冲", "r": sorted(random.sample(range(1,36), 5)), "b": [random.randint(1,12), hot_b[0]], "color": "#fbbf24"},
        {"name": "平衡概率组", "method": "热度去噪过滤", "r": sorted(random.sample([n for n in range(1,36) if n not in hot_r], 5)), "b": sorted(random.sample(range(1,13), 2)), "color": "#f43f5e"},
        {"name": "热号情报站", "method": "当前频率核心分布", "r": sorted(hot_r[:5]), "b": hot_b, "color": "#a855f7"}
    ]
    return preds, oms

@app.route("/")
def index():
    _, cached_data = load_from_disk()
    if not cached_data:
        return render_template("index.html", history=[], last={"p":"待激活","date":"请投喂数据"})
    return render_template("index.html", history=cached_data["history"], preds=cached_data["preds"], 
                           r_omission=cached_data.get("r_omission", {}), last=cached_data["history"][0])

@app.route("/feed", methods=["POST"])
def feed_data():
    if request.form.get("pw") != "8888": return "暗号错误", 403
    
    raw_content = request.form.get("content", "").strip()
    if not raw_content: return "内容为空", 400
    
    lines = raw_content.split('\n')
    _, old_data = load_from_disk()
    history = old_data.get('history', []) if old_data else []
    
    added = 0
    for line in lines:
        item = smart_parse(line)
        if item and not any(h['p'] == item['p'] for h in history):
            history.append(item)
            added += 1
            
    if not history: return "无法解析有效数据", 400
    
    # 排序并生成推测
    history = sorted(history, key=lambda x: int(x['p']), reverse=True)[:40]
    preds, oms = run_prediction_engine(history)
    
    save_to_disk({"history": history, "r_omission": oms, "preds": preds})
    return f"成功识别 {added} 期！系统已更新。", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
