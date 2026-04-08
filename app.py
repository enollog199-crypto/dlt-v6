from flask import Flask, render_template, request, redirect, url_for, session
import requests, re, random, sqlite3, json, os
import numpy as np
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ai_ultra_v66_final"

# ===== 数据库初始化 =====
def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT PRIMARY KEY, red TEXT, blue TEXT, hit TEXT, confidence REAL, prob_data TEXT)''')
    conn.commit()
    conn.close()

# ===== 核心 AI 引擎 (高性能版) =====
def autonomous_engine(history):
    if len(history) < 5:
        return [1,2,3,4,5], [1,2], 50.0, {str(i):0.1 for i in range(1,36)}, "新系统数据初始化..."
    
    # 构建矩阵
    df = pd.DataFrame(0, index=range(len(history)), columns=range(1,36))
    for i, h in enumerate(history):
        df.loc[i, h['red']] = 1
    
    # 权重计算
    data = df.values[::-1]
    weights = np.exp(np.linspace(-1.2, 0.8, len(data)))
    
    # 红球逻辑
    prob = np.dot(weights, data) + np.random.normal(0, 0.05, 35)
    red_res = (np.argsort(prob)[-5:] + 1).tolist()
    conf = round(float(np.std(prob) * 18), 2)
    conf = min(max(conf, 45.0), 98.8)

    # 蓝球逻辑
    blue_df = pd.DataFrame(0, index=range(len(history)), columns=range(1,13))
    for i, h in enumerate(history):
        blue_df.loc[i, h['blue']] = 1
    blue_prob = np.dot(weights, blue_df.values[::-1]) + np.random.normal(0, 0.05, 12)
    blue_res = (np.argsort(blue_prob)[-2:] + 1).tolist()

    p_dict = {str(i+1): round(float(prob[i]), 2) for i in range(35)}
    return sorted(red_res), sorted(blue_res), conf, p_dict, "多源校验学习完成"

# ===== 双源数据抓取逻辑 =====
def fetch_source_a(): # 500.com
    try:
        res = requests.get("https://datachart.500.com/dlt/history/newinc/history.php", timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        res.encoding = 'utf-8'
        rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
        return [{"period": t[0], "red": sorted(list(map(int, t[2:7]))), "blue": sorted(list(map(int, t[7:9])))} 
                for t in [re.findall(r'<td.*?>(.*?)</td>', r) for r in rows[:30]]]
    except: return None

def fetch_source_b(): # 新浪彩票
    try:
        res = requests.get("https://kj.sina.com.cn/dlt/", timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        res.encoding = 'utf-8'
        ps = re.findall(r'<td class="td_issue">(.*?)</td>', res.text)
        bs = re.findall(r'<td class="td_ball">.*?<span class="ball_red">(.*?)</span>.*?<span class="ball_blue">(.*?)</span>', res.text, re.S)
        return [{"period": ps[i].strip(), "red": sorted(list(map(int, bs[i][0].replace('</span><span class="ball_red">', ' ').split()))),
                 "blue": sorted(list(map(int, bs[i][1].replace('</span><span class="ball_blue">', ' ').split())))} for i in range(min(10, len(ps)))]
    except: return None

# ===== 同步与比对核心 =====
def sync_system():
    sa, sb = fetch_source_a(), fetch_source_b()
    final_h = []
    if sa and sb:
        db = {h['period']: h for h in sb}
        for ha in sa:
            if ha['period'] in db and ha == db[ha['period']]:
                final_h.append(ha)
        if not final_h: final_h = sa
    else:
        final_h = sa or sb or []

    if not final_h: return

    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    # 核销
    for h in final_h:
        row = c.execute("SELECT red, blue FROM predict WHERE period=?", (h['period'],)).fetchone()
        if row and not c.execute("SELECT 1 FROM predict WHERE period=? AND hit!='/'",(h['period'],)).fetchone():
            hr = len(set(json.loads(row[0])) & set(h['red']))
            hb = len(set(json.loads(row[1])) & set(h['blue']))
            c.execute("UPDATE predict SET hit=? WHERE period=?", (f"{hr}+{hb}", h['period']))

    # 预测下期
    next_p = str(int(final_h[0]['period']) + 1)
    if not c.execute("SELECT 1 FROM predict WHERE period=?", (next_p,)).fetchone():
        r, b, conf, pdict, exp = autonomous_engine(final_h)
        c.execute("INSERT INTO predict VALUES (?,?,?,?,?,?)", (next_p
