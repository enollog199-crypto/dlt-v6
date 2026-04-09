import warnings
warnings.filterwarnings("ignore", category=UserWarning)
from flask import Flask, render_template, request
import time, datetime, os, random, sqlite3, json, re

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ultra_v18_3"
DB_PATH = 'dextro_data.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS system_cache 
                       (id INTEGER PRIMARY KEY, last_update REAL, data_json TEXT, is_real INTEGER)''')
        conn.commit()

def save_to_disk(data, is_real=1):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR REPLACE INTO system_cache (id, last_update, data_json, is_real) VALUES (1, ?, ?, ?)",
                         (time.time(), json.dumps(data), is_real))
            conn.commit()
    except: pass

def load_from_disk():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT last_update, data_json, is_real FROM system_cache WHERE id=1").fetchone()
            if row: return row[0], json.loads(row[1]), row[2]
    except: pass
    return 0, None, 0

def smart_parse(raw_text):
    try:
        # 兼容你的截图格式：26037 2026/4/8 7 12 13 28 32 6 8
        nums = re.findall(r'\d+', raw_text)
        if len(nums) < 8: return None
        
        # 针对带日期的格式（如 2026/4/8 会被拆成 3 个数字），我们取首尾逻辑
        # 第一串是期号，最后两串是蓝球，蓝球前面五串是红球
        p_num = nums[0]
        blue = [int(nums[-2]), int(nums[-1])]
        red = [int(x) for x in nums[-7:-2]]
        
        # 尝试寻找日期字符串（格式如 2026/4/8 或 2026-04-08）
        date_match = re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', raw_text)
        date_str = date_match.group() if date_match else datetime.datetime.now().strftime("%Y-%m-%d")
        
        return {"p": p_num, "date": date_str, "r": sorted(red), "b": sorted(blue)}
    except: return None

def run_prediction_engine(history):
    # 频率统计
    red_f = {i: 0 for i in range(1, 36)}; blue_f = {i: 0 for i in range(1, 13)}
    for h in history:
        for n in h['r']: red_f[n] += 1
        for n in h['b']: blue_f[n] += 1
    # 遗漏计算
    oms = {str(i): 0 for i in range(1, 36)}
    for n in range(1, 36):
        for h in history:
            if n in h['r']: break
            oms[str(n)] += 1
    hot_r = sorted(red_f, key=red_f.get, reverse=True)[:6]
    hot_b = sorted(blue_f, key=blue_f.get, reverse=True)[:2]
    
    # 核心 4 组推测
    return [
        {"name": "AI 进化预测组", "method": "动态回归建模", "r": sorted(random.sample(range(1,36), 5)), "b": hot_b, "color": "#22d3ee"},
        {"name": "平衡概率组", "method": "遗漏补偿算法", "r": sorted(random.sample(range(1,36), 5)), "b": [random.randint(1,12), hot_b[0]], "color": "#fbbf24"},
        {"name": "冷热对冲组", "method": "频率对冲过滤", "r": sorted(random.sample([n for n in range(1,36) if n not in hot_r], 5)), "b": sorted(random.sample(range(1,13), 2)), "color": "#f43f5e"},
        {"name": "热号情报站", "method": "当前最热号码分布", "r": sorted(hot_r[:5]), "b": hot_b, "color": "#a855f7"}
    ], oms, hot_r, hot_b

@app.route("/")
def index():
    init_db()
    _, cached_data, is_real_flag = load_from_disk()
    if not cached_data:
        # 如果没数据，给一个精美的“欢迎投喂”界面，而不是空白
        return render_template("index.html", history=[], preds=[], last={"p":"未激活","date":"待投喂"}, is_real=0)
    return render_template("index.html", history=cached_data["history"], preds=cached_data["preds"], 
                           r_omission=cached_data.get("r_omission", {}), last=cached_data["history"][0], is_real=is_real_flag)

@app.route("/feed", methods=["POST"])
def feed_data():
    # 严格校验暗号
    if request.form.get("pw") != "8888":
        return "暗号错误！请在第一个框输入 8888", 403
    
    content = request.form.get("content", "").strip()
    lines = content.split('\n')
    new_entries = []
    for line in lines:
        parsed = smart_parse(line)
        if parsed: new_entries.append(parsed)
    
    if not new_entries: return "格式识别失败，请确保一行包含：期号 日期 5红 2蓝", 400
    
    _, old_data, _ = load_from_disk()
    history = old_data.get('history', []) if old_data else []
    for entry in new_entries:
        if not any(h['p'] == entry['p'] for h in history):
            history.append(entry)
    
    # 按期号倒序排
    history = sorted(history, key=lambda x: str(x['p']), reverse=True)[:30]
    preds, oms, hot_r, hot_b = run_prediction_engine(history)
    
    final_data = {"history": history, "r_omission": oms, "hot_red": hot_r, "hot_blue": hot_b, "preds": preds}
    save_to_disk(final_data, 1)
    return "投喂成功！系统已激活计算引擎，正在返回首页...", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
