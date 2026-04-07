import sqlite3

conn = sqlite3.connect("user_v28.db")
c = conn.cursor()

# ===== 用户表 =====
c.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    vip INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT 0
)
""")

# ===== 预测记录表（命中统计用）=====
c.execute("""
CREATE TABLE IF NOT EXISTS predictions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    numbers TEXT,
    hit INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT (strftime('%s','now'))
)
""")

conn.commit()
conn.close()

print("数据库初始化完成（V29）")
