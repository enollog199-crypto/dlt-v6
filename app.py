from flask import Flask, render_template, request
import requests, re, random, sqlite3
from collections import Counter

app = Flask(__name__, template_folder="web")

# ===== 数据 =====
def fetch_history():
    url="https://datachart.500.com/dlt/history/newinc/history.php"
    html=requests.get(url).text
    rows=re.findall(r'<tr class="t_tr1">(.*?)</tr>',html,re.S)

    data=[]
    for row in rows[:50]:
        tds=re.findall(r'<td.*?>(.*?)</td>',row)

        period=tds[0]
        red=list(map(int,re.findall(r'\d{2}',"".join(tds[2:7]))))
        blue=list(map(int,re.findall(r'\d{2}',"".join(tds[7:9]))))

        data.append({"period":period,"red":red,"blue":blue})

    return data

# ===== 数据库 =====
def init_db():
    conn = sqlite3.connect("dlt.db")
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS predictions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        red TEXT,
        blue TEXT,
        hit INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()

def save_prediction(pred):
    conn = sqlite3.connect("dlt.db")
    c = conn.cursor()

    c.execute("""
    INSERT INTO predictions (red, blue, hit)
    VALUES (?, ?, ?)
    """, (
        ",".join(map(str,pred["red"])),
        ",".join(map(str,pred["blue"])),
        pred.get("hit",0)
    ))

    conn.commit()
    conn.close()

def get_records():
    conn = sqlite3.connect("dlt.db")
    c = conn.cursor()

    rows = c.execute("SELECT red, blue, hit FROM predictions ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()

    return [{"red":r[0],"blue":r[1],"hit":r[2]} for r in rows]

# ===== 基础 =====
def hot(history):
    c=Counter()
    for h in history: c.update(h["red"])
    return [n for n,_ in c.most_common()]

def blue_hot(history):
    c=Counter()
    for h in history: c.update(h["blue"])
    return [n for n,_ in c.most_common()]

def pick_by_zone():
    return random.sample(range(1,13),2)+random.sample(range(13,25),2)+random.sample(range(25,36),1)

def adjust_odd_even(nums):
    if sum(n%2 for n in nums)<2:
        nums[random.randint(0,4)] +=1
    return nums

def add_consecutive(nums):
    a=random.randint(1,34)
    nums[0]=a
    nums[1]=a+1
    return nums

def kill(history):
    freq=Counter()
    for h in history: freq.update(h["red"])
    return [n for n,_ in freq.most_common()][-10:]

# ===== AI =====
def evaluate_features(nums, history):
    reds = nums["red"]
    hot_nums = hot(history)[:10]
    cold_nums = hot(history)[-10:]

    f={}
    f["hot"]=len([n for n in reds if n in hot_nums])
    f["cold"]=len([n for n in reds if n in cold_nums])

    low=len([n for n in reds if n<=12])
    mid=len([n for n in reds if 13<=n<=24])
    high=len([n for n in reds if n>=25])
    f["zone"]=1 if (low>=1 and mid>=2 and high>=1) else 0

    odd=sum(n%2 for n in reds)
    f["odd_even"]=1 if 2<=odd<=3 else 0

    reds=sorted(reds)
    f["consecutive"]=sum(1 for i in range(len(reds)-1) if reds[i]+1==reds[i+1])

    return f

def train_weights(history):
    weights={k:1.0 for k in ["hot","cold","zone","odd_even","consecutive"]}
    score_board={k:0 for k in weights}

    for i in range(1,20):
        past=history[i:]
        real=history[i-1]

        for _ in range(20):
            combo=gen_single(past)
            f=evaluate_features(combo,past)
            h=hit(combo,real)

            for k in weights:
                score_board[k]+=f[k]*h

    total=sum(score_board.values())+0.0001
    for k in weights:
        weights[k]=score_board[k]/total

    return weights

def apply_strategy(weights,mode):
    if mode=="aggressive":
        weights["hot"]*=1.5
        weights["consecutive"]*=1.5
    elif mode=="stable":
        weights["zone"]*=1.5
        weights["odd_even"]*=1.5
    elif mode=="cold":
        weights["cold"]*=2
    return weights

def score_with_weights(nums, history, weights):
    f=evaluate_features(nums,history)
    return sum(f[k]*weights[k] for k in weights)

def gen_single(history):
    base=pick_by_zone()
    base=adjust_odd_even(base)

    if random.random()>0.5:
        base=add_consecutive(base)

    base=list(set(base))

    while len(base)<5:
        base.append(random.randint(1,35))

    k=kill(history)
    base=[n for n in base if n not in k]

    while len(base)<5:
        base.append(random.randint(1,35))

    return {
        "red":sorted(base[:5]),
        "blue":sorted(random.sample(blue_hot(history)[:10],2)),
        "dan":sorted(random.sample(base[:5],2)),
        "kill":k[:5]
    }

def gen(history,mode="stable"):
    weights=apply_strategy(train_weights(history),mode)

    candidates=[]
    for _ in range(100):
        c=gen_single(history)
        s=score_with_weights(c,history,weights)
        candidates.append((s,c))

    candidates.sort(reverse=True,key=lambda x:x[0])
    return [c[1] for c in candidates[:3]],weights

def hit(p,r):
    return len(set(p["red"])&set(r["red"]))+len(set(p["blue"])&set(r["blue"]))

def backtest(history):
    res=[]
    for i in range(10,len(history)):
        past=history[i:]
        real=history[i-1]
        preds,_=gen(past)
        res.append(max(hit(p,real) for p in preds))
    return res

# ===== 路由 =====
@app.route("/",methods=["GET","POST"])
def home():
    init_db()

    history=fetch_history()
    latest=history[0]

    mode=request.form.get("mode","stable")

    preds,weights=gen(history,mode)

    for p in preds:
        p["hit"]=hit(p,latest)
        save_prediction(p)

    records=get_records()
    results=backtest(history[:30])

    return render_template("index.html",
        latest=latest,
        preds=preds,
        weights=weights,
        records=records,
        results=results,
        mode=mode
    )

import os
port=int(os.environ.get("PORT",10000))
app.run(host="0.0.0.0",port=port)
