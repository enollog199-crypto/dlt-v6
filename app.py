from flask import Flask, render_template_string
import sqlite3, random, json, os, requests, re
from collections import Counter
import threading, time

app = Flask(__name__)
app.secret_key = "v34_real_ai_2026_auto"

MODEL_FILE = "model.json"
MODEL_HISTORY_FILE = "model_history.json"
HISTORY_FILE = "history.json"

lock = threading.Lock()

# ===== 数据库 =====
def get_db():
    return sqlite3.connect("user_v28.db")

# ===== 历史数据 =====
def fetch_real_history():
    if os.path.exists(HISTORY_FILE):
        return json.load(open(HISTORY_FILE))
    try:
        html = requests.get("https://www.lottery.gov.cn/kj/kjlb.html?dlt", timeout=5).text
        nums = re.findall(r'\d{2}', html)
        res=[]
        for i in range(0, min(len(nums),700), 7):
            front=list(map(int, nums[i:i+5]))
            res.append(front)
        history = res[:100]
    except:
        history = [sorted(random.sample(range(1,36),5)) for _ in range(60)]
    json.dump(history, open(HISTORY_FILE,"w"))
    return history

# ===== 模型加载/保存 =====
def load_model():
    if os.path.exists(MODEL_FILE):
        return json.load(open(MODEL_FILE))
    return {"freq":0.33,"gap":0.33,"balance":0.34}

def save_model(model):
    json.dump(model, open(MODEL_FILE,"w"))

def load_model_history():
    if os.path.exists(MODEL_HISTORY_FILE):
        return json.load(open(MODEL_HISTORY_FILE))
    return []

def save_model_history(model):
    history = load_model_history()
    history.append(model.copy())
    json.dump(history, open(MODEL_HISTORY_FILE,"w"))

# ===== 模型 =====
def model_freq(history):
    flat = [n for h in history for n in h]
    freq = Counter(flat)
    return sorted(range(1,36), key=lambda x: freq.get(x,0), reverse=True)

def model_gap(history):
    score={}
    for i in range(1,36):
        gap=0
        for h in history[::-1]:
            if i in h: break
            gap+=1
        score[i]=gap
    return sorted(score, key=score.get, reverse=True)

def model_balance(history):
    nums=list(range(1,36))
    random.shuffle(nums)
    return nums

def predict(history, model):
    m_list = {
        "freq": model_freq(history),
        "gap": model_gap(history),
        "balance": model_balance(history)
    }
    score={}
    for i in range(1,36):
        s=0
        for k,v in m_list.items():
            rank=(35 - v.index(i))/35
            s += model[k]*rank
        score[i]=s
    nums, weights = zip(*score.items())
    total=sum(weights)
    probs=[w/total for w in weights]
    numbers = sorted(random.choices(nums, probs, k=5))
    confidence = round(sum(score[n] for n in numbers)/5,3)
    hit = sum([1 for n in numbers if n in history[0]])
    return numbers, confidence, hit

def evaluate_model(history, model):
    hits=[]
    for i in range(20,len(history)):
        train=history[:i]
        real=history[i]
        pred,_ ,_= predict(train, model)
        hits.append(len(set(pred)&set(real)))
    return sum(hits)/len(hits) if hits else 0

def update_model(model, history):
    base_score = evaluate_model(history, model)
    alpha = 0.03
    for k in model:
        temp = model.copy()
        temp[k] += alpha
        s = evaluate_model(history, temp)
        if s > base_score:
            model[k] += alpha
        else:
            model[k] -= alpha/2
    total=sum(model.values())
    for k in model:
        model[k]=round(model[k]/total,3)
    save_model_history(model)
    return model

# ===== 自动预测线程 =====
dynamic_data = {"recs":[],"heatmap":[0]*35,"hits":[],"confs":[],"model":{}}

def auto_predict_loop():
    history = fetch_real_history()
    model = load_model()
    while True:
        with lock:
            model = update_model(model, history)
            save_model(model)
            heatmap=[0]*35
            recs=[]
            hits=[]
            confs=[]
            for _ in range(3):
                numbers, conf, hit = predict(history, model)
                recs.append((numbers, conf))
                for n in numbers:
                    heatmap[n-1]+=1
                hits.append(hit)
                confs.append(conf)
            dynamic_data.update({
                "recs":recs,
                "heatmap":heatmap,
                "hits":hits,
                "confs":confs,
                "model":model
            })
        time.sleep(2)

threading.Thread(target=auto_predict_loop, daemon=True).start()

# ===== 首页 =====
@app.route("/")
def home():
    with lock:
        data = dynamic_data.copy()
    return render_template_string("""
    <html>
    <head>
        <title>V34.6 AI 动态预测</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body{background:#020617;color:#fff;text-align:center;font-family:Arial;}
            .card{background:#1e293b;padding:20px;margin:20px;border-radius:12px;}
            .ball{display:inline-block;background:#ef4444;padding:8px;margin:4px;border-radius:50%}
        </style>
    </head>
    <body>
    <h1>🤖 ChatGPT AI预测系统 V34.6</h1>

    <div class="card">
        <h3>🔥 AI推荐（3注）</h3>
        <div id="predictions"></div>
    </div>

    <div class="card">
        <h3>📊 当前推荐号码热度</h3>
        <canvas id="heatChart" width="800" height="200"></canvas>
    </div>

    <div class="card">
        <h3>📊 模型权重演化趋势</h3>
        <canvas id="modelChart" width="800" height="200"></canvas>
    </div>

    <div class="card">
        <h3>📊 自我预测统计（动态动画）</h3>
        <canvas id="hitTrend" width="800" height="200"></canvas>
    </div>

    <script>
    let dynamicData = {{data|tojson}};

    function renderPredictions(){
        const div = document.getElementById('predictions');
        div.innerHTML="";
        dynamicData.recs.forEach(r=>{
            let html = "";
            r[0].forEach(n=> html += `<span class='ball'>${n}</span>`);
            html += ` （信心: ${r[1]})`;
            div.innerHTML += "<div>"+html+"</div>";
        });
    }
    renderPredictions();

    // 图表初始化
    const heatCtx = document.getElementById('heatChart').getContext('2d');
    const heatChart = new Chart(heatCtx, {
        type:'bar',
        data:{
            labels:[...Array(35).keys()].map(x=>x+1),
            datasets:[{label:'号码热度', data:dynamicData.heatmap, backgroundColor:'rgba(239,68,68,0.7)'}]
        },
        options:{responsive:true,scales:{y:{beginAtZero:true}}}
    });

    const modelCtx = document.getElementById('modelChart').getContext('2d');
    const modelChart = new Chart(modelCtx, {
        type:'line',
        data:{
            labels:[...Array( dynamicData.model ? 1 : 0 ).keys()],
            datasets:[
                {label:'freq', data:[dynamicData.model.freq||0], borderColor:'rgba(34,197,94,1)', fill:false},
                {label:'gap', data:[dynamicData.model.gap||0], borderColor:'rgba(59,130,246,1)', fill:false},
                {label:'balance', data:[dynamicData.model.balance||0], borderColor:'rgba(245,158,11,1)', fill:false}
            ]
        },
        options:{responsive:true, plugins:{legend:{display:true}}, scales:{y:{beginAtZero:true}}}
    });

    const hitCtx = document.getElementById('hitTrend').getContext('2d');
    const hitChart = new Chart(hitCtx, {
        type:'line',
        data:{
            labels:[1,2,3],
            datasets:[{
                label:'预测命中率动态',
                data:dynamicData.hits,
                borderColor:'rgba(14,165,233,1)',
                fill:false
            }]
        },
        options:{responsive:true, animation:{duration:1000}, scales:{y:{beginAtZero:true,max:5}}}
    });

    // 每2秒更新
    setInterval(()=>{
        fetch(window.location.href).then(r=>r.text()).then(html=>{
            const parser = new DOMParser();
            const doc = parser.parseFromString(html,'text/html');
            dynamicData = {{data|tojson}};
            renderPredictions();
            heatChart.data.datasets[0].data = dynamicData.heatmap;
            heatChart.update();
            hitChart.data.datasets[0].data = dynamicData.hits;
            hitChart.update();
        });
    },2000);
    </script>
    </body>
    </html>
    """, data=data)

if __name__=="__main__":
    app.run(host="0.0.0.0", port=10000)
