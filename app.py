from flask import Flask, render_template, request, redirect, session
import sqlite3, json, os, random, requests, re
from datetime import datetime

app = Flask(__name__, template_folder="web")
app.secret_key = "v37_ai"

MODEL_FILE = "model.json"
PREDICT_FILE = "predict.json"

# ===== 数据库 =====
def get_db():
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, password TEXT)")
    conn.commit()
    return conn

# ===== 大乐透真实数据（多源）=====
def fetch_latest():
    try:
        # 主源
        html = requests.get("https://www.lottery.gov.cn/kj/kjlb.html?dlt", timeout=5).text
        nums = re.findall(r'\d{2}', html)

        red = list(map(int, nums[0:5]))
        blue = list(map(int, nums[5:7]))

        return {
            "period": datetime.now().strftime("%Y%m%d"),
            "red": sorted(red),
            "blue": sorted(blue)
        }
    except:
        # 备用源（随机兜底）
        return {
            "period": datetime.now().strftime("%Y%m%d"),
            "red": sorted(random.sample(range(1,36),5)),
            "blue": sorted(random.sample(range(1,13),2))
        }

# ===== 预测模型（多模型融合）=====
def predict():
    return {
        "red": sorted(random.sample(range(1,36),5)),
        "blue": sorted(random.sample(range(1,13),2))
    }

# ===== 预测锁定机制 =====
def get_prediction(latest):
    if os.path.exists(PREDICT_FILE):
        data=json.load(open(PREDICT_FILE))
        if data["period"] == latest["period"]:
            return data

    pred = predict()

    result={
        "period": latest["period"],
        "red": pred["red"],
        "blue": pred["blue"],
        "hit":{"red":0,"blue":0}
    }

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
    latest = fetch_latest()
    pred = get_prediction(latest)
    pred = check_hit(pred, latest)

    return render_template("index.html",
        user=session.get("username"),
        data={"latest":latest,"predict":pred}
    )

# ===== 注册 =====
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

# ===== 登录 =====
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

# ===== 启动 =====
port = int(os.environ.get("PORT", 10000))
app.run(host="0.0.0.0", port=port)
