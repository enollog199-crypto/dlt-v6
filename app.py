@app.route("/")
def index():
    init_db()
    sync_system()
    conn = sqlite3.connect("ai.db")
    rows = conn.execute("SELECT period, red, blue, hit, confidence, prob_data FROM predict ORDER BY period DESC LIMIT 15").fetchall()
    conn.close()
    
    records, l_list, v_list = [], [], []
    
    # 核心修正：如果数据库还没数据，创建一个临时的“等待”记录，防止模板报错
    if not rows:
        records.append({
            "period": "同步中...", 
            "red": [0,0,0,0,0], 
            "blue": [0,0], 
            "hit": "/", 
            "conf": 0, 
            "exp": "正在连接服务器同步数据，请稍后刷新页面..."
        })
        p_data = {}
    else:
        for r in rows:
            pj = json.loads(r[5]) if r[5] else {}
            records.append({
                "period": str(r[0]),
                "red": json.loads(r[1]),
                "blue": json.loads(r[2]),
                "hit": str(r[3]),
                "conf": r[4],
                "exp": pj.get("exp","")
            })
            if str(r[3]) != "/":
                l_list.append(str(r[0]))
                v_list.append(sum(map(int, str(r[3]).split('+'))))
        
        # 确保 p_data 存在
        first_row_pj = json.loads(rows[0][5]) if rows[0][5] else {}
        p_data = first_row_pj.get("prob", {})

    top_num = sorted(p_data.items(), key=lambda x:x[1], reverse=True)[:10]
    chart_payload = {"lab_list": l_list[::-1], "val_list": v_list[::-1]}
    
    return render_template("index.html", 
                           records=records, 
                           top_numbers=top_num, 
                           chart_data=chart_payload, 
                           logged_in=('user' in session))
