from flask import Flask, render_template_string, request, redirect, session
import sqlite3, requests, re
from collections import Counter

app = Flask(__name__)
app.secret_key = "dlt_v18_secret"

# ===== 数据库初始化 =====
def init_db():
    conn = sqlite3.connect("user.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ===== 获取真实开奖（简化版）=====
def fetch_data():
    try:
        html = requests.get("https://www.lottery.gov.cn/kj/kjlb.html?dlt", timeout=5).text
        nums = re.findall(r'\d{2}', html)

        front = list(map(int, nums[:5]))
        back = list(map(int, nums[5:7]))

        return {"front": front, "back": back}
    except:
        return {"front":[3,8,15,22,30],"back":[2,9]}

# ===== AI推荐（频率模型）=====
def recommend():
    history = []

    try:
        html = requests.get("https://www.lottery.gov.cn/kj/kjlb.html?dlt").text
        nums = re.findall(r'\d{2}', html)

        for i in range(0, 140, 7):
            f = list(map(int, nums[i:i+5]))
            history.extend(f)
    except:
        history = [3,8,15,22,30]*10

    count = Counter(history)

    hot = [x[0] for x in count.most_common(10)]

    return [
        {"front":sorted(hot[:5]),"back":[2,9],
         "desc":"高频热号组合（稳定型策略）"},
        {"front":sorted(hot[5:10]),"back":[1,7],
         "desc":"次热号分散组合（平衡策略）"},
        {"front":sorted(set(range(1,36))-set(hot[:10]))[:5],"back":[3,11],
         "desc":"冷号反弹策略（高风险高收益）"},
    ]

# ===== 注册 =====
@app.route("/register", methods=["GET","POST"])
def register():
    msg=""

    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]
        p2=request.form["password2"]

        if not u or not p:
            msg="请输入完整信息"

        elif p!=p2:
            msg="两次密码不一致"

        else:
            conn=sqlite3.connect("user.db")
            c=conn.cursor()

            try:
                c.execute("INSERT INTO users(username,password) VALUES(?,?)",(u,p))
                conn.commit()
                conn.close()
                return redirect("/login")
            except:
                msg="用户名已存在"

    return f"""
    <h2>注册账号</h2>
    <form method="post">
    用户名:<input name="username"><br>
    密码:<input type="password" name="password"><br>
    确认密码:<input type="password" name="password2"><br>
    <button>注册</button>
    </form>
    <p style='color:red'>{msg}</p>
    <a href="/login">已有账号？去登录</a>
    """

# ===== 登录 =====
@app.route("/login", methods=["GET","POST"])
def login():
    msg=""

    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]

        conn=sqlite3.connect("user.db")
        c=conn.cursor()
        res=c.execute("SELECT * FROM users WHERE username=? AND password=?",(u,p)).fetchone()
        conn.close()

        if res:
            session["user"]=u
            return redirect("/")
        else:
            msg="账号或密码错误"

    return f"""
    <h2>登录</h2>
    <form method="post">
    用户名:<input name="username"><br>
    密码:<input type="password" name="password"><br>
    <button>登录</button>
    </form>
    <p style='color:red'>{msg}</p>
    <a href="/register">没有账号？去注册</a>
    """

# ===== 页面 =====
HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body{background:#0f172a;color:white;text-align:center;font-family:Arial;}
.card{background:#1e293b;margin:10px;padding:15px;border-radius:12px;}
.btn{background:#22c55e;padding:10px;border-radius:10px;display:inline-block;margin-top:10px;}
</style>
</head>

<body>

<h2>🎯 大乐透 V18 真实数据版</h2>
<h3>👤 {{ user }}</h3>

{% if user == "游客" %}
<div class="btn" onclick="location.href='/login'">登录 / 注册</div>
{% endif %}

<div class="card">
<h3>最新开奖</h3>
{{ latest.front }} + {{ latest.back }}
</div>

<div class="card">
<h3>推荐号码</h3>
{% for r in rec %}
<div>
{{ r.front }} + {{ r.back }}<br>
<small>{{ r.desc }}</small>
</div><br>
{% endfor %}
</div>

</body>
</html>
"""

@app.route("/")
def home():
    user=session.get("user","游客")
    latest = fetch_data()
    rec = recommend()

    return render_template_string(HTML,
        user=user,
        latest=latest,
        rec=rec
    )

app.run(host="0.0.0.0", port=10000)
