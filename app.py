from flask import Flask, render_template_string
import random, json, os
from collections import Counter
from datetime import datetime

app = Flask(__name__)

RECORD_FILE = "records.json"


# ===== 模型 =====
def ai_model(history):
    nums=[n for h in history for n in h]
    freq=Counter(nums)
    pool=[]
    for i in range(1,36):
        pool += [i]*max(1,freq.get(i,1))
    return sorted(random.sample(list(set(pool)),5))


def expert_model():
    experts=[
        [3,8,12,22,30],
        [5,9,18,25,33],
        [1,7,15,20,28]
    ]
    return random.choice(experts)


def random_model():
    return sorted(random.sample(range(1,36),5))


# ===== 假数据（可替换真实）=====
def get_history():
    return [random.sample(range(1,36),5) for _ in range(50)]


# ===== 记录 =====
def load_records():
    if os.path.exists(RECORD_FILE):
        return json.load(open(RECORD_FILE))
    return []

def save_records(r):
    json.dump(r, open(RECORD_FILE,"w"))


# ===== PK =====
def run_models(history):
    return {
        "AI": ai_model(history),
        "EXPERT": expert_model(),
        "RANDOM": random_model()
    }


def evaluate(models, real):
    hits={}
    for k,v in models.items():
        hits[k]=len(set(v)&set(real))
    return hits


# ===== 排行榜 =====
def leaderboard(records):
    stats={}

    for r in records:
        for m,h in r["hits"].items():
            stats.setdefault(m, {"total":0,"max":0,"win":0,"count":0})
            stats[m]["total"]+=h
            stats[m]["count"]+=1
            stats[m]["max"]=max(stats[m]["max"],h)

        # 谁赢
        max_hit=max(r["hits"].values())
        for m,h in r["hits"].items():
            if h==max_hit:
                stats[m]["win"]+=1

    # 计算平均
    for m in stats:
        stats[m]["avg"]=round(stats[m]["total"]/stats[m]["count"],2)

    return stats


# ===== UI =====
HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{background:#0f172a;color:white;text-align:center;font-family:Arial;}
.card{background:#1e293b;margin:12px;padding:15px;border-radius:14px;}
.ball{display:inline-block;background:#ef4444;padding:8px;margin:3px;border-radius:50%;}
.win{color:#22c55e;font-weight:bold;}
</style>
</head>

<body>

<h2>🏆 大乐透 V27（模型PK排行榜）</h2>

<div class="card">
<h3>本期PK</h3>

{% for k,v in models.items() %}
<div>
<b>{{k}}</b> :
{% for n in v %}
<span class="ball">{{n}}</span>
{% endfor %}
👉 命中 {{ hits[k] }}
</div>
{% endfor %}

</div>

<div class="card">
<h3>排行榜</h3>

{% for k,v in board.items() %}
<div>
<b>{{k}}</b> |
平均: {{v.avg}} |
最高: {{v.max}} |
胜场: <span class="win">{{v.win}}</span>
</div>
{% endfor %}

</div>

</body>
</html>
"""


@app.route("/")
def home():
    history=get_history()
    real=random.choice(history)

    models=run_models(history)
    hits=evaluate(models, real)

    records=load_records()

    issue=datetime.now().strftime("%Y%m%d")

    # 防重复
    if not records or records[-1]["issue"]!=issue:
        records.append({
            "issue":issue,
            "real":real,
            "models":models,
            "hits":hits
        })
        save_records(records)

    board=leaderboard(records)

    return render_template_string(HTML,
        models=models,
        hits=hits,
        board=board
    )


app.run(host="0.0.0.0", port=10000)
