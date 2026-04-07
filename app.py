from flask import Flask, request, redirect, session, render_template_string
import sqlite3, random, json, time
from werkzeug.security import generate_password_hash, check_password_hash

import db_user  # 自动初始化数据库（只留这一次）

app = Flask(__name__)
app.secret_key = "v29_secret"

def get_db():
    return sqlite3.connect("user_v28.db")


@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        u = request.form["username"]
        p = generate_password_hash(request.form["password"])

        conn=get_db(); c=conn.cursor()
        try:
            c.execute("INSERT INTO users(username,password) VALUES (?,?)",(u,p))
            conn.commit()
            return "注册成功 <a href='/login'>登录</a>"
        except:
            return "用户名已存在"

    return """注册<br><form method=post>
    用户:<input name=username><br>
    密码:<input name=password type=password><br>
    <button>注册</button></form>"""


@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]

        conn=get_db(); c=conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?",(u,))
        user=c.fetchone()

        if user and check_password_hash(user[2],p):
            session["uid"]=user[0]
            session["username"]=user[1]
            session["vip"]=user[3]
            session["vip_expire"]=user[4]
            return redirect("/")
        return "登录失败"

    return """登录<br><form method=post>
    用户:<input name=username><br>
    密码:<input name=password type=password><br>
    <button>登录</button></form>"""


def check_vip():
    if session.get("vip_expire",0) < time.time():
        session["vip"]=0
        return 0
    return 1


@app.route("/")
def home():
    if "uid" not in session:
        return redirect("/login")

    vip = check_vip()

    rec = sorted(random.sample(range(1,36),5))
    recs = [sorted(random.sample(range(1,36),5)) for _ in range(5)] if vip else []

    return render_template_string("""
    <h2>🎯 V29</h2>
    <p>用户：{{u}}</p>
    <p>VIP：{{vip}}</p>

    <h3>推荐</h3>
    {{rec}}

    {% if vip %}
    <h3>VIP多注</h3>
    {% for r in recs %}
    <p>{{r}}</p>
    {% endfor %}
    {% else %}
    <a href="/pay">开通VIP ￥9.9/月</a>
    {% endif %}

    <br>
    <a href="/records">命中记录</a><br>
    <a href="/logout">退出</a>
    """, u=session["username"], vip=vip, rec=rec, recs=recs)


@app.route("/pay")
def pay():
    return """
    <h3>支付 ￥9.9</h3>
    <a href="https://paypal.me/1949china" target="_blank">👉 去PayPal付款</a>
    <br><br>
    <a href="/confirm">我已付款</a>
    """


@app.route("/confirm")
def confirm():
    if "uid" not in session:
        return redirect("/login")

    expire = int(time.time()) + 30*24*3600

    conn=get_db(); c=conn.cursor()
    c.execute("UPDATE users SET vip=1, created_at=? WHERE id=?",(expire,session["uid"]))
    conn.commit()

    session["vip"]=1
    session["vip_expire"]=expire

    return "VIP开通成功 <a href='/'>返回</a>"


@app.route("/records")
def records():
    if "uid" not in session:
        return redirect("/login")

    conn=get_db(); c=conn.cursor()
    c.execute("SELECT numbers,hit FROM predictions WHERE user_id=?",(session["uid"],))
    data=c.fetchall()

    return "<br>".join([str(d) for d in data])


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


app.run(host="0.0.0.0", port=10000)
