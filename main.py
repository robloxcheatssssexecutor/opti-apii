from fastapi import FastAPI
import sqlite3
import hashlib
from datetime import datetime, timedelta

API_KEY = "X9qP_7ZkL_Opt_2026_ProKey#91"

conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    username TEXT UNIQUE,
    password TEXT,
    plan TEXT,
    expiry TEXT
)
""")
conn.commit()

def hash_pass(p):
    return hashlib.sha256(p.encode()).hexdigest()

app = FastAPI()

@app.post("/login")
def login(data: dict):

    if data.get("api_key") != API_KEY:
        return {"ok": False}

    user = data["user"]
    pwd = hash_pass(data["pass"])
    days = data["days"]
    plan = data["plan"]

    cur.execute("SELECT plan, expiry FROM users WHERE username=? AND password=?", (user, pwd))
    row = cur.fetchone()

    if not row:
        return {"ok": False}

    plan = row[0]
    expiry = row[1]

    if datetime.now() > datetime.fromisoformat(expiry):
        return {"ok": False, "expired": True}

    return {
    "ok": True,
    "plan": plan,
    "expiry": expiry
}

@app.post("/create")
def create_user(data: dict):

    if data.get("api_key") != API_KEY:
        return {"ok": False}

    user = data["user"]
    pwd = hash_pass(data["pass"])
    days = data["days"]

    expiry = (datetime.now() + timedelta(days=days)).isoformat()

    cur.execute(
        "INSERT OR REPLACE INTO users VALUES (?,?,?,?)",
        (user, pwd, plan, expiry)
    )

    conn.commit()

    return {"ok": True}

if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
