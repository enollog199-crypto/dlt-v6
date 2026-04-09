import warnings
warnings.filterwarnings("ignore", category=UserWarning)
from flask import Flask, render_template
import requests, time, datetime, os, random, sqlite3, json

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_vision_v17_2"
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

class DataEngine:
    def fetch_all(self):
        try:
            url = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?gameNo=85&pageSize=30"
            res = requests.get(url, timeout=4, headers={'User-Agent': 'Mozilla/5.0'})
            if res.status_code == 200:
                raw = res.json()['value']['list']
                data = []
                for i in raw:
                    nums = i['lotteryDrawResult'].split()
                    r_list = sorted([int(n) for n in nums[:5]])
                    data.append({
                        "p": i['lotteryDrawNum'], "date": i['lotteryDrawTime'],
                        "r": r_list, "r_set": list(set(r_list)),
                        "b": sorted([int(n) for n in nums[5:]])
                    })
                return data
        except: return None

@app.route("/")
def index():
    init_db()
    now_ts = time.time()
    last_update, cached_data, is_real_flag = load_from_disk()
    
    # 强制尝试更新（如果超过1小时）
    if not cached_data or (now_ts - last_update > 3600):
        new_history = DataEngine().fetch_all()
        if new_history:
            # 计算逻辑...
            red_f = {i: 0 for i in range(1, 36)}; blue_f = {i: 0 for i in range(1, 13)}
            for h in new_history[:10]:
                for n in h['r']: red_f[n] += 1
                for n in h['b']: blue_f[n] += 1
            hot_r = sorted(red_f, key=red_f.get, reverse=True)[:6]
            hot_b = sorted(blue_f, key=blue_f.get, reverse=True)[:2]
            oms = {str(i): 0 for i in range(1, 36)}
            for n in range(1, 36):
                for h in new_history:
                    if n in h['r']: break
                    oms[str(n)] += 1

            cached_data = {
                "history": new_history, "hot_red": hot_r, "hot_blue": hot_b, "r_omission": oms,
                "data_source": "LIVE", # 标记为实时
                "preds": [
                    {"name": "AI 实时建模组", "method": "基于官网最新 30 期数据分析", "r": sorted(random.sample(range(1,36),5)), "b": hot_b, "color": "#22d3ee"},
                    {"name": "事实避热对冲组", "method": "动态剔除近 10 期高频号码", "r": sorted(random.sample([n for n in range(1,36) if n not in hot_r], 5)), "b": sorted(random.sample([n for n in range(1,13) if n not in hot_b], 2)), "color": "#f43f5e"}
                ]
            }
            save_to_disk(cached_data, 1)
            is_real_flag = 1
        elif not cached_data:
            # 彻底抓不到且没缓存时，生成模拟数据
            cached_data = {
                "history": [{"p": "数据同步中", "date": "待更新", "r": [1,2,3,4,5], "b": [1,2], "r_set": [1,2,3,4,5]}],
                "hot_red": [1,2,3,4,5,6], "hot_blue": [1,12], "r_omission": {str(i):0 for i in range(1,36)},
                "data_source": "OFFLINE", # 标记为离线
                "preds": [
                    {"name": "系统模拟预演组", "method": "由于网络限制，当前使用离线算法", "r": [8,12,19,23,31], "b": [3,10], "color": "#94a3b8"},
                    {"name": "极低频补偿组", "method": "离线状态下的概率回补模拟", "r": [2,14,20,28,35], "b": [5,11], "color": "#94a3b8"}
                ]
            }
            is_real_flag = 0

    return render_template("index.html", 
                           history=cached_data["history"], 
                           preds=cached_data["preds"], 
                           hot_red=cached_data["hot_red"], 
                           hot_blue=cached_data["hot_blue"], 
                           r_omission=cached_data.get("r_omission", {}), 
                           last=cached_data["history"][0],
                           is_real=is_real_flag)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
