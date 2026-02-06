from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    return "I'm alive! บอททำงานอยู่ค้าบ"

def run():
    # ดึงพอร์ตจาก Render (ถ้าไม่มีให้ใช้ 8080)
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()