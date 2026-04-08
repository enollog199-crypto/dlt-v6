from flask import Flask, render_template, request, redirect, session
import sqlite3, json, os, random, requests, re
from collections import Counter

app = Flask(__name__, template_folder="web")
app.secret_key = "v39_ai"

MODEL_FILE = "model.json"
PREDICT_FILE = "predict.json"

# ===== 数据库 =====
def get_db():
    conn = sqlite3.connect("data.db")
    c = conn.cursor()

    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, password TEXT)")
    c.execute("""
    CREATE TABLE IF NOT EXISTS predictions(
        id INTEGER PRIMARY KEY,
        username TEXT,
        red_hit INT,
        blue_hit INT
    )
    """)

    conn.commit()
    return conn

# ===== 抓历史数据 =====
def fetch_history():
    try:
        html = requests.get("https://www.lottery.gov.cn/kj/kjlb.html?dlt").text
        nums = re.findall(r'\d{2}', html)

        res=[]
        for i in range(0,700,7):
            red=list(map(int, nums[i:i+5]))
            blue=list(map(int, nums[i+5:i+7]))
            res.append({"red":red,"blue":blue})

        return res[:120]
    except:
        return [{"red":sorted(random.sample(range(1,36),5)),
                 "blue":sorted(random.sample(range(1,13),2))} for _ in range(80)]

# ===== 模型 =====
def load_model():
    if os.path.exists(MODEL_FILE):
        return json.load(open(MODEL_FILE))
    return {"freq":0.4,"gap":0.3,"rand":0.3}

def save_model(m):
    json.dump(m, open(MODEL_FILE,"w"))

# ===== 前区模型 =====
def model_freq(history):
    flat=[n for h in history for n in h["red"]]
    freq=Counter(flat)
    return sorted(freq, key=freq.get, reverse=True)

def model_gap(history):
    score={}
    for i in range(1,36):
        gap=0
        for h in history[::-1]:
            if i in h["red"]: break
            gap+=1
        score[i]=gap
    return sorted(score, key=score.get, reverse=True)

# ===== 蓝球模型（重点）=====
def model_blue(history):
    flat=[n for h in history for n in h["blue"]]
    freq=Counter(flat)
    ranked=sorted(freq, key=freq.get, reverse=True)
    return sorted(random.sample(ranked[:6],2))

# ===== 预测 =====
def predict(history, model):
    m1=model_freq(history)
    m2=model_gap(history)

    score={}
    for i in range(1,36):
        score[i]=(
            model["freq"]*(35-m1.index(i))+
            model["gap"]*(35-m2.index(i))+
            model["rand"]*random.random()*35
        )

    ranked=sorted(score, key=score.get, reverse=True)

    red=sorted(random.sample(ranked[:15],5))
    blue=model_blue(history)

    return {"red":red,"blue":blue}

# ===== 自学习 =====
def update_model(model, history):
    for k in model:
        model[k]+=random.uniform(-0.02,0.02)

    total=sum(model.values())
    for k in model:
        model[k]=round(model[k]/total,3)

    return model

# ===== 锁定预测 =====
def get_prediction(history, model):
    if os.path.exists(PREDICT_FILE):
        return json.load(open(PREDICT_FILE))

    pred=predict(history,model)
    result={"red":pred["red"],"blue":pred["blue"],"hit":{"red":0,"blue":0}}
    json.dump(result, open(PREDICT_FILE,"w"))
    return result

# ===== 命中计算 =====
def check_hit(pred, real):
    r=len(set(pred["red"]) & set(real["red"]))
    b=len(set(pred["blue"]) & set(real["blue"]))
    pred["hit"]={"red":r,"blue":b}
    json.dump(pred, open(PREDICT_FILE,"w"))
    return pred

# ===== 首页 =====
@app.route("/")
def home():
    history=fetch_history()
    latest=history[0]

    model=load_model()
    model=update_model(model,history)
    save_model(model)

    pred=get_prediction(history,model)
    pred=check_hit(pred,latest)

    # 保存记录
    if "username" in session:
        conn=get_db();c=conn.cursor()
        c.execute("INSERT INTO predictions(username,red_hit,blue_hit) VALUES (?,?,?)",
                  (session["username"], pred["hit"]["red"], pred["hit"]["blue"]))
        conn.commit()

    return render_template("index.html",
        user=session.get("username"),
        data={"latest":latest,"predict":pred}
    )

# ===== 排行榜 =====
@app.route("/rank")
def rank():
    conn=get_db();c=conn.cursor()
    c.execute("""
    SELECT username, AVG(red_hit+blue_hit) as score, COUNT(*)
    FROM predictions
    GROUP BY username
    ORDER BY score DESC
    LIMIT 10
    """)
    rows=c.fetchall()
    return render_template("rank.html", rows=rows)

# ===== 登录注册 =====
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]
        conn=get_db();c=conn.cursor()
        c.execute("INSERT INTO users(username,password) VALUES (?,?)",(u,p))
        conn.commit()
        return redirect("/login")
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]
        conn=get_db();c=conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?",(u,p))
        user=c.fetchone()
        if user:
            session["username"]=u
            return redirect("/")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
    
import os
port=int(os.environ.get("PORT",10000))
app.run(host="0.0.0.0",port=port)
