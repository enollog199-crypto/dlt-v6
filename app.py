from flask import Flask, request, redirect, session, render_template_string
import sqlite3, random, json

from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "v31_ui"

def get_db():
    return sqlite3.connect("user_v28.db")


# ===== 首页 =====
@app.route("/")
def home():
    user = session.get("username")

    return render_template_string("""
    <style>
    body{font-family:Arial;background:#0f172a;color:#fff;text-align:center}
    .box{margin-top:80px}
    a{display:block;margin:10px;color:#38bdf8}
    </style>

    <div class="box">
    <h1>🎯 彩票预测系统 V31</h1>

    {% if user %}
        <p>欢迎：{{user}}</p>
        <a href="/dashboard">进入系统</a>
        <a href="/rank">排行榜</a>
        <a href="/logout">退出</a>
    {% else %}
        <a href="/login">登录</a>
        <a href="/register">注册</a>
    {% endif %}
    </div>
    """, user=user)


# ===== 注册 =====
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        u=request.form["username"]
        p=generate_password_hash(request.form["password"])

        conn=get_db(); c=conn.cursor()
        try:
            c.execute("INSERT INTO users(username,password) VALUES (?,?)",(u,p))
            conn.commit()
            return redirect("/login")
        except:
            return "用户名已存在"

    return """
    <h2>注册</h2>
    <form method=post>
    用户:<input name=username><br>
    密码:<input name=password type=password><br>
    <button>注册</button>
    </form>
    <a href="/">返回</a>
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
            return redirect("/dashboard")

        return "登录失败"

    return """
    <h2>登录</h2>
    <form method=post>
    用户:<input name=username><br>
    密码:<input name=password type=password><br>
    <button>登录</button>
    </form>
    <a href="/">返回</a>
    """


# ===== 系统主页 =====
@app.route("/dashboard")
def dashboard():
    if "uid" not in session:
        return redirect("/login")

    rec = sorted(random.sample(range(1,36),5))

    # 模拟命中
    hit = random.randint(0,5)

    conn=get_db(); c=conn.cursor()
    c.execute("INSERT INTO predictions(user_id,numbers,hit) VALUES (?,?,?)",
              (session["uid"], json.dumps(rec), hit))
    conn.commit()

    return render_template_string("""
    <style>
    body{background:#020617;color:#fff;text-align:center;font-family:Arial}
    .card{background:#1e293b;padding:20px;margin:20px;border-radius:10px}
    </style>

    <h2>🎯 预测系统</h2>

    <div class="card">
    <h3>本期推荐</h3>
    <p style="font-size:20px">{{rec}}</p>
    <p>命中：{{hit}}</p>
    </div>

    <a href="/dashboard">刷新预测</a><br>
    <a href="/rank">排行榜</a><br>
    <a href="/">首页</a>
    """, rec=rec, hit=hit)


# ===== 排行榜 =====
@app.route("/rank")
def rank():
    conn=get_db(); c=conn.cursor()

    c.execute("""
    SELECT user_id, AVG(hit) as avg_hit, COUNT(*) 
    FROM predictions
    GROUP BY user_id
    ORDER BY avg_hit DESC
    LIMIT 10
    """)

    rows = c.fetchall()

    html = "<h2>🏆 排行榜</h2>"
    for i,r in enumerate(rows):
        html += f"<p>第{i+1}名 用户{r[0]} 命中率:{round(r[1],2)} 次数:{r[2]}</p>"

    html += "<br><a href='/'>返回</a>"
    return html


# ===== 退出 =====
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


app.run(host="0.0.0.0", port=10000)
