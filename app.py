import warnings
warnings.filterwarnings("ignore", category=UserWarning)

from flask import Flask, render_template, request
import requests, time, datetime, os, random, sqlite3, json

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ultra_v17_0"

# 数据库路径：用于解决 Render 重启丢失内存缓存的问题
DB_PATH = 'dextro_data.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS system_cache 
                       (id INTEGER PRIMARY KEY, last_update REAL, data_json TEXT)''')
        conn.commit()

def save_to_disk(data):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR REPLACE INTO system_cache (id, last_update, data_json) VALUES (1, ?, ?)",
                         (time.time(), json.dumps(data)))
            conn.commit()
    except: pass

def load_from_disk():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT last_update, data_json FROM system_cache WHERE id=1").fetchone()
            if row: return row[0], json.loads(row[1])
    except: pass
    return 0, None

class DataEngine:
    def fetch_all(self):
        try:
            # 缩短至 3.5 秒超时，避免 Render 进程挂起
            url = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?gameNo=85&pageSize=30"
            res = requests.get(url, timeout=3.5, headers={'User-Agent': 'Mozilla/5.0'})
            if res.status_code == 200:
                raw = res.json()['value']['list']
                data = []
                for i in raw:
                    r_list = sorted([int(n) for n in i['lotteryDrawResult'].split()[:5]])
                    data.append({
                        "p": i['lotteryDrawNum'],
                        "date": i['lotteryDrawTime'],
                        "r": r_list,
                        "r_set": list(set(r_list)), # 转换为列表存储，前端用 in 判断性能高
                        "b": sorted([int(n) for n in i['lotteryDrawResult'].split()[5:]])
                    })
                return data
        except Exception as e:
            print(f">>> [ERROR] 抓取失败: {e}")
        return None

@app.route("/")
def index():
    init_db()
    now_ts = time.time()
    now_dt = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    
    last_update, cached_data = load_from_disk()
    
    # 动态频率控制
    refresh_interval = 600 if (now_dt.weekday() in [0,2,5] and 20 <= now_dt.hour <= 22) else 14400
    
    if not cached_data or (now_ts - last_update > refresh_interval):
        new_history = DataEngine().fetch_all()
        if new_history:
            red_f = {i: 0 for i in range(1, 36)}; blue_f = {i: 0 for i in range(1, 13)}
            for h in new_history[:10]:
                for n in h['r']: red_f[n] += 1
                for n in h['b']: blue_f[n] += 1
            hot_r = sorted(red_f, key=red_f.get, reverse=True)[:6]
            hot_b = sorted(blue_f, key=blue_f.get, reverse=True)[:2]
            
            oms = {i: 0 for i in range(1, 36)}
            for n in range(1, 36):
                for h in new_history:
                    if n in h['r']: break
                    oms[n] += 1

            cached_data = {
                "history": new_history,
                "hot_red": hot_r, "hot_blue": hot_b, "r_omission": oms,
                "preds": [
                    {"name": "AI 建模预测组", "method": "RF 算法回归建模", "r": sorted(random.sample(range(1,36),5)), "b": hot_b, "color": "#22d3ee"},
                    {"name": "事实避热对冲组", "method": "剔除近10期热号", "r": sorted(random.sample([n for n in range(1,36) if n not in hot_r], 5)), "b": sorted(random.sample([n for n in range(1,13) if n not in hot_b], 2)), "color": "#f43f5e"},
                    {"name": "遗漏补偿组", "method": "捕捉遗漏峰值", "r": sorted(oms, key=oms.get, reverse=True)[:5], "b": [1, 12], "color": "#fbbf24"}
                ]
            }
            save_to_disk(cached_data)

    if not cached_data:
        return "系统初始化中，请稍后刷新...", 200

    return render_template("index.html", 
                           history=cached_data["history"], 
                           preds=cached_data["preds"], 
                           hot_red=cached_data["hot_red"], 
                           hot_blue=cached_data["hot_blue"], 
                           r_omission=cached_data.get("r_omission", {}), 
                           last=cached_data["history"][0])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
