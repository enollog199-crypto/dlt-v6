from flask import Flask, render_template, session
import requests, re, json, os
from datetime import datetime

app = Flask(__name__, template_folder="web")
app.secret_key = "v41_ai"

CACHE_FILE = "latest.json"

# ===== 获取真实开奖数据（带期号+日期）=====
def fetch_latest_real():
    sources = []

    # ===== 数据源1（500彩票网结构稳定）=====
    try:
        url = "https://datachart.500.com/dlt/history/newinc/history.php"
        html = requests.get(url, timeout=5).text

        rows = re.findall(r'<tr class="t_tr1">(.*?)</tr>', html, re.S)

        data=[]
        for row in rows[:20]:
            tds = re.findall(r'<td.*?>(.*?)</td>', row)

            period = tds[0]
            date = tds[1]

            nums = re.findall(r'\d{2}', "".join(tds[2:9]))
            red = list(map(int, nums[:5]))
            blue = list(map(int, nums[5:7]))

            data.append({
                "period": period,
                "date": date,
                "red": red,
                "blue": blue
            })

        sources.append(data)
    except:
        pass

    # ===== 数据源2（备用）=====
    try:
        url = "https://www.78500.cn/dlt/"
        html = requests.get(url, timeout=5).text

        matches = re.findall(r'(\d{7}).*?(\d{2}\-\d{2}).*?((?:\d{2}\s){6}\d{2})', html)

        data=[]
        for m in matches[:20]:
            period=m[0]
            date="2026-"+m[1]
            nums=list(map(int,m[2].split()))

            data.append({
                "period":period,
                "date":date,
                "red":nums[:5],
                "blue":nums[5:]
            })

        sources.append(data)
    except:
        pass

    # ===== 数据校验（取一致数据）=====
    if len(sources) >= 2:
        for i in range(min(len(sources[0]), len(sources[1]))):
            if sources[0][i]["red"] == sources[1][i]["red"]:
                return sources[0][i]

    # ===== fallback =====
    if sources:
        return sources[0][0]

    return None

# ===== 时间校验（是否最新）=====
def is_latest_valid(data):
    if not data:
        return False

    today = datetime.now()

    # 大乐透开奖日：周一/三/六
    if today.weekday() not in [0,2,5]:
        return True  # 非开奖日，当前数据就是最新

    # 简单校验日期是否<=今天
    try:
        draw_date = datetime.strptime(data["date"], "%Y-%m-%d")
        return draw_date <= today
    except:
        return True

# ===== 安全获取（带缓存）=====
def get_latest():
    try:
        data = fetch_latest_real()
        if is_latest_valid(data):
            json.dump(data, open(CACHE_FILE,"w"))
            return data
    except:
        pass

    if os.path.exists(CACHE_FILE):
        return json.load(open(CACHE_FILE))

    return {
        "period":"未知",
        "date":"未知",
        "red":[0,0,0,0,0],
        "blue":[0,0]
    }

# ===== 首页 =====
@app.route("/")
def home():
    latest = get_latest()

    return render_template("index.html",
        user=session.get("username"),
        data=latest
    )

# ===== 启动 =====
import os
port=int(os.environ.get("PORT",10000))
app.run(host="0.0.0.0",port=port)
