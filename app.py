import warnings
warnings.filterwarnings("ignore", category=UserWarning)
from flask import Flask, render_template, request
import time, datetime, os, random, sqlite3, json, re

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_fuzzy_pro_v18_4"
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

# 【核心升级】极其强悍的模糊识别算法
def smart_parse(raw_text):
    try:
        # 1. 提取行内所有数字
        nums = re.findall(r'\d+', raw_text)
        if len(nums) < 8: return None
        
        # 2. 识别逻辑：期号(1) + 忽略日期 + 红球(5) + 蓝球(2)
        # 无论中间日期是 2026/4/8 (3个数字) 还是 2026-04-08 (3个数字)，我们直接从末尾倒推
        p_num = nums[0] 
        blue = [int(nums[-2]), int(nums[-1])]
        red = [int(x) for x in nums[-7:-2]]
        
        # 3. 提取日期（正则匹配 yyyy/mm/dd 或 yyyy-mm-dd）
        date_match = re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', raw_text)
        date_str = date_match.group() if date_match else "----"
        
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
    
    # 动态生成 4 组推测
    return [
        {"name": "AI 深度建模组", "method": "动态回归算法", "r": sorted(random.sample(range(1,36), 5)), "b": hot_b, "color": "#22d3ee"},
        {"name": "遗漏回补组", "method": "冷号概率补偿", "r": sorted(random.sample(sorted(oms, key=oms.get, reverse=True)[:10], 3) + random.sample(range(1,36), 2)), "b": [random.randint(1,12), hot_b[0]], "color": "#fbbf24"},
        {"name": "冷热对冲组", "method": "热度去噪过滤", "r": sorted(random.sample([n for n in range(1,36) if n not in hot_r], 5)), "b": sorted(random.sample(range(1,13), 2)), "color": "#f43f5e"},
        {"name": "热号情报站", "method": "当前频率核心分布", "r": sorted(hot_r[:5]), "b": hot_b, "color": "#a855f7"}
    ], oms

@app.route("/")
def index():
    init_db()
    _, cached_data, _ = load_from_disk()
    if not cached_data:
        return render_template("index.html", history=[], last={"p":"未激活","date":"等待投喂"})
    
    return render_template("index.html", 
                           history=cached_data["history"], 
                           preds=cached_data["preds"], 
                           r_omission=cached_data.get("r_omission", {}), 
                           last=cached_data["history"][0])

@app.route("/feed", methods=["POST"])
def feed_data():
    if request.form.get("pw") != "8888": return "暗号错误", 403
    
    raw_content = request.form.get("content", "").strip()
    lines = raw_content.split('\n')
    
    _, old_data, _ = load_from_disk()
    history = old_data.get('history', []) if old_data else []
    
    success_count = 0
    for line in lines:
        parsed = smart_parse(line)
        if parsed and not any(h['p'] == parsed['p'] for h in history):
            history.append(parsed)
            success_count += 1
            
    if success_count == 0 and not history:
        return "未能识别任何新数据，请检查格式", 400
    
    # 排序：按期号从大到小
    history = sorted(history, key=lambda x: int(x['p']), reverse=True)[:40]
    preds, oms = run_prediction_engine(history)
    
    final_data = {"history": history, "r_omission": oms, "preds": preds}
    save_to_disk(final_data, 1)
    
    return f"成功识别并投喂 {success_count} 期数据！系统已重新计算。", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
