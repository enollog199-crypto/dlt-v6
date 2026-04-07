from flask import Flask, render_template_string, request, redirect, session
import sqlite3, requests, re, random
from collections import Counter

app = Flask(__name__)
app.secret_key = "dlt_secret"

# ===== 初始化用户数据库 =====
def init_user_db():
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

init_user_db()

# ===== 抓数据 =====
def fetch():
    html = requests.get("https://www.lottery.gov.cn/zst/dlt/").text
    nums = re.findall(r'\d{2}', html)

    res=[]
    i=0
    while i+6<len(nums) and len(res)<30:
        f=[int(x) for x in nums[i:i+5]]
        b=[int(x) for x in nums[i+5:i+7]]
        res.append({"front":f,"back":b})
        i+=7
    return res

# ===== AI评分 =====
def score_model(h):
    total=Counter()
    recent=Counter()

    for i,x in enumerate(h):
        total.update(x["front"])
        if i<10:
            recent.update(x["front"])

    score={}
    for i in range(1,36):
        score[i]=total[i]*0.6 + recent[i]*0.4
    return score

# ===== 选号 =====
def pick(score):
    nums=sorted(score.items(), key=lambda x:x[1], reverse=True)
    pool=[x[0] for x in nums[:20]]
    return sorted(random.sample(pool,5)), sorted(random.sample(range(1,13),2))

# ===== 主逻辑 =====
def run():
    h=fetch()
    latest=h[0]
    score=score_model(h)

    rec=[]
    for _ in range(3):
        f,b=pick(score)
        rec.append({"front":f,"back":b})

    return latest,rec

# ===== 注册 =====
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]

        conn=sqlite3.connect("user.db")
        c=conn.cursor()
        c.execute("INSERT INTO users(username,password) VALUES(?,?)",(u,p))
        conn.commit()
        conn.close()

        return redirect("/login")

    return '''
    <h2>注册</h2>
    <form method="post">
    用户名<input name="username"><br>
    密码<input name="password"><br>
    <button>注册</button>
    </form>
    '''

# ===== 登录 =====
@app.route("/login", methods=["GET","POST"])
def login():
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

    return '''
    <h2>登录</h2>
    <form method="post">
    用户名<input name="username"><br>
    密码<input name="password"><br>
    <button>登录</button>
    </form>
    '''

# ===== 首页 =====
HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{background:#0f172a;color:white;text-align:center;font-family:Arial;}
.card{background:#1e293b;margin:10px;padding:15px;border-radius:12px;}
.btn{background:#22c55e;padding:10px;border-radius:10px;display:inline-block;margin-top:10px;}
</style>
</head>

<body>

<h2>🎯 大乐透 V17</h2>
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
<div>{{ r.front }} + {{ r.back }}</div>
{% endfor %}
</div>

<div class="btn" onclick="location.reload()">刷新</div>

</body>
</html>
"""

@app.route("/")
def home():
    latest,rec = run()
    user = session.get("user", "游客")
    return render_template_string(HTML, latest=latest, rec=rec, user=user)

app.run(host="0.0.0.0", port=10000)
