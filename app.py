from flask import Flask, render_template_string
import random

app = Flask(__name__)

def generate_numbers():
    res = []
    for _ in range(3):
        front = sorted(random.sample(range(1,36),5))
        back = sorted(random.sample(range(1,13),2))
        res.append({"front": front, "back": back})
    return res

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>DLT V6 Pro</title>
    <style>
        body { font-family: Arial; text-align: center; background:#f5f5f5; }
        h1 { color:#333; }
        .card {
            background:white;
            margin:20px auto;
            padding:20px;
            width:300px;
            border-radius:10px;
            box-shadow:0 0 10px rgba(0,0,0,0.1);
        }
        .num { font-size:20px; margin:5px; }
        button {
            padding:10px 20px;
            font-size:16px;
            background:#007bff;
            color:white;
            border:none;
            border-radius:5px;
        }
    </style>
</head>
<body>
    <h1>🎯 大乐透 V6 Pro</h1>
    <button onclick="location.reload()">刷新推荐</button>
    {% for r in data %}
    <div class="card">
        <div>前区：</div>
        <div class="num">{{ r.front }}</div>
        <div>后区：</div>
        <div class="num">{{ r.back }}</div>
    </div>
    {% endfor %}
</body>
</html>
"""

@app.route("/")
def home():
    data = generate_numbers()
    return render_template_string(HTML, data=data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
