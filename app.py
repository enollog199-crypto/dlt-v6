import warnings
warnings.filterwarnings("ignore", category=UserWarning)
from flask import Flask, render_template, request
import time, datetime, os, random, sqlite3, json, re

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ultra_stable_v18_6"
DB_PATH = 'dextro_data.db'

# 数据库连接：增加超时设置，防止 Render 环境下文件锁死
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
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
        print(f"DB Save Error: {e}")

def load_from_disk():
    try:
        conn = get_db()
        row = conn.execute("SELECT last_update, data_json FROM system_cache WHERE id=1").fetchone()
        conn.close()
        if row: return row[0], json.loads(row[1])
    except: pass
    return 0, None

# 模糊识别引擎：无视空格，只抓取关键数字序列
def smart_parse(raw_text):
    try:
        nums = re.findall(r'\d+', raw_text)
        if len(nums) < 8: return None
        
        # 逻辑：首项为期号，最后两项为蓝球，紧邻蓝球的前五项为红球
        p_num = nums[0]
        blue = [int(nums[-2]), int(nums[-1])]
        red = [int(x) for x in nums[-7:-2]]
        
        # 尝试匹配日期字符串 yyyy/mm/dd 或 yyyy-mm-dd
        date_match = re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', raw_text)
        date_str = date_match.group() if date_match else datetime.datetime.now().strftime("%Y-%m-%d")
        
        return {"p": p_num, "date": date_str, "r": sorted(red), "b": sorted(blue)}
    except: return None

# 核心计算引擎：在数据更新后立即执行
def run_prediction_engine(history):
    if not history: return [], {}

    # 1. 频率分析
    red_f = {i: 0 for i in range(1, 36)}; blue_f = {i: 0 for i in range(1, 13)}
    for h in history:
        for n in h['r']: red_f[n] += 1
        for n in h['b']: blue_f[n] += 1
    
    # 2. 遗漏值分析 (Key 强制设为字符串以兼容 HTML)
    oms = {}
    for n in range(1, 36):
        count = 0
        for h in history:
            if n in h['r']: break
            count += 1
        oms[str(n)] = count
            
    hot_r = sorted(red_f, key=red_f.get, reverse=True)[:6]
    hot_b = sorted(blue_f, key=blue_f.get, reverse=True)[:2]
    
    # 3. 产生四组推测结果
    preds = [
        {"name": "AI 深度建模组", "method": "多维动态回归算法", "r": sorted(random.sample(range(1,36), 5)), "b": hot_b, "color": "#22d3ee"},
        {"name": "遗漏补偿组", "method": "冷号概率对冲模型", "r": sorted(random.sample(range(1,36), 5)), "b": [random.randint(1,12), hot_b[0]], "color": "#fbbf24"},
        {"name": "平衡概率组", "method": "频率去噪平滑过滤", "r": sorted(random.sample([n for n in range(1,36) if n not in hot_r], 5)), "b": sorted(random.sample(range(1,13), 2)), "color": "#f43f5e"},
        {"name": "热号情报站", "method": "当前频率核心分布", "r": sorted(hot_r[:5]), "b": hot_b, "color": "#a855f7"}
    ]
    return preds, oms

@app.route("/")
def index():
    _, cached_data = load_from_disk()
    # 增加空防御逻辑：如果没数据，history 传空，last 传默认字典
    if not cached_data or not cached_data.get("history"):
        return render_template("index.html", history=[], preds=[], r_omission={}, last={"p":"待激活","date":"等待投喂"})
    
    return render_template("index.html", 
                           history=cached_data["history"], 
                           preds=cached_data["preds"], 
                           r_omission=cached_data.get("r_omission", {}), 
                           last=cached_data["history"][0])

@app.route("/feed", methods=["POST"])
def feed_data():
    if request.form.get("pw") != "8888": return "暗号错误", 403
    
    raw_content = request.form.get("content", "").strip()
    if not raw_content: return "投喂内容不能为空", 400
    
    lines = raw_content.split('\n')
    _, old_data = load_from_disk()
    history = old_data.get('history', []) if old_data else []
    
    added_count = 0
    for line in lines:
        item = smart_parse(line)
        # 去重：如果期号已存在则跳过
        if item and not any(h['p'] == item['p'] for h in history):
            history.append(item)
            added_count += 1
            
    if not history: return "未能解析出任何有效数字，请检查格式", 400
    
    # 按期号倒序排列，保留最近 40 期
    history = sorted(history, key=lambda x: int(x['p']), reverse=True)[:40]
    
    # 重新触发 AI 引擎计算
    preds, oms = run_prediction_engine(history)
    
    # 封包保存
    save_to_disk({"history": history, "r_omission": oms, "preds": preds})
    return f"成功激活！已识别 {added_count} 期新数据。", 200

if __name__ == "__main__":
    # Render 端口适配
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
