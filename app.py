from flask import Flask, render_template
import requests, re, random
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

# ===== 模型 =====
def hot(history):
    c=Counter()
    for h in history: c.update(h["red"])
    return [n for n,_ in c.most_common()]

def blue_hot(history):
    c=Counter()
    for h in history: c.update(h["blue"])
    return [n for n,_ in c.most_common()]

# ===== 区间选择 =====
def pick_by_zone():
    low=random.sample(range(1,13),2)
    mid=random.sample(range(13,25),2)
    high=random.sample(range(25,36),1)
    return low+mid+high

# ===== 奇偶控制 =====
def adjust_odd_even(nums):
    odd=[n for n in nums if n%2==1]
    even=[n for n in nums if n%2==0]

    if len(odd)<2:
        nums[random.randint(0,4)] +=1
    return nums

# ===== 连号 =====
def add_consecutive(nums):
    a=random.randint(1,34)
    nums[0]=a
    nums[1]=a+1
    return nums

# ===== 杀号 =====
def kill(history):
    freq=Counter()
    for h in history: freq.update(h["red"])
    low=[n for n,_ in freq.most_common()][-10:]
    return low

# ===== 生成预测 =====
def gen(history):
    base=pick_by_zone()

    base=adjust_odd_even(base)

    if random.random()>0.5:
        base=add_consecutive(base)

    base=list(set(base))

    while len(base)<5:
        base.append(random.randint(1,35))

    # 去杀号
    k=kill(history)
    base=[n for n in base if n not in k]

    while len(base)<5:
        base.append(random.randint(1,35))

    red=sorted(base[:5])

    blue=sorted(random.sample(blue_hot(history)[:8],2))

    return {"red":red,"blue":blue,"kill":k[:5]}

# ===== 命中 =====
def hit(p,r):
    return len(set(p["red"])&set(r["red"])) + \
           len(set(p["blue"])&set(r["blue"]))

# ===== 首页 =====
@app.route("/")
def home():
    history=fetch_history()
    latest=history[0]

    pred=gen(history)

    h=hit(pred,latest)

    return render_template("index.html",
        latest=latest,
        pred=pred,
        hit=h
    )

# ===== 启动 =====
import os
port=int(os.environ.get("PORT",10000))
app.run(host="0.0.0.0",port=port)
