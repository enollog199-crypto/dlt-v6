from flask import Flask, render_template
import requests, re, random, sqlite3
from collections import Counter

app = Flask(__name__, template_folder="web")

# ===== DB =====
def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT, mode TEXT, red TEXT, blue TEXT, hit TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS weights
                 (num INT PRIMARY KEY, score REAL)''')

    # 初始化权重
    for i in range(1,36):
        c.execute("INSERT OR IGNORE INTO weights VALUES (?,?)",(i,1.0))

    conn.commit()
    conn.close()

def load_weights():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute("SELECT * FROM weights")
    rows = c.fetchall()
    conn.close()
    return {r[0]:r[1] for r in rows}

def update_weights(hit_red):
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()

    for n in hit_red:
        c.execute("UPDATE weights SET score = score + 0.5 WHERE num=?", (n,))

    # 衰减
    c.execute("UPDATE weights SET score = score * 0.995")

    conn.commit()
    conn.close()

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

# ===== 权重池 =====
def build_pool(weights):
    pool=[]
    for n,score in weights.items():
        pool += [n]*int(score*10)
    return pool

def pick(pool,k,maxn):
    s=set()
    while len(s)<k:
        if pool:
            s.add(random.choice(pool))
        else:
            s.add(random.randint(1,maxn))
    return sorted(list(s))

# ===== AI生成 =====
def gen_ai(weights):
    pool = build_pool(weights)
    red = pick(pool,5,35)
    blue = pick(pool,2,12)
    return red, blue

# ===== 保存预测 =====
def save_predict(period, mode, red, blue):
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()

    c.execute("SELECT * FROM predict WHERE period=? AND mode=?", (period, mode))
    if c.fetchone():
        conn.close()
        return

    c.execute("INSERT INTO predict VALUES (?,?,?,?,?)",
              (period, mode, str(red), str(blue), "/"))

    conn.commit()
    conn.close()

# ===== 更新命中+学习 =====
def update_hit_and_learn(history):
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()

    weights = load_weights()

    for h in history:
        period = h["period"]
        real_red = set(h["red"])

        c.execute("SELECT rowid, red, hit FROM predict WHERE period=?", (period,))
        rows = c.fetchall()

        for r in rows:
            rid, red, hit = r

            if hit != "/":
                continue

            red = set(eval(red))
            hit_red = list(red & real_red)

            hcount = len(hit_red)

            c.execute("UPDATE predict SET hit=? WHERE rowid=?", (hcount, rid))

            # 🧠 学习
            update_weights(hit_red)

    conn.commit()
    conn.close()

# ===== 读取 =====
def load_predicts():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute("SELECT * FROM predict ORDER BY period DESC")
    rows = c.fetchall()
    conn.close()

    return [{"period":r[0],"mode":r[1],"red":r[2],"blue":r[3],"hit":r[4]} for r in rows]

# ===== 首页 =====
@app.route("/")
def home():

    init_db()

    history = fetch_history()
    latest = history[0] if history else None

    weights = load_weights()

    if latest:
        conn = sqlite3.connect("ai.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM predict WHERE period=?", (latest["period"],))
        exists = c.fetchone()[0]
        conn.close()

        if exists == 0:
            for m in ["AI"]:
                red, blue = gen_ai(weights)
                save_predict(latest["period"], m, red, blue)

    update_hit_and_learn(history)

    records = load_predicts()

    return render_template("index.html",
        latest=latest,
        records=records,
        weights=weights
    )

# ===== 启动 =====
import os
port=int(os.environ.get("PORT",10000))
app.run(host="0.0.0.0",port=port)
