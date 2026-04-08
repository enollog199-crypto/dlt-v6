from flask import Flask, render_template
import requests, re, random, sqlite3, json, os
import numpy as np
import pandas as pd

app = Flask(__name__, template_folder="web")

# ===== DB =====
def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT PRIMARY KEY, red TEXT, blue TEXT, hit TEXT, confidence REAL, prob_data TEXT)''')
    conn.commit()
    conn.close()

# ===== AI 引擎（V63）=====
def autonomous_engine(history, boost=1.0):

    if len(history) < 15:
        return sorted(random.sample(range(1,36),5)), sorted(random.sample(range(1,13),2)), 50.0, {}, "数据不足"

    df = pd.DataFrame(0, index=range(len(history)), columns=range(1,36))
    for i, h in enumerate(history):
        df.loc[i, h['red']] = 1

    data = df.values[::-1]

    # 趋势权重（加入学习因子）
    trend_weights = np.exp(np.linspace(-1, 0.5, len(data))) * boost

    # 遗漏补偿
    gap_bonus = np.zeros(35)
    for col in range(35):
        idx = np.where(data[:, col] == 1)[0]
        if len(idx) > 0:
            gap_bonus[col] = (len(data) - idx[-1]) * 0.12
        else:
            gap_bonus[col] = len(data) * 0.15

    prob = np.dot(trend_weights, data) + gap_bonus
    prob = np.maximum(prob, 0) + np.random.normal(0, 0.1, 35)

    # ===== 新置信度（真实）=====
    confidence = round((len([p for p in prob if p > np.mean(prob)]) / 35) * 100, 2)

    # ===== AI解释 =====
    if np.mean(gap_bonus) > 2:
        explain = "冷号补偿增强期"
    elif confidence > 60:
        explain = "热点集中期"
    else:
        explain = "常规波动期"

    red = np.argsort(prob)[-5:] + 1

    # ===== 蓝球增强（加入gap）=====
    blue_df = pd.DataFrame(0, index=range(len(history)), columns=range(1,13))
    for i,h in enumerate(history):
        blue_df.loc[i, h['blue']] = 1

    blue_data = blue_df.values[::-1]

    blue_gap = np.zeros(12)
    for col in range(12):
        idx = np.where(blue_data[:, col] == 1)[0]
        if len(idx) > 0:
            blue_gap[col] = (len(blue_data) - idx[-1]) * 0.1
        else:
            blue_gap[col] = len(blue_data) * 0.12

    blue_prob = np.dot(trend_weights, blue_data) + blue_gap
    blue = np.argsort(blue_prob)[-2:] + 1

    prob_dict = {str(i+1): round(float(prob[i]),2) for i in range(35)}

    return sorted(red.tolist()), sorted(blue.tolist()), confidence, prob_dict, explain


# ===== 同步系统（含自学习）=====
def sync_system():
    try:
        res = requests.get("https://datachart.500.com/dlt/history/newinc/history.php", timeout=8)
        res.encoding = 'utf-8'
        rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', res.text, re.S)

        history = []
        for row in rows[:30]:
            tds = re.findall(r'<td.*?>(.*?)</td>', row)
            history.append({
                "period": tds[0],
                "red": list(map(int, tds[2:7])),
                "blue": list(map(int, tds[7:9]))
            })

        conn = sqlite3.connect("ai.db")
        c = conn.cursor()

        boost = 1.0

        # ===== 命中反馈（学习核心）=====
        for h in history:
            pred = c.execute("SELECT red, blue, hit FROM predict WHERE period=?", (h['period'],)).fetchone()
            if pred and pred[2] == "/":
                real_red, real_blue = set(h['red']), set(h['blue'])
                p_red, p_blue = set(json.loads(pred[0])), set(json.loads(pred[1]))

                hit_r = len(p_red & real_red)
                hit_b = len(p_blue & real_blue)

                hit_info = f"{hit_r}+{hit_b}"
                c.execute("UPDATE predict SET hit=? WHERE period=?", (hit_info, h['period']))

                # ===== 强化学习 =====
                score = hit_r + hit_b
                if score >= 3:
                    boost *= 1.05
                else:
                    boost *= 0.97

        # ===== 生成下一期 =====
        next_p = str(int(history[0]['period']) + 1)

        if not c.execute("SELECT 1 FROM predict WHERE period=?", (next_p,)).fetchone():
            r,b,conf,pdict,exp = autonomous_engine(history, boost)
            c.execute("INSERT INTO predict VALUES (?,?,?,?,?,?)",
                      (next_p, json.dumps(r), json.dumps(b), "/", conf, json.dumps({"prob":pdict,"exp":exp})))

        conn.commit()
        conn.close()

        return history[0], history

    except Exception as e:
        print("ERROR:", e)
        return None, []


# ===== 页面 =====
@app.route("/")
def index():
    init_db()
    latest, history = sync_system()

    conn = sqlite3.connect("ai.db")
    rows = conn.execute("SELECT * FROM predict ORDER BY period DESC LIMIT 15").fetchall()
    conn.close()

    records = []
    chart_labels, chart_values = [], []

    for r in rows:
        pdata = json.loads(r[5]) if r[5] else {}
        item = {
            "period": r[0],
            "red": json.loads(r[1]),
            "blue": json.loads(r[2]),
            "hit": r[3],
            "conf": r[4],
            "exp": pdata.get("exp","")
        }
        records.append(item)

        if r[3] != "/":
            chart_labels.append(r[0])
            chart_values.append(sum(map(int, r[3].split('+'))))

    prob_data = json.loads(rows[0][5])["prob"] if rows else {}
    top_numbers = sorted(prob_data.items(), key=lambda x:x[1], reverse=True)[:10]

    return render_template("index.html",
        latest=latest,
        records=records,
        top_numbers=top_numbers,
        chart_data={"labels": chart_labels[::-1], "values": chart_values[::-1]}
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port)
