from flask import Flask, render_template, session, request, redirect
import sqlite3, requests, re, json, os, random
from collections import Counter
from datetime import datetime

app = Flask(__name__, template_folder="web")
app.secret_key = "v46.2"

DB="data.db"
STATS_FILE="stats.json"

# ===== 数据库 =====
def get_db():
    conn=sqlite3.connect(DB)
    c=conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, password TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS hits(id INTEGER PRIMARY KEY, hit INT)")
    conn.commit()
    return conn

# ===== 获取真实开奖（修复版）=====
def fetch_history():
    try:
        url="https://datachart.500.com/dlt/history/newinc/history.php"
        html=requests.get(url,timeout=5).text

        rows=re.findall(r'<tr class="t_tr1">(.*?)</tr>',html,re.S)

        history=[]
        for row in rows[:30]:
            tds=re.findall(r'<td.*?>(.*?)</td>',row)

            if len(tds) < 9:
                continue

            period=tds[0].strip()
            date=tds[1].strip()

            red=list(map(int, re.findall(r'\d{2}', "".join(tds[2:7]))))
            blue=list(map(int, re.findall(r'\d{2}', "".join(tds[7:9]))))

            history.append({
                "period":period,
                "date":date,
                "red":red,
                "blue":blue
            })

        return history
    except:
        return []

# ===== 模型 =====
def hot(history):
    c=Counter()
    for h in history: c.update(h["red"])
    return [n for n,_ in c.most_common()]

def cold(history):
    score={}
    for i in range(1,36):
        gap=0
        for h in history:
            if i in h["red"]: break
            gap+=1
        score[i]=gap
    return sorted(score,key=score.get,reverse=True)

def blue_model(history):
    c=Counter()
    for h in history: c.update(h["blue"])
    return [n for n,_ in c.most_common()]

# ===== AI预测（带标签）=====
def gen_one(history, mode):
    h=hot(history)
    c=cold(history)

    if mode=="稳健型":
        pool=h[:12]
    elif mode=="进攻型":
        pool=c[:12]
    else:
        pool=h[:6]+c[:6]

    red=sorted(random.sample(pool,5))
    blue=sorted(random.sample(blue_model(history)[:6],2))

    return {"red":red,"blue":blue,"mode":mode}

def gen_multi(history):
    return [
        gen_one(history,"稳健型"),
        gen_one(history,"进攻型"),
        gen_one(history,"均衡型")
    ]

# ===== 命中 =====
def calc_hit(p,r):
    return len(set(p["red"])&set(r["red"])) + \
           len(set(p["blue"])&set(r["blue"]))

# ===== 统计 =====
def load_stats():
    if os.path.exists(STATS_FILE):
        return json.load(open(STATS_FILE))
    return {"cost":0,"win":0,"round":0}

def save_stats(s):
    json.dump(s,open(STATS_FILE,"w"))

# ===== 趋势 =====
def get_trend():
    conn=get_db()
    c=conn.cursor()
    c.execute("SELECT hit FROM hits ORDER BY id DESC LIMIT 10")
    rows=c.fetchall()
    return [r[0] for r in rows[::-1]]

# ===== 首页 =====
@app.route("/")
def home():
    history=fetch_history()
    latest=history[0] if history else {}

    preds=gen_multi(history)

    conn=get_db()
    c=conn.cursor()

    total_hit=0
    for p in preds:
        h=calc_hit(p,latest) if latest else 0
        p["hit"]=h
        total_hit+=h
        c.execute("INSERT INTO hits(hit) VALUES (?)",(h,))

    conn.commit()

    # ===== ROI统计 =====
    stats=load_stats()
    stats["round"]+=1
    stats["cost"]+=6
    stats["win"]+=total_hit*2
    save_stats(stats)

    roi=round((stats["win"]-stats["cost"])/stats["cost"],2) if stats["cost"]>0 else 0

    trend=get_trend()

    return render_template("index.html",
        latest=latest,
        preds=preds,
        stats=stats,
        roi=roi,
        trend=trend,
        user=session.get("username")
    )

# ===== 登录/注册 =====
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]

        conn=get_db()
        c=conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?",(u,p))
        if c.fetchone():
            session["username"]=u
            return redirect("/")

    return '<form method=post>user<input name=username> pass<input name=password><button>登录</button></form>'

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]

        conn=get_db()
        c=conn.cursor()
        c.execute("INSERT INTO users(username,password) VALUES (?,?)",(u,p))
        conn.commit()
        return redirect("/login")

    return '<form method=post>user<input name=username> pass<input name=password><button>注册</button></form>'

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ===== 启动 =====
import os
port=int(os.environ.get("PORT",10000))
app.run(host="0.0.0.0",port=port)
