from flask import Flask, render_template
import requests, re, json, os, random
from collections import Counter
from datetime import datetime

app = Flask(__name__, template_folder="web")
app.secret_key = "v46_ai"

PREDICT_FILE="predict.json"
STATS_FILE="stats.json"

# ===== 获取历史 =====
def fetch_history():
    try:
        url="https://datachart.500.com/dlt/history/newinc/history.php"
        html=requests.get(url,timeout=5).text
        rows=re.findall(r'<tr class="t_tr1">(.*?)</tr>',html,re.S)

        history=[]
        for row in rows[:100]:
            nums=re.findall(r'\d{2}',row)
            red=list(map(int,nums[2:7]))
            blue=list(map(int,nums[7:9]))
            history.append({"red":red,"blue":blue})

        return history
    except:
        return []

# ===== 模型 =====
def hot(history):
    c=Counter()
    for h in history: c.update(h["red"])
    return [n for n,_ in c.most_common()]

def cold(history):
    score={}
    for i in range(1,36):
        gap=0
        for h in history:
            if i in h["red"]: break
            gap+=1
        score[i]=gap
    return sorted(score,key=score.get,reverse=True)

def blue_model(history):
    c=Counter()
    for h in history: c.update(h["blue"])
    return [n for n,_ in c.most_common()]

# ===== 生成一注 =====
def gen_one(history):
    h=hot(history)[:10]
    c=cold(history)[:10]

    dan=random.sample(h,2)
    pool=list(set(h+c))
    res=set(dan)

    while len(res)<5:
        res.add(random.choice(pool))

    blue=sorted(random.sample(blue_model(history)[:6],2))

    return {"red":sorted(res),"blue":blue,"dan":dan}

# ===== 多注 =====
def gen_multi(history):
    result=[]
    while len(result)<3:
        p=gen_one(history)
        if all(len(set(p["red"]) & set(r["red"]))<3 for r in result):
            result.append(p)
    return result

# ===== 命中 =====
def hit(p,r):
    return len(set(p["red"])&set(r["red"])) + \
           len(set(p["blue"])&set(r["blue"]))

# ===== 投注策略 =====
def bet_strategy(last_hit):
    if last_hit >=3:
        return 1
    elif last_hit==2:
        return 2
    else:
        return 3

# ===== 统计 =====
def load_stats():
    if os.path.exists(STATS_FILE):
        return json.load(open(STATS_FILE))
    return {"cost":0,"win":0,"round":0,"last_hit":0}

def save_stats(s):
    json.dump(s,open(STATS_FILE,"w"))

# ===== 锁定预测 =====
def get_prediction(history):
    today=str(datetime.now().date())

    if os.path.exists(PREDICT_FILE):
        data=json.load(open(PREDICT_FILE))
        if data["date"]==today:
            return data

    preds=gen_multi(history)

    data={"date":today,"preds":preds}
    json.dump(data,open(PREDICT_FILE,"w"))
    return data

# ===== 首页 =====
@app.route("/")
def home():
    history=fetch_history()
    latest=history[0] if history else {"red":[],"blue":[]}

    pred_data=get_prediction(history)
    stats=load_stats()

    preds=[]
    total_hit=0

    for p in pred_data["preds"]:
        h=hit(p,latest)
        total_hit+=h
        preds.append({
            "red":p["red"],
            "blue":p["blue"],
            "dan":p["dan"],
            "hit":h
        })

    # ===== 更新统计 =====
    bet=bet_strategy(stats["last_hit"])

    stats["round"]+=1
    stats["cost"]+=bet*6  # 每注2元，3注=6元
    stats["win"]+=total_hit*2  # 简化收益模型
    stats["last_hit"]=total_hit

    save_stats(stats)

    roi = round((stats["win"]-stats["cost"])/stats["cost"],2) if stats["cost"]>0 else 0

    return render_template("index.html",
        latest=latest,
        preds=preds,
        bet=bet,
        stats=stats,
        roi=roi
    )

# ===== 启动 =====
import os
port=int(os.environ.get("PORT",10000))
app.run(host="0.0.0.0",port=port)
