from flask import Flask, render_template, request, redirect, url_for, session
import requests, re, random, sqlite3, json, os
import numpy as np
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ai_multi_source_v65_final"

# ===== 数据库初始化 =====
def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT PRIMARY KEY, red TEXT, blue TEXT, hit TEXT, confidence REAL, prob_data TEXT)''')
    conn.commit()
    conn.close()

# ===== AI 核心分析引擎 (增强版) =====
def autonomous_engine(history, boost=1.0):
    """
    history: 经过对齐后的准确历史数据列表
    """
    if len(history) < 10:
        return sorted(random.sample(range(1,36),5)), sorted(random.sample(range(1,13),2)), 60.0, {}, "正在积累多源验证数据..."
    
    # 转换为 DataFrame 进行向量化计算
    df = pd.DataFrame(0, index=range(len(history)), columns=range(1,36))
    for i, h in enumerate(history):
        df.loc[i, h['red']] = 1
    
    data = df.values[::-1] # 时间线反转
    # 指数加权移动平均权重
    weights = np.exp(np.linspace(-1.2, 0.8, len(data))) * boost
    
    # 红球概率计算
    prob = np.dot(weights, data)
    # 加入随机微扰防止模型死锁
    prob += np.random.normal(0, 0.05, 35)
    
    red_results = (np.argsort(prob)[-5:] + 1).tolist()
    confidence = round(float(np.std(prob) * 18), 2)
    confidence = min(max(confidence, 45.0), 98.5) # 限制在合理区间

    # 蓝球概率计算
    blue_df = pd.DataFrame(0, index=range(len(history)), columns=range(1,13))
    for i, h in enumerate(history):
        blue_df.loc[i, h['blue']] = 1
    blue_prob = np.dot(weights, blue_df.values[::-1]) + np.random.normal(0, 0.05, 12)
    blue_results = (np.argsort(blue_prob)[-2:] + 1).tolist()

    # 格式化概率输出给前端走势图
    prob_dict = {str(i+1): round(float(prob[i]), 2) for i in range(35)}
    
    return sorted(red_results), sorted(blue_results), confidence, prob_dict, "多源对齐完成，模型动态修正中"

# ===== 数据源抓取 (同上一步，保留双源校验) =====
def fetch_from_500():
    try:
        url = "https://datachart.500.com/dlt/history/newinc/history.php"
        res = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        res.encoding = 'utf-8'
        rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
        return [{"period": t[0], "red": sorted(list(map(int, t[2:7]))), "blue": sorted(list(map(int, t[7:9])))} 
                for t in [re.findall(r'<td.*?>(.*?)</td>', r) for r in rows[:30]]]
    except: return None

def fetch_from_sina():
    try:
        url = "https://kj.sina.com.cn/dlt/"
        res = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        res.encoding = 'utf-8'
        ps = re.findall(r'<td class="td_issue">(.*?)</td>', res.text)
        bs = re.findall(r'<td class="td_ball">.*?<span class="ball_red">(.*?)</span>.*?<span class="ball_blue">(.*?)</span>', res.text, re.S)
        return [{"period": ps[i].strip(), 
                 "red": sorted(list(map(int, bs[i][0].replace('</span><span class="ball_red">', ' ').split()))),
                 "blue": sorted(list(map(int, bs[i][1].replace('</span><span class="ball_blue">', ' ').split())))} 
                for i in range(min(10, len(ps)))]
    except: return None

# ===== 同步与比对核心 =====
def sync_system():
    source_a = fetch_from_500()
    source_b = fetch_from_sina()
    
    final_h = []
    if source_a and source_b:
        dict_b = {h['period']: h for h in source_b}
        for ha in source_a:
            if ha['period'] in dict_b and ha == dict_b[ha['period']]:
                final_h.append(ha)
        if not final_h: final_h = source_a # 若完全不匹配则回退
    else:
        final_h = source_a or source_b or []

    if not final_h: return None, []

    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    # 1. 更新历史命中情况 (核销)
    for h in final_h:
        old = c.execute("SELECT red, blue FROM predict WHERE period=?", (h['period'],)).fetchone()
        if old and not c.execute("SELECT hit FROM predict WHERE period=? AND hit != '/'", (h['period'],)).fetchone():
            hr = len(set(json.loads(old[0])) & set(h['red']))
            hb = len(set(json.loads(old[1])) & set(h['blue']))
            c.execute("UPDATE predict SET hit=? WHERE period=?", (f"{hr}+{hb}", h['period']))

    # 2. 生成最新预测
    next_p = str(int(final_h[0]['period']) + 1)
    if not c.execute("SELECT 1 FROM predict WHERE period=?", (next_p,)).fetchone():
        r, b, conf, pdict, exp = autonomous_engine(final_h)
        c.execute("INSERT INTO predict VALUES (?,?,?,?,?,?)", (next_p, json.dumps(r), json.dumps(b), "/", conf, json.dumps({"prob":pdict,"exp":exp})))
    
    conn.commit()
    conn.close()
    return final_h[0], final_h

@app.route("/")
def index():
    init_db()
    sync_system()
    conn = sqlite3.connect("ai.db")
    rows = conn.execute("SELECT period, red, blue, hit, confidence, prob_data FROM predict ORDER BY period DESC LIMIT 15").fetchall()
    conn.close()

    records = []
    chart_l, chart_v = [], []
    for r in rows:
        p_j = json.loads(r[5]) if r[5] else {}
        records.append({"period":str(r[0]), "red":json.loads(r[1]), "blue":json.loads(r[2]), "hit":str(r[3]), "conf":r[4], "exp":p_j.get("exp","")})
        if str(r[3]) != "/":
            chart_l.append(str(r[0])); chart_v.append(sum(map(int, str(r[3]).split('+'))))

    prob_data = json.loads(rows[0][5]).get("prob", {}) if rows else {}
    top_num = sorted(prob_data.items(), key=lambda x:x[1], reverse=True)[:10]

    return render_template("index.html", records=records, top_numbers=top_num, 
                           chart_data={"labels":list(reversed(chart_l)), "values":list(reversed(chart_v))}, 
                           logged_in=('user' in session))

# ... 其他路由 (login/register/rank/logout) ...
