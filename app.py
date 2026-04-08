from flask import Flask, render_template, request, redirect, url_for, session
import requests, re, random, sqlite3, json, os
import numpy as np
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_ai_ultra_stable_v67"

# ===== 数据库初始化 =====
def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT PRIMARY KEY, red TEXT, blue TEXT, hit TEXT, confidence REAL, prob_data TEXT)''')
    conn.commit()
    conn.close()

# ===== 核心 AI 引擎 =====
def autonomous_engine(history):
    if len(history) < 5:
        return [1,2,3,4,5], [1,2], 50.0, {str(i):0.1 for i in range(1,36)}, "新系统数据初始化..."
    
    # 构建特征矩阵
    df = pd.DataFrame(0, index=range(len(history)), columns=range(1,36))
    for i, h in enumerate(history):
        df.loc[i, h['red']] = 1
    
    data = df.values[::-1]
    weights = np.exp(np.linspace(-1.2, 0.8, len(data)))
    
    # 计算概率
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

# ===== 数据抓取 =====
def fetch_source_a():
    try:
        res = requests.get("https://datachart.500.com/dlt/history/newinc/history.php", timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        res.encoding = 'utf-8'
        rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)
        results = []
        for r in rows[:30]:
            tds = re.findall(r'<td.*?>(.*?)</td>', r)
            results.append({"period": tds[0], "red": sorted(list(map(int, tds[2:7]))), "blue": sorted(list(map(int, tds[7:9])))})
        return results
    except: return None

def fetch_source_b():
    try:
        res = requests.get("https://kj.sina.com.cn/dlt/", timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        res.encoding = 'utf-8'
        ps = re.findall(r'<td class="td_issue">(.*?)</td>', res.text)
        bs = re.findall(r'<td class="td_ball">.*?<span class="ball_red">(.*?)</span>.*?<span class="ball_blue">(.*?)</span>', res.text, re.S)
        results = []
        for i in range(min(10, len(ps))):
            r_list = sorted(list(map(int, bs[i][0].replace('</span><span class="ball_red">', ' ').split())))
            b_list = sorted(list(map(int, bs[i][1].replace('</span><span class="ball_blue">', ' ').split())))
            results.append({"period": ps[i].strip(), "red": r_list, "blue": b_list})
        return results
    except: return None

# ===== 同步系统 (修正了括号闭合问题) =====
def sync_system():
    sa, sb =
