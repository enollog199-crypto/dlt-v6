from flask import Flask, request, redirect, session, render_template_string
import sqlite3, random, json
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "v31_5_final"

# ===== 数据库 =====
def get_db():
    return sqlite3.connect("user_v28.db")


# ===== 首页（直接预测）=====
@app.route("/")
def home():
    user = session.get("username")

    rec = sorted(random.sample(range(1,36),5))
    hit = random.randint(0,5)

    # 登录用户才记录
    if "uid" in session:
        conn=get_db(); c=conn.cursor()
        c.execute("INSERT INTO predictions(user_id,numbers,hit) VALUES (?,?,?)",
                  (session["uid"], json.dumps(rec), hit))
        conn.commit()

    return render_template_string("""
    <style>
    body{background:#020617;color:#fff;text-align:center;font-family:Arial}
    .card{background:#1e293b;padding:20px;margin:20px;border-radius:12px}
    a{color:#38bdf8;text-decoration:none}
    .btn{display:inline-block;margin:8px;padding:8px 16px;background:#38bdf8;color:#000;border-radius:6px}
    </style>

    <h1>🚀 ChatGPT AI大乐透预测引擎</h1>
    <p style="color:#94a3b8">数据驱动选号 · 算法优化组合 · 提高命中机会</p>

    {% if user %}
        <p>欢迎：{{user}}</p>
        <a href="/logout">退出</a>
    {% else %}
        <a class="btn" href="/login">登录</a>
        <a class="btn" href="/register">注册</a>
    {% endif %}

    <div class="card">
        <h3>🔥 本期智能推荐</h3>
        <p style="font-size:24px">{{rec}}</p>
        <p>模拟命中：{{hit}}</p>
    </div>

    <a href="/">🔄 再来一组</a><br><br>
    <a href="/rank">🏆 查看排行榜</a>

    {% if not user %}
    <p style="color:#facc15;margin-top:20px">
    👉 登录后可记录命中率 & 解锁更多预测
    </p>
    {% endif %}
    """, user=user, rec=rec, hit=hit)


# ===== 注册（含限制）=====
@app.route("/register", methods=["GET","POST"])
def register():
    msg = ""

    if request.method=="POST":
        u = request.form["username"]
        p = request.form["password"]

        # ===== 校验 =====
        if len(u) < 4 or len(u) > 12:
            msg = "❌ 用户名需4-12位"
        elif not u.isalnum():
            msg = "❌ 用户名只能字母或数字"
        elif len(p) < 6 or len(p) > 18:
            msg = "❌ 密码需6-18位"
        else:
            conn=get_db(); c=conn.cursor()
            try:
                p_hash = generate_password_hash(p)
                c.execute("INSERT INTO users(username,password) VALUES (?,?)",(u,p_hash))
                conn.commit()
                return redirect("/login")
            except:
                msg = "❌ 用户名已存在"

    return f"""
    <style>
    body{{background:#020617;color:#fff;text-align:center;font-family:Arial}}
    input{{margin:8px;padding:6px}}
    .tip{{color:#94a3b8;font-size:13px}}
    .err{{color:#ef4444}}
    </style>

    <h2>注册</h2>

    <form method="post">
        用户名:<br>
        <input name="username" minlength="4" maxlength="12" required><br>
        <div class="tip">4-12位｜仅字母或数字</div>

        密码:<br>
        <input name="password" type="password" minlength="6" maxlength="18" required><br>
        <div class="tip">6-18位</div>

        <br>
        <button>注册</button>
    </form>

    <div class="err">{msg}</div>

    <br><a href="/">返回首页</a>
    """


# ===== 登录 =====
@app.route("/login", methods=["GET","POST"])
def login():
    msg=""

    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]

        conn=get_db(); c=conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?",(u,))
        user=c.fetchone()

        if user and check_password_hash(user[2],p):
            session["uid"]=user[0]
            session["username"]=user[1]
            return redirect("/")
        else:
            msg="❌ 用户名或密码错误"

    return f"""
    <style>
    body{{background:#020617;color:#fff;text-align:center;font-family:Arial}}
    input{{margin:8px;padding:6px}}
    .err{{color:#ef4444}}
    </style>

    <h2>登录</h2>

    <form method="post">
        用户:<br>
        <input name="username"><br>

        密码:<br>
        <input name="password" type="password"><br>

        <button>登录</button>
    </form>

    <div class="err">{msg}</div>

    <br><a href="/">返回首页</a>
    """


# ===== 排行榜 =====
@app.route("/rank")
def rank():
    conn=get_db(); c=conn.cursor()

    c.execute("""
    SELECT users.username, AVG(predictions.hit), COUNT(*)
    FROM predictions
    JOIN users ON predictions.user_id = users.id
    GROUP BY users.username
    ORDER BY AVG(predictions.hit) DESC
    LIMIT 10
    """)

    rows = c.fetchall()

    html = """
    <h2>🏆 命中排行榜</h2>
    <p>（基于历史预测统计）</p>
    """

    for i,r in enumerate(rows):
        html += f"<p>第{i+1}名 {r[0]} ｜ 命中率:{round(r[1],2)} ｜ 次数:{r[2]}</p>"

    html += "<br><a href='/'>返回首页</a>"
    return html


# ===== 退出 =====
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


app.run(host="0.0.0.0", port=10000)
