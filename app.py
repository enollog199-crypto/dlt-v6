from flask import Flask, render_template_string
import requests
import re
import random
from collections import Counter, defaultdict

app = Flask(__name__)

# =========================
# 1. 官方开奖数据
# =========================
def fetch_history(limit=60):
    url = "https://www.lottery.gov.cn/zst/dlt/"
    try:
        html = requests.get(url, timeout=10).text
        nums = re.findall(r'\d{2}', html)

        history = []
        i = 0
        while i + 6 < len(nums) and len(history) < limit:
            front = sorted([int(x) for x in nums[i:i+5]])
            back = sorted([int(x) for x in nums[i+5:i+7]])
            history.append({"front": front, "back": back})
            i += 7

        return history
    except:
        return []

# =========================
# 2. 专家推荐抓取（简化版）
# =========================
def fetch_experts():
    sources = [
        "https://www.ydniu.com/experts/dlt",
        "https://www.zhcw.com/czfw/sjfx/dlt/"
    ]

    expert_numbers = []

    for url in sources:
        try:
            html = requests.get(url, timeout=10).text
            nums = re.findall(r'\b\d{1,2}\b', html)

            # 简单抽取组合（真实环境可优化）
            for i in range(0, min(len(nums)-5, 50), 5):
                pick = [int(n) for n in nums[i:i+5] if int(n) <= 35]
                if len(pick) == 5:
                    expert_numbers.append(sorted(pick))
        except:
            continue

    return expert_numbers

# =========================
# 3. 专家评分
# =========================
def score_experts(history, experts):
    scores = []

    for ex in experts:
        hit_total = 0
        count = 0

        for h in history[-20:]:
            hit = len(set(ex) & set(h["front"]))
            hit_total += hit
            count += 1

        avg = hit_total / count if count else 0
        scores.append((ex, avg))

    # 按命中率排序
    scores.sort(key=lambda x: x[1], reverse=True)

    return scores[:5]  # 取Top5专家

# =========================
# 4. 热冷号
# =========================
def analyze(history):
    counter = Counter()
    for h in history:
        counter.update(h["front"])

    hot = [k for k,v in counter.items() if v >= 2]
    cold = [i for i in range(1,36) if i not in counter]

    return hot, cold

# =========================
# 5. 融合选号（核心）
# =========================
def generate_one(top_experts, hot, cold):
    pick = []

    # 专家号（权重高）
    if top_experts:
        pick += random.sample(top_experts[0][0], 2)

    # 热号
    if len(hot) >= 2:
        pick += random.sample(hot, 2)

    # 冷号
    if cold:
        pick += random.sample(cold, 1)

    # 去重补齐
    pick = list(set(pick))
    while len(pick) < 5:
        n = random.randint(1,35)
        if n not in pick:
            pick.append(n)

    front = sorted(pick[:5])
    back = sorted(random.sample(range(1,13),2))

    return front, back

# =========================
# 6. 回测
# =========================
def backtest(history):
    hits = []

    for i in range(20, len(history)-1):
        train = history[:i]
        test = history[i]

        hot, cold = analyze(train)
        front, _ = generate_one([], hot, cold)

        hit = len(set(front) & set(test["front"]))
        hits.append(hit)

    return round(sum(hits)/len(hits),2) if hits else 0

# =========================
# 7. 策略判断
# =========================
def strategy(avg):
    if avg >= 2:
        return "🔥 强势（专家+热号有效）"
    elif avg >= 1:
        return "⚖️ 稳健（均衡策略）"
    else:
        return "❄️ 防守（降低风险）"

# =========================
# 8. 主流程
# =========================
def run():
    history = fetch_history()
    experts = fetch_experts()

    if not history:
        return [], "❌ 数据异常", 0

    top_experts = score_experts(history, experts)
    hot, cold = analyze(history)
    avg = backtest(history)
    state = strategy(avg)

    rec = []
    for _ in range(3):
        f,b = generate_one(top_experts, hot, cold)
        rec.append({"front": f, "back": b})

    return rec, state, avg, top_experts

# =========================
# 9. 页面
# =========================
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>DLT V7 Pro</title>
</head>
<body style="text-align:center;font-family:Arial;">
    <h1>🎯 大乐透 V7 专家融合系统</h1>

    <h3>策略：{{ state }}</h3>
    <h3>平均命中：{{ avg }}</h3>

    <button onclick="location.reload()">🔄 更新</button>

    <h3>🏆 Top专家：</h3>
    {% for e in experts %}
        <div>{{ e[0] }}（命中：{{ "%.2f"|format(e[1]) }}）</div>
    {% endfor %}

    <hr>

    {% for r in data %}
    <div style="margin:20px;">
        前区：{{ r.front }}<br>
        后区：{{ r.back }}
    </div>
    {% endfor %}
</body>
</html>
"""

@app.route("/")
def home():
    data, state, avg, experts = run()
    return render_template_string(HTML, data=data, state=state, avg=avg, experts=experts)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
