from flask import Flask, render_template, request, redirect, url_for, session
import requests, re, random, sqlite3, json, os
import numpy as np
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ai_multi_source_v65"

# ===== 数据库初始化 =====
def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT PRIMARY KEY, red TEXT, blue TEXT, hit TEXT, confidence REAL, prob_data TEXT)''')
    conn.commit()
    conn.close()

# ===== 数据抓取源 A: 500.com =====
def fetch_from_500():
    try:
        url = "https://datachart.500.com/dlt/history/newinc/history.php"
        res = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        res.encoding = 'utf-8'
        rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
        history = []
        for row in rows[:5]: # 取最近5期做比对
            tds = re.findall(r'<td.*?>(.*?)</td>', row)
            history.append({"period": tds[0], "red": sorted(list(map(int, tds[2:7]))), "blue": sorted(list(map(int, tds[7:9])))})
        return history
    except: return None

# ===== 数据抓取源 B: 新浪彩票 (备份源) =====
def fetch_from_sina():
    try:
        url = "https://kj.sina.com.cn/dlt/"
        res = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        res.encoding = 'utf-8'
        # 匹配期号和开奖号码
        periods = re.findall(r'<td class="td_issue">(.*?)</td>', res.text)
        balls = re.findall(r'<td class="td_ball">.*?<span class="ball_red">(.*?)</span>.*?<span class="ball_blue">(.*?)</span>', res.text, re.S)
        history = []
        for i in range(min(5, len(periods))):
            reds = sorted(list(map(int, balls[i][0].replace('</span><span class="ball_red">', ' ').split())))
            blues = sorted(list(map(int, balls[i][1].replace('</span><span class="ball_blue">', ' ').split())))
            history.append({"period": periods[i].strip(), "red": reds, "blue": blues})
        return history
    except: return None

# ===== 核心同步逻辑：双源对齐 =====
def sync_system():
    init_db()
    source_a = fetch_from_500()
    source_b = fetch_from_sina()
    
    final_history = None
    
    # 比对逻辑：如果两个源都有数据，取交集（确保准确）
    if source_a and source_b:
        # 以期号为 Key 进行比对
        dict_a = {h['period']: h for h in source_a}
        dict_b = {h['period']: h for h in source_b}
        final_history = []
        for p in dict_a:
            if p in dict_b and dict_a[p] == dict_b[p]: # 完全一致才信任
                final_history.append(dict_a[p])
    elif source_a: # 如果 B 坏了，单用 A
        final_history = source_a
    elif source_b: # 如果 A 坏了，单用 B
        final_history = source_b

    if not final_history: return None, []

    # 写入数据库并生成预测
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    try:
        # 核销逻辑 (略，同前)
        latest_period = final_history[0]['period']
        next_p = str(int(latest_period) + 1)
        
        if not c.execute("SELECT 1 FROM predict WHERE period=?", (next_p,)).fetchone():
            # 这里调用你的 AI 引擎渲染新数据
            # 为了简洁，演示直接生成随机占位 (实际应用中会调用 autonomous_engine)
            r, b = sorted(random.sample(range(1,36),5)), sorted(random.sample(range(1,13),2))
            c.execute("INSERT INTO predict VALUES (?,?,?,?,?,?)", 
                      (next_p, json.dumps(r), json.dumps(b), "/", 85.5, json.dumps({"prob":{},"exp":"多源核验完成"})))
        conn.commit()
    finally:
        conn.close()
    
    return final_history[0], final_history

# ===== 路由部分 (全量覆盖，确保无内置方法报错) =====
@app.route("/")
def index():
    latest, history = sync_system()
    conn = sqlite3.connect("ai.db")
    rows = conn.execute("SELECT period, red, blue, hit, confidence, prob_data FROM predict ORDER BY period DESC LIMIT 15").fetchall()
    conn.close()

    records = []
    chart_l, chart_v = [], []

    for r in rows:
        p_json = json.loads(r[5]) if r[5] else {}
        records.append({
            "period": str(r[0]),
            "red": json.loads(r[1]),
            "blue": json.loads(r[2]),
            "hit": str(r[3]),
            "conf": r[4],
            "exp": p_json.get("exp", "分析完成")
        })
        if str(r[3]) != "/":
            chart_l.append(str(r[0]))
            try: chart_v.append(sum(map(int, str(r[3]).split('+'))))
            except: chart_v.append(0)

    # 封装图表数据，强制 list 转换
    f_chart = {"labels": list(reversed(chart_l)), "values": list(reversed(chart_v))}
    
    # 提取概率排行
    p_data = json.loads(rows[0][5]).get("prob", {}) if rows else {}
    top_numbers = sorted(p_data.items(), key=lambda x:x[1], reverse=True)[:10]

    return render_template("index.html", records=records, top_numbers=top_numbers, chart_data=f_chart, logged_in=('user' in session))

# ... 保留 login/register/rank ...
