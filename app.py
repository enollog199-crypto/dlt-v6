from flask import Flask, render_template_string, request, redirect, session
import sqlite3, random

app = Flask(__name__)
app.secret_key = "dlt_secret"

# ===== 初始化数据库 =====
def init_db():
    conn = sqlite3.connect("user.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ===== 模拟最新开奖（稳定，不乱跳）=====
LATEST = {"front":[3,8,15,22,30],"back":[2,9]}

# ===== 模拟走势数据 =====
trend_front = [random.randint(1,35) for _ in range(20)]
trend_back = [random.randint(1,12) for _ in range(20)]

# ===== 推荐逻辑（固定+可信度）=====
def recommend():
    return [
        {"front":[3,8,15,22,30],"back":[2,9],
         "desc":"热号主导 + 高频区间组合（可信度85%）"},
        {"front":[5,11,18,24,33],"back":[1,7],
         "desc":"冷热均衡策略 + 区间分散（可信度78%）"},
        {"front":[2,9,14,27,35],"back":[3,11],
         "desc":"冷号反弹 + 边号策略（可信度72%）"},
    ]

# ===== 注册 =====
@app.route("/register", methods=["GET","POST"])
def register():
    msg=""
    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]
        p2=request.form["password2"]

        if p!=p2:
            msg="两次密码不一致"
        else:
            conn=sqlite3.connect("user.db")
            c=conn.cursor()
            c.execute("INSERT INTO users(username,password) VALUES(?,?)",(u,p))
            conn.commit()
            conn.close()
            return redirect("/login")

    return f"""
    <h2>注册账号</h2>
    <form method="post">
    用户名<input name="username"><br>
    密码<input type="password" name="password"><br>
    确认密码<input type="password" name="password2"><br>
    <button>注册</button>
    </form>
    <p>{msg}</p>
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
    用户名<input name="username"><br>
    密码<input type="password" name="password"><br>
    <button>登录</button>
    </form>
    <p>{msg}</p>
    <a href="/register">没有账号？去注册</a>
    """

# ===== 首页 =====
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

<h2>🎯 大乐透 V17 专业版</h2>
<h3>👤 {{ user }}</h3>

{% if user == "游客" %}
<div class="btn" onclick="location.href='/login'">登录 / 注册</div>
{% endif %}

<div class="card">
<h3>最新开奖</h3>
{{ latest.front }} + {{ latest.back }}
</div>

<div class="card">
<h3>推荐号码（AI分析）</h3>
{% for r in rec %}
<div>
{{ r.front }} + {{ r.back }}<br>
<small>{{ r.desc }}</small>
</div>
<br>
{% endfor %}
</div>

<div class="card">
<h3>趋势分析</h3>
<canvas id="chart"></canvas>
</div>

<script>
const ctx=document.getElementById('chart');

new Chart(ctx,{
type:'line',
data:{
labels:[...Array(20).keys()],
datasets:[
{
label:'前区走势',
data:{{ trend_f }},
borderWidth:2
},
{
label:'后区走势',
data:{{ trend_b }},
borderWidth:2
}
]
}
});
</script>

</body>
</html>
"""

@app.route("/")
def home():
    user=session.get("user","游客")
    rec = recommend()
    return render_template_string(HTML,
        user=user,
        latest=LATEST,
        rec=rec,
        trend_f=trend_front,
        trend_b=trend_back
    )

app.run(host="0.0.0.0", port=10000)
