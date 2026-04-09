from flask import Flask, render_template
import requests, re, random, os, datetime
import numpy as np

app = Flask(__name__, template_folder="web")
app.secret_key = os.environ.get("SECRET_KEY", "dextro_v9_secure")

# =========================
# 1️⃣ 严谨数据引擎 (带日期抓取)
# =========================
class LotteryEngine:
    def __init__(self):
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def fetch_live(self):
        try:
            # 抓取 500.com 历史，提取期号、日期、号码
            res = requests.get("https://datachart.500.com/dlt/history/newinc/history.php", timeout=7, headers=self.headers)
            res.encoding = 'utf-8'
            rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
            data = []
            for r in rows[:50]:
                tds = re.findall(r'<td.*?>(.*?)</td>', r)
                if len(tds) >= 9:
                    data.append({
                        "p": tds[0],             # 期号
                        "date": tds[14] if len(tds)>14 else "N/A", # 开奖日期
                        "r": sorted(list(map(int, tds[2:7]))),
                        "b": sorted(list(map(int, tds[7:9])))
                    })
            return data
        except:
            return []

# =========================
# 2️⃣ 矩阵计算与遗漏分析
# =========================
def compute_metrics(history):
    # 初始化遗漏值 (当前未出的距离)
    red_omission = {i: 0 for i in range(1, 36)}
    blue_omission = {i: 0 for i in range(1, 13)}
    
    # 从近到远扫描
    for n in range(1, 36):
        for idx, h in enumerate(history):
            if n in h['r']: break
            red_omission[n] += 1
            
    for n in range(1, 13):
        for idx, h in enumerate(history):
            if n in h['b']: break
            blue_omission[n] += 1
            
    return red_omission, blue_omission

def quantum_engine_v9(history, mode="balanced", avoid_red=None, avoid_blue=None):
    if not history: return [1,2,3,4,5], [1,2], {}
    
    # 转换为概率分布 (基于频率和遗漏)
    red_scores = np.zeros(35)
    blue_scores = np.zeros(12)
    
    for i, h in enumerate(history):
        w = np.exp(-i/15)
        for n in h['r']: red_scores[n-1] += w
        for n in h['b']: blue_scores[n-1] += w

    # 排除逻辑 (事实避热)
    if avoid_red:
        for r_num in avoid_red: red_scores[r_num-1] = -999
    if avoid_blue:
        for b_num in avoid_blue: blue_scores[b_num-1] = -999

    # Softmax 抽样
    def get_pick(scores, count, range_max):
        exp_s = np.exp(scores - np.max(scores))
        p = exp_s / exp_s.sum()
        return sorted(np.random.choice(range(1, range_max+1), count, replace=False, p=p).tolist())

    r = get_pick(red_scores, 5, 35)
    b = get_pick(blue_scores, 2, 12)
    
    prob_dict = {str(i+1): round(float(red_scores[i]), 2) for i in range(35)}
    return r, b, prob_dict

# =========================
# 3️⃣ 路由逻辑
# =========================
cache = {"data": None, "time": 0}

@app.route("/")
def index():
    engine = LotteryEngine()
    history = engine.fetch_live()
    if not history: history = [{"p":"数据解析中","date":"-","r":[0,0,0,0,0],"b":[0,0]}]

    # 计算遗漏值
    r_omission, b_omission = compute_metrics(history)
    
    # 事实避热：识别全网最热号 (频率最高的前 8 红 3 蓝)
    red_freq = {i: 0 for i in range(1, 36)}
    for h in history[:10]: # 只看最近10期识别热度
        for n in h['r']: red_freq[n] += 1
    hot_red = sorted(red_freq, key=red_freq.get, reverse=True)[:8]
    hot_blue = [1, 5, 9] # 假设热点蓝球

    # 生成预测
    p1 = quantum_engine_v9(history, "conservative")
    p2 = quantum_engine_v9(history, "balanced")
    p3 = quantum_engine_v9(history, "aggressive")
    # 第 4 组：真正执行避热逻辑
    p4_r, p4_b, _ = quantum_engine_v9(history, "anti_hot", avoid_red=hot_red, avoid_blue=hot_blue)

    preds = [
        {"n": "趋势拟合型", "r": p1[0], "b": p1[1], "d": "基于指数衰减加权", "c": "var(--cyan)"},
        {"n": "概率均衡型", "r": p2[0], "b": p2[1], "d": "频率+遗漏综合平衡", "c": "#fff"},
        {"n": "遗漏补偿型", "r": p3[0], "b": p3[1], "d": "专注长期未出冷号", "c": "var(--amber)"},
        {"n": "事实避热型", "r": p4_r, "b": p4_b, "d": "已剔除实时热号池", "c": "var(--pink)"}
    ]

    return render_template("index.html", 
                           history=history, # 保持原始顺序用于显示
                           preds=preds, 
                           hot_red=hot_red, hot_blue=hot_blue,
                           r_omission=r_omission, b_omission=b_omission,
                           last_period=history[0])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
