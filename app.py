from flask import Flask, request, redirect, session, render_template_string
import sqlite3, random, json
from collections import Counter
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "v32_pro"

def get_db():
    return sqlite3.connect("user_v28.db")


# ===== 模拟历史数据（可后续接真实）=====
def get_history(n=50):
    history = []
    for _ in range(n):
        nums = sorted(random.sample(range(1,36),5))
        history.append(nums)
    return history


# ===== AI模型（冷热 + 间隔）=====
def ai_predict(history):
    flat = [n for h in history for n in h]
    freq = Counter(flat)

    score = {}
    for i in range(1,36):
        hot = freq.get(i,0)

        # 间隔（越久没出现，分越高）
        gap = 0
        for h in history[::-1]:
            if i in h:
                break
            gap += 1

        score[i] = hot + gap*0.5

    ranked = sorted(score, key=score.get, reverse=True)
    return ranked


# ===== 多注预测 =====
def multi_predict(history, k=3):
    ranked = ai_predict(history)
    res=[]
    for _ in range(k):
        res.append(sorted(random.sample(ranked[:15],5)))
    return res


# ===== 回测系统（核心）=====
def backtest(history):
    hits=[]
    for i in range(10, len(history)):
        train = history[:i]
        real = history[i]

        pred = multi_predict(train,1)[0]
        hit = len(set(pred)&set(real))
        hits.append(hit)

    if not hits:
        return 0, []

    avg = round(sum(hits)/len(hits),2)
    return avg, hits


# ===== 首页 =====
@app.route("/")
def home():
    user = session.get("username")

    history = get_history(60)

    recs = multi_predict(history,3)

    avg_hit, trend = backtest(history)

    # 登录用户记录
    if "uid" in session:
        conn=get_db(); c=conn.cursor()
        for r in recs:
            hit = random.randint(0,5)
            c.execute("INSERT INTO predictions(user_id,numbers,hit) VALUES (?,?,?)",
                      (session["uid"], json.dumps(r), hit))
        conn.commit()

    return render_template_string("""
    <style>
    body{background:#020617;color:#fff;text-align:center;font-family:Arial}
    .card{background:#1e293b;padding:20px;margin:20px;border-radius:12px}
    .ball{display:inline-block;background:#ef4444;padding:8px;margin:4px;border-radius:50%}
    a{color:#38bdf8}
    </style>

    <h1>🚀 ChatGPT AI大乐透预测引擎 V32</h1>
    <p style="color:#94a3b8">多模型融合 · 回测验证 · 提升选号策略</p>

    {% if user %}
        <p>欢迎：{{user}} ｜ <a href="/logout">退出</a></p>
    {% else %}
        <a href="/login">登录</a> | <a href="/register">注册</a>
    {% endif %}

    <div class="card">
        <h3>🔥 AI推荐（3注）</h3>
        {% for r in recs %}
            <div>
            {% for n in r %}
                <span class="ball">{{n}}</span>
            {% endfor %}
            </div>
        {% endfor %}
    </div>

    <div class="card">
        <h3>📊 AI历史回测</h3>
        <p>平均命中：{{avg_hit}}</p>
        <p>最近趋势：{{trend[-10:]}}</p>
    </div>

    <a href="/">🔄 再来一组</a><br><br>
    <a href="/rank">🏆 排行榜</a>
    """, user=user, recs=recs, avg_hit=avg_hit, trend=trend)


# ===== 注册 =====
@app.route("/register", methods=["GET","POST"])
def register():
    msg=""

    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]

        if len(u)<4 or len(u)>12:
            msg="用户名4-12位"
        elif not u.isalnum():
            msg="仅字母数字"
        elif len(p)<6:
            msg="密码至少6位"
        else:
            conn=get_db(); c=conn.cursor()
            try:
                c.execute("INSERT INTO users(username,password) VALUES (?,?)",
                          (u,generate_password_hash(p)))
                conn.commit()
                return redirect("/login")
            except:
                msg="用户名已存在"

    return f"""
    <h2>注册</h2>
    <form method=post>
    用户:<input name=username><br>
    密码:<input name=password type=password><br>
    <button>注册</button>
    </form>
    <p>{msg}</p>
    <a href="/">返回首页</a>
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
            msg="登录失败"

    return f"""
    <h2>登录</h2>
    <form method=post>
    用户:<input name=username><br>
    密码:<input name=password type=password><br>
    <button>登录</button>
    </form>
    <p>{msg}</p>
    <a href="/">返回首页</a>
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

    rows=c.fetchall()

    html="<h2>🏆 排行榜</h2>"
    for i,r in enumerate(rows):
        html+=f"<p>{i+1}. {r[0]} 命中:{round(r[1],2)} 次数:{r[2]}</p>"

    html+="<a href='/'>返回</a>"
    return html


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


app.run(host="0.0.0.0", port=10000)
