from flask import Flask, request, redirect, session, render_template_string
import sqlite3, random, json, time
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "v29_secret"

# ===== 数据库 =====
def get_db():
    return sqlite3.connect("user_v28.db")


# ===== 注册 =====
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        u = request.form["username"]
        p = generate_password_hash(request.form["password"])

        conn=get_db(); c=conn.cursor()
        try:
            c.execute("INSERT INTO users(username,password,vip) VALUES (?,?,0)",(u,p))
            conn.commit()
            return "注册成功 <a href='/login'>登录</a>"
        except:
            return "用户名已存在"

    return """注册<br><form method=post>
    用户:<input name=username><br>
    密码:<input name=password type=password><br>
    <button>注册</button></form>"""


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
            session["vip_expire"]=user[4] if len(user)>4 else 0
            return redirect("/")
        return "登录失败"

    return """登录<br><form method=post>
    用户:<input name=username><br>
    密码:<input name=password type=password><br>
    <button>登录</button></form>"""


# ===== VIP检查 =====
def check_vip():
    if "vip_expire" not in session:
        return 0

    if session["vip_expire"] < time.time():
        session["vip"]=0
        return 0
    return 1


# ===== 首页 =====
@app.route("/")
def home():
    if "uid" not in session:
        return redirect("/login")

    vip = check_vip()

    rec = sorted(random.sample(range(1,36),5))
    recs = [sorted(random.sample(range(1,36),5)) for _ in range(5)] if vip else []

    return render_template_string("""
    <h2>🎯 V29 系统</h2>

    <p>用户：{{u}}</p>
    <p>VIP状态：{{vip}}</p>

    <h3>普通预测</h3>
    {{rec}}

    {% if vip %}
        <h3>🔥 VIP多注</h3>
        {% for r in recs %}
        <p>{{r}}</p>
        {% endfor %}
    {% else %}
        <p>👉 VIP ￥9.9/月</p>
        <a href="/pay">去支付</a>
    {% endif %}

    <a href="/records">我的命中</a><br>
    <a href="/logout">退出</a>
    """, u=session["username"], vip=vip, rec=rec, recs=recs)


# ===== 支付页面 =====
@app.route("/pay")
def pay():
    return """
    <h3>VIP ￥9.9/月</h3>
    <p>点击下面付款（PayPal）</p>
    <a href="https://paypal.me/1949china" target="_blank">
    👉 去支付
    </a>
    <br><br>
    <a href="/confirm">我已付款</a>
    """


# ===== 手动确认付款（核心）=====
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


# ===== 命中记录 =====
@app.route("/records")
def records():
    if "uid" not in session:
        return redirect("/login")

    conn=get_db(); c=conn.cursor()
    c.execute("SELECT numbers,hit FROM predictions WHERE user_id=? ORDER BY id DESC LIMIT 10",(session["uid"],))
    data=c.fetchall()

    return "<br>".join([f"{d[0]} 👉 命中 {d[1]}" for d in data])


# ===== 保存预测 =====
def save_prediction(uid, rec, hit):
    conn=get_db(); c=conn.cursor()
    c.execute("INSERT INTO predictions(user_id,numbers,hit) VALUES (?,?,?)",
              (uid,json.dumps(rec),hit))
    conn.commit()


# ===== 退出 =====
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


app.run(host="0.0.0.0", port=10000)
