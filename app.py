from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests, re, time, datetime, os, random
import numpy as np
from sklearn.ensemble import RandomForestClassifier

app = Flask(__name__, template_folder="web")
app.secret_key = "dextro_bet_v15_secure"
# 数据库配置
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dextro_game.db'
db = SQLAlchemy(app)

# =========================
# 数据库模型
# =========================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    balance = db.Column(db.Float, default=1000.0) # 初始虚拟金

class Bet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    period = db.Column(db.String(20), nullable=False) # 期号
    red_balls = db.Column(db.String(50))
    blue_balls = db.Column(db.String(20))
    amount = db.Column(db.Float)
    status = db.Column(db.String(20), default="待开奖") # 待开奖/已中奖/未中奖
    win_amount = db.Column(db.Float, default=0.0)

with app.app_context():
    db.create_all()

# =========================
# 数据引擎 (保持 V14 的防御逻辑)
# =========================
class DataEngine:
    def _safe_nums(self, arr, min_v, max_v):
        out = []
        for x in arr:
            try:
                n = int(re.sub(r'<.*?>', '', str(x)).strip())
                if min_v <= n <= max_v: out.append(n)
            except: continue
        return sorted(list(set(out)))

    def fetch(self):
        # 此处简化，实际调用之前写的 _sina 或 _500
        return self._sina() 

    def _sina(self):
        try:
            url = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?gameNo=85&pageSize=50"
            res = requests.get(url, timeout=5)
            js = res.json()
            return [{
                "p": i['lotteryDrawNum'],
                "date": i['lotteryDrawTime'],
                "r": self._safe_nums(i['lotteryDrawResult'].split()[:5], 1, 35),
                "b": self._safe_nums(i['lotteryDrawResult'].split()[5:], 1, 12)
            } for i in js['value']['list']]
        except: return []

# =========================
# 虚拟派奖逻辑
# =========================
def auto_settle_bets(latest_period_num, win_r, win_b):
    """自动比对期号并派奖"""
    pending_bets = Bet.query.filter_by(period=latest_period_num, status="待开奖").all()
    for bet in pending_bets:
        user_r = [int(x) for x in bet.red_balls.split(',')]
        user_b = [int(x) for x in bet.blue_balls.split(',')]
        
        # 简单比对逻辑 (示例：中5+2虚拟奖10000)
        match_r = len(set(user_r) & set(win_r))
        match_b = len(set(user_b) & set(win_b))
        
        prize = 0
        if match_r == 5 and match_b == 2: prize = bet.amount * 1000
        elif match_r >= 3: prize = bet.amount * 5
        
        if prize > 0:
            user = User.query.get(bet.user_id)
            user.balance += prize
            bet.status = "已中奖"
            bet.win_amount = prize
        else:
            bet.status = "未中奖"
    db.session.commit()

# =========================
# 路由逻辑
# =========================
@app.route("/")
def index():
    engine = DataEngine()
    history = engine.fetch()
    if not history: return "数据同步中...", 503
    
    # 自动派奖触发
    auto_settle_bets(history[0]['p'], history[0]['r'], history[0]['b'])
    
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    
    # (此处省略 V14 的 AI 计算逻辑，保持原样即可)
    return render_template("index.html", history=history, user=user, last=history[0])

@app.route("/bet", methods=["POST"])
def place_bet():
    if 'user_id' not in session: return jsonify({"msg": "请先登录"}), 403
    
    user = User.query.get(session['user_id'])
    data = request.json
    amount = float(data.get('amount', 2))
    
    if user.balance < amount: return jsonify({"msg": "虚拟币不足"}), 400
    
    new_bet = Bet(
        user_id=user.id,
        period=str(int(data.get('period')) + 1), # 投注下一期
        red_balls=",".join(map(str, data.get('reds'))),
        blue_balls=",".join(map(str, data.get('blues'))),
        amount=amount
    )
    user.balance -= amount
    db.session.add(new_bet)
    db.session.commit()
    return jsonify({"msg": "投注成功", "new_balance": user.balance})

@app.route("/register", methods=["POST"])
def register():
    data = request.form
    if User.query.filter_by(username=data['username']).first():
        return "用户名已存在"
    new_user = User(username=data['username'], password=data['password'])
    db.session.add(new_user)
    db.session.commit()
    return redirect(url_for('index'))

@app.route("/login", methods=["POST"])
def login():
    data = request.form
    user = User.query.filter_by(username=data['username'], password=data['password']).first()
    if user:
        session['user_id'] = user.id
    return redirect(url_for('index'))

@app.route("/logout")
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
