from flask import Flask, render_template, request, redirect, session
import sqlite3, requests, re, json, os, random
from collections import Counter
from datetime import datetime

app = Flask(__name__, template_folder="web")
app.secret_key = "v46_fix"

DB="data.db"
PREDICT_FILE="predict.json"

# ===== 数据库 =====
def get_db():
    conn=sqlite3.connect(DB)
    c=conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        username TEXT,
        password TEXT
    )""")

    conn.commit()
    return conn

# ===== 获取开奖（带期号日期）=====
def fetch_history():
    try:
        url="https://datachart.500.com/dlt/history/newinc/history.php"
        html=requests.get(url,timeout=5).text

        rows=re.findall(r'<tr class="t_tr1">(.*?)</tr>',html,re.S)

        history=[]
        for row in rows[:50]:
            tds=re.findall(r'<td.*?>(.*?)</td>',row)

            period=tds[0]
            date=tds[1]

            nums=re.findall(r'\d{2}', "".join(tds[2:9]))
            red=list(map(int,nums[:5]))
            blue=list(map(int,nums[5:7]))

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

# ===== 生成预测（带策略标签）=====
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

    return {
        "red":red,
        "blue":blue,
        "mode":mode
    }

def gen_multi(history):
    return [
        gen_one(history,"稳健型"),
        gen_one(history,"进攻型"),
        gen_one(history,"均衡型")
    ]

# ===== 命中 =====
def hit(p,r):
    return len(set(p["red"])&set(r["red"])) + \
           len(set(p["blue"])&set(r["blue"]))

# ===== 首页 =====
@app.route("/")
def home():
    history=fetch_history()
    latest=history[0] if history else {}

    preds=gen_multi(history)

    for p in preds:
        p["hit"]=hit(p,latest) if latest else 0

    return render_template("index.html",
        latest=latest,
        preds=preds,
        user=session.get("username")
    )

# ===== 注册 =====
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

    return '''
    <h2>注册</h2>
    <form method=post>
    用户:<input name=username><br>
    密码:<input name=password type=password><br>
    <button>注册</button>
    </form>
    '''

# ===== 登录 =====
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]

        conn=get_db()
        c=conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?",(u,p))
        user=c.fetchone()

        if user:
            session["username"]=u
            return redirect("/")

    return '''
    <h2>登录</h2>
    <form method=post>
    用户:<input name=username><br>
    密码:<input name=password type=password><br>
    <button>登录</button>
    </form>
    '''

# ===== 退出 =====
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ===== 启动 =====
import os
port=int(os.environ.get("PORT",10000))
app.run(host="0.0.0.0",port=port)
