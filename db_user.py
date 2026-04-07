from flask import Flask, request, redirect, session, render_template_string
import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "v30_ui"

def get_db():
    return sqlite3.connect("user_v28.db")


# ===== 首页（开放访问）=====
@app.route("/")
def home():
    user = session.get("username")

    return render_template_string("""
    <h1>🎯 彩票预测系统 V30</h1>

    {% if user %}
        <p>欢迎：{{user}}</p>
        <a href="/dashboard">进入系统</a><br>
        <a href="/logout">退出</a>
    {% else %}
        <a href="/login">登录</a><br>
        <a href="/register">注册</a>
    {% endif %}
    """ , user=user)


# ===== 注册 =====
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        u = request.form["username"]
        p = generate_password_hash(request.form["password"])

        conn=get_db(); c=conn.cursor()
        try:
            c.execute("INSERT INTO users(username,password) VALUES (?,?)",(u,p))
            conn.commit()
            return "注册成功 <a href='/login'>去登录</a>"
        except:
            return "用户名已存在"

    return """
    <h2>注册</h2>
    <form method="post">
    用户:<input name="username"><br>
    密码:<input name="password" type="password"><br>
    <button>注册</button>
    </form>
    <br>
    <a href="/">返回首页</a>
    """


# ===== 登录 =====
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
            return redirect("/dashboard")

        return "登录失败 <a href='/login'>重试</a>"

    return """
    <h2>登录</h2>
    <form method="post">
    用户:<input name="username"><br>
    密码:<input name="password" type="password"><br>
    <button>登录</button>
    </form>
    <br>
    <a href="/">返回首页</a>
    """


# ===== 核心页面（需要登录）=====
@app.route("/dashboard")
def dashboard():
    if "uid" not in session:
        return redirect("/login")

    return """
    <h2>🎯 系统主页</h2>

    <p>普通用户：1组预测</p>
    <p>VIP：多组预测（即将开放）</p>

    <a href="/subscribe">开通VIP</a><br>
    <a href="/">返回首页</a><br>
    <a href="/logout">退出</a>
    """


# ===== 订阅入口 =====
@app.route("/subscribe")
def subscribe():
    return """
    <h3>VIP ￥9.9/月（自动续费）</h3>
    <a href="/create-subscription">👉 PayPal订阅</a><br><br>
    <a href="/dashboard">返回</a>
    """


# ===== 退出 =====
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


app.run(host="0.0.0.0", port=10000)
