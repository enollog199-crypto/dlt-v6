from flask import Flask, render_template, request
import requests, re, random, sqlite3
from collections import Counter

app = Flask(__name__, template_folder="web")

# ===== 数据库 =====
def init_db():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS predict
                 (period TEXT, mode TEXT, red TEXT, blue TEXT, hit INT)''')
    conn.commit()
    conn.close()

def save_predict(period, mode, red, blue):
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute("INSERT INTO predict VALUES (?,?,?,?,?)",
              (period, mode, str(red), str(blue), 0))
    conn.commit()
    conn.close()

def update_hit(period, real):
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()

    c.execute("SELECT rowid, red, blue FROM predict WHERE period=?", (period,))
    rows = c.fetchall()

    for r in rows:
        rid, red, blue = r
        red = eval(red)
        blue = eval(blue)

        hit = len(set(red)&set(real["red"])) + len(set(blue)&set(real["blue"]))

        c.execute("UPDATE predict SET hit=? WHERE rowid=?", (hit, rid))

    conn.commit()
    conn.close()

def load_predicts():
    conn = sqlite3.connect("ai.db")
    c = conn.cursor()
    c.execute("SELECT * FROM predict ORDER BY period DESC LIMIT 20")
    rows = c.fetchall()
    conn.close()
    return [{"period":r[0],"mode":r[1],"red":r[2],"blue":r[3],"hit":r[4]} for r in rows]

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

# ===== AI逻辑 =====
def gen_by_mode(mode):
    if mode=="稳健":
        red=sorted(random.sample(range(1,36),5))
    elif mode=="激进":
        red=sorted([random.randint(1,35) for _ in range(5)])
    else:
        red=sorted(random.sample(range(10,36),5))

    blue=sorted(random.sample(range(1,13),2))

    return red,blue

# ===== 首页 =====
@app.route("/", methods=["GET","POST"])
def home():

    init_db()

    history=fetch_history()

    latest=history[0] if history else None

    modes=["稳健","激进","冷号"]

    preds=[]

    if request.method=="POST":
        for m in modes:
            red,blue=gen_by_mode(m)
            preds.append({"mode":m,"red":red,"blue":blue})

            if latest:
                save_predict(latest["period"],m,red,blue)

    # 更新命中（只对已开奖）
    if history:
        for h in history[:10]:
            update_hit(h["period"],h)

    records=load_predicts()

    return render_template("index.html",
        latest=latest,
        preds=preds,
        records=records
    )

# ===== 启动 =====
import os
port=int(os.environ.get("PORT",10000))
app.run(host="0.0.0.0",port=port)
