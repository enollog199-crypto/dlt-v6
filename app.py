
from flask import Flask, jsonify
import random

app = Flask(__name__)

def generate_numbers():
    res = []
    for _ in range(3):
        front = sorted(random.sample(range(1,36),5))
        back = sorted(random.sample(range(1,13),2))
        res.append({"front": front, "back": back})
    return res

@app.route("/")
def home():
    return jsonify({
        "system": "DLT V6 Pro Online",
        "recommend": generate_numbers()
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
