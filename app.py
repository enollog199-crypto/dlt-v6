from flask import Flask, request, redirect, session, render_template_string
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "v28_secret"

# ===== 数据库连接 =====
def get_db():
    return sqlite3.connect("user_v28.db")


# ===== 注册 =====
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        conn = get_db()
        c = conn.cursor()

        try:
            c.execute("INSERT INTO users(username,password) VALUES (?,?)",(username,password))
            conn.commit()
            return "注册成功 <a href='/login'>去登录</a>"
        except:
            return "用户名已存在"

    return """
    <h2>注册</h2>
    <form method="post">
    用户名:<input name="username"><br>
    密码:<input name="password" type="password"><br>
    <button>注册</button>
    </form>
    """


# ===== 登录 =====
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?",(username,))
        user = c.fetchone()

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            session["vip"] = user[3]
            return redirect("/")
        else:
            return "登录失败"

    return """
    <h2>登录</h2>
    <form method="post">
    用户名:<input name="username"><br>
    密码:<input name="password" type="password"><br>
    <button>登录</button>
    </form>
    """


# ===== 退出 =====
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ===== 首页（带VIP功能）=====
@app.route("/")
def home():
    if "user_id" not in session:
        return redirect("/login")

    username = session["username"]
    vip = session["vip"]

    # 简单预测（示例）
    import random
    rec = sorted(random.sample(range(1,36),5))

    # VIP多注
    recs = []
    if vip == 1:
        recs = [sorted(random.sample(range(1,36),5)) for _ in range(5)]

    return render_template_string("""
    <h2>🎯 V28 系统</h2>

    <p>用户：{{username}}</p>
    <p>VIP：{{vip}}</p>

    <h3>普通推荐</h3>
    {{rec}}

    {% if vip==1 %}
    <h3>🔥 VIP多注</h3>
    {% for r in recs %}
        <p>{{r}}</p>
    {% endfor %}
    {% else %}
    <p>👉 开通VIP查看多注预测</p>
    {% endif %}

    <br>
    <a href="/logout">退出</a>
    """, username=username, vip=vip, rec=rec, recs=recs)


# ===== 手动开VIP（测试用）=====
@app.route("/vip")
def set_vip():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET vip=1 WHERE id=?", (session["user_id"],))
    conn.commit()

    session["vip"] = 1
    return "已开通VIP <a href='/'>返回</a>"


app.run(host="0.0.0.0", port=10000)
