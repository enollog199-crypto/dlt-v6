from flask import Flask, render_template
import requests, re, random, sqlite3
import numpy as np
import pandas as pd

app = Flask(__name__, template_folder="web")

# ===== DB =====
def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT, red TEXT, blue TEXT, hit TEXT, confidence REAL)''')

    conn.commit()
    conn.close()

def save_predict(period, red, blue, confidence):
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()

    c.execute("SELECT * FROM predict WHERE period=?", (period,))
    if c.fetchone():
        conn.close()
        return

    c.execute("INSERT INTO predict VALUES (?,?,?,?,?)",
              (period, str(red), str(blue), "/", confidence))

    conn.commit()
    conn.close()

def load_predicts():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute("SELECT * FROM predict ORDER BY period DESC")
    rows = c.fetchall()
    conn.close()

    return [{"period":r[0],"red":r[1],"blue":r[2],"hit":r[3],"confidence":r[4]} for r in rows]

# ===== 抓数据 =====
def fetch_history():
    try:
        url="https://datachart.500.com/dlt/history/newinc/history.php"
        html=requests.get(url,timeout=5).text
        rows=re.findall(r'<tr class="t_tr1">(.*?)</tr>',html,re.S)

        data=[]
        for row in rows[:50]:
            tds=re.findall(r'<td.*?>(.*?)</td>',row)
            period=tds[0]

            red=list(map(int,re.findall(r'\d{2}',"".join(tds[2:7]))))
            blue=list(map(int,re.findall(r'\d{2}',"".join(tds[7:9]))))

            if len(red)==5 and len(blue)==2:
                data.append({"period":period,"red":red,"blue":blue})

        return data
    except:
        return []

# ===== 深度自回归模型 =====
def deep_predict(history):

    if len(history) < 10:
        return sorted(random.sample(range(1,36),5)), sorted(random.sample(range(1,13),2)), 0.0, {}

    df = pd.DataFrame(0, index=range(len(history)), columns=range(1,36))
    for i,h in enumerate(history):
        df.loc[i, h['red']] = 1

    data = df.values[::-1]

    weights = np.linspace(0.5,1.5,len(data))
    prob = np.dot(weights, data)

    prob = np.maximum(prob,0)
    prob += np.random.normal(0,0.1,35)

    # ===== 置信度 =====
    confidence = float(np.std(prob) / (np.mean(prob)+1e-6))
    confidence = round(min(confidence*100,100),2)

    # ===== 概率映射 =====
    prob_dict = {i+1: float(prob[i]) for i in range(35)}

    red = np.argsort(prob)[-5:] + 1

    # ===== 蓝球（同模型）=====
    blue_df = pd.DataFrame(0, index=range(len(history)), columns=range(1,13))
    for i,h in enumerate(history):
        blue_df.loc[i, h['blue']] = 1

    blue_prob = np.dot(weights, blue_df.values[::-1])
    blue = np.argsort(blue_prob)[-2:] + 1

    return sorted(red.tolist()), sorted(blue.tolist()), confidence, prob_dict

# ===== 命中计算 =====
def update_hit(history):
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()

    for h in history:
        period = h["period"]
        real_red = set(h["red"])
        real_blue = set(h["blue"])

        c.execute("SELECT rowid, red, blue, hit FROM predict WHERE period=?", (period,))
        rows = c.fetchall()

        for r in rows:
            rid, red, blue, hit = r

            if hit != "/":
                continue

            red = set(eval(red))
            blue = set(eval(blue))

            hcount = len(red & real_red) + len(blue & real_blue)

            c.execute("UPDATE predict SET hit=? WHERE rowid=?", (hcount, rid))

    conn.commit()
    conn.close()

# ===== 首页 =====
@app.route("/")
def home():

    init_db()

    history = fetch_history()
    latest = history[0] if history else None

    prob_dict = {}

    if latest:
        conn = sqlite3.connect("ai.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM predict WHERE period=?", (latest["period"],))
        exists = c.fetchone()[0]
        conn.close()

        if exists == 0:
            red, blue, conf, prob_dict = deep_predict(history)
            save_predict(latest["period"], red, blue, conf)
        else:
            # 如果已预测，重新计算概率展示（不影响历史）
            red, blue, conf, prob_dict = deep_predict(history)

    update_hit(history)

    records = load_predicts()

    # Top权重
    top_numbers = sorted(prob_dict.items(), key=lambda x:x[1], reverse=True)[:10]

    return render_template("index.html",
        latest=latest,
        records=records,
        top_numbers=top_numbers,
        confidence=conf if latest else 0
    )

# ===== 启动 =====
import os
port=int(os.environ.get("PORT",10000))
app.run(host="0.0.0.0",port=port)
