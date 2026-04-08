from flask import Flask, render_template, request, redirect, session
import sqlite3, os, json, random, threading, time

app = Flask(__name__)
app.secret_key = "v37_secret"

DB = "users.db"
MODEL_FILE = "model_v37.json"
HISTORY_FILE = "history_v37.json"

lock = threading.Lock()

# ================= 数据库 =================
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)")
    conn.commit()
    conn.close()

init_db()

# ================= 用户 =================
def get_user():
    if "user" in session:
        return session["user"]
    return None

# ================= 开奖（模拟稳定版本） =================
def fetch_latest():
    # 👉 真实接口不稳定，这里用“稳定+递增期号”
    if os.path.exists(HISTORY_FILE):
        history=json.load(open(HISTORY_FILE))
    else:
        history=[]

    if history:
        last=int(history[-1]["period"])
        period=str(last+1)
    else:
        period="1000000"

    red=sorted(random.sample(range(1,36),5))
    blue=sorted(random.sample(range(1,13),2))

    return {"period":period,"red":red,"blue":blue}

def load_history():
    if os.path.exists(HISTORY_FILE):
        return json.load(open(HISTORY_FILE))
    return []

def save_history(draw):
    history=load_history()
    if not history or history[-1]["period"]!=draw["period"]:
        history.append(draw)
        json.dump(history,open(HISTORY_FILE,"w"))

# ================= AI预测 =================
def load_model():
    if os.path.exists(MODEL_FILE):
        return json.load(open(MODEL_FILE))
    return {"freq":0.33,"random":0.67}

def save_model(m):
    json.dump(m,open(MODEL_FILE,"w"))

def predict(history):
    red=sorted(random.sample(range(1,36),5))
    blue=sorted(random.sample(range(1,13),2))
    return red,blue

# ================= 全局数据 =================
data={
    "latest":{"period":"","red":[],"blue":[]},
    "predict":{"period":"","red":[],"blue":[],"hit":{"red":0,"blue":0}}
}

# ================= 核心循环 =================
def loop():
    while True:
        with lock:
            latest=fetch_latest()
            history=load_history()

            # 新开奖
            if not history or history[-1]["period"]!=latest["period"]:
                save_history(latest)

                # 命中计算
                if data["predict"]["period"]:
                    pr=data["predict"]["red"]
                    pb=data["predict"]["blue"]

                    hit_r=len(set(pr)&set(latest["red"]))
                    hit_b=len(set(pb)&set(latest["blue"]))

                    data["predict"]["hit"]={"red":hit_r,"blue":hit_b}

                # 新预测（只在开奖后生成）
                red,blue=predict(history)
                data["predict"]={
                    "period":latest["period"],
                    "red":red,
                    "blue":blue,
                    "hit":{"red":0,"blue":0}
                }

            data["latest"]=latest

        time.sleep(8)

threading.Thread(target=loop,daemon=True).start()

# ================= 页面 =================

@app.route("/")
def index():
    return render_template("index.html",data=data,user=get_user())

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]

        conn=sqlite3.connect(DB)
        c=conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?",(u,p))
        user=c.fetchone()
        conn.close()

        if user:
            session["user"]=u
            return redirect("/")
    return render_template("login.html")

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]

        conn=sqlite3.connect(DB)
        c=conn.cursor()
        c.execute("INSERT INTO users (username,password) VALUES (?,?)",(u,p))
        conn.commit()
        conn.close()

        return redirect("/login")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)
