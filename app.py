from flask import Flask, render_template_string, session
import requests, re, random, json, os
from collections import Counter

app = Flask(__name__)
app.secret_key = "v23"

MODEL_FILE = "model.json"

# ===== 开奖数据 =====
def fetch():
    try:
        html = requests.get("https://www.lottery.gov.cn/kj/kjlb.html?dlt").text
        nums = re.findall(r'\d{2}', html)

        res=[]
        for i in range(0,700,7):
            f=list(map(int, nums[i:i+5]))
            b=list(map(int, nums[i+5:i+7]))
            res.append({"front":f,"back":b})

        return res
    except:
        return [{"front":[3,8,15,22,30],"back":[2,9]}]*50

# ===== 专家数据 =====
def fetch_experts():
    return [
        {"name":"专家A","nums":[3,8,12,22,30]},
        {"name":"专家B","nums":[5,9,18,25,33]},
        {"name":"专家C","nums":[1,7,15,20,28]}
    ]

# ===== AI概率模型 =====
def ai_model(history):
    all_nums=[n for h in history for n in h["front"]]
    freq=Counter(all_nums)

    score={}
    for i in range(1,36):
        score[i]=freq.get(i,0)

    return sorted(score, key=score.get, reverse=True)

# ===== 读取模型 =====
def load_model():
    if os.path.exists(MODEL_FILE):
        return json.load(open(MODEL_FILE))
    return {"A":1.0,"B":1.0,"C":1.0,"AI":1.0}

# ===== 保存模型 =====
def save_model(m):
    json.dump(m, open(MODEL_FILE,"w"))

# ===== 强化学习更新 =====
def update_model(model, hit_score):
    for k in model:
        if hit_score >= 3:
            model[k] += 0.2
        elif hit_score == 2:
            model[k] += 0.05
        else:
            model[k] -= 0.05

        model[k] = max(0.1, model[k])  # 防止负数

    return model

# ===== 融合 =====
def fusion(history, model):
    experts = fetch_experts()
    ai_nums = ai_model(history)[:10]

    pool=[]

    for i,e in enumerate(experts):
        weight = list(model.values())[i]
        pool += e["nums"] * int(weight)

    pool += ai_nums * int(model["AI"])

    return sorted(random.sample(list(set(pool)),5))

# ===== 页面 =====
HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{
background:linear-gradient(135deg,#0f172a,#1e293b);
color:white;text-align:center;font-family:Arial;}
.card{
background:#1e293b;margin:12px;padding:15px;border-radius:14px;}
.ball{
display:inline-block;background:#ef4444;
padding:10px;margin:4px;border-radius:50%;}
</style>
</head>

<body>

<h2>🎯 大乐透 V23 自进化系统</h2>
<h3>👤 {{ user }}</h3>

<div class="card">
<h3>最新开奖</h3>
{{ latest.front }}
</div>

<div class="card">
<h3>模型权重（AI进化中）</h3>
{{ model }}
</div>

<div class="card">
<h3>推荐号码</h3>
{% for n in rec %}
<span class="ball">{{n}}</span>
{% endfor %}
</div>

</body>
</html>
"""

@app.route("/")
def home():
    user=session.get("user","游客")

    history=fetch()
    latest=history[0]

    model = load_model()

    rec = fusion(history, model)

    # ===== 用上一期训练 =====
    last_real = history[0]["front"]
    hit_score = len(set(rec)&set(last_real))

    model = update_model(model, hit_score)
    save_model(model)

    return render_template_string(HTML,
        user=user,
        latest=latest,
        rec=rec,
        model=model
    )

app.run(host="0.0.0.0", port=10000)
