from fastapi import FastAPI
import sqlite3
import hashlib
from datetime import datetime, timedelta

API_KEY = "X9qP_7ZkL_Opt_2026_ProKey#91"

conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE users(
    username TEXT UNIQUE,
    password TEXT,
    expiry TEXT,
    plan TEXT,
    discord_id TEXT
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

    cur.execute("SELECT expiry, plan FROM users WHERE username=? AND password=?", (user, pwd))
    row = cur.fetchone()

    if not row:
        return {"ok": False}

    if datetime.now() > datetime.fromisoformat(row[0]):
        return {"ok": False, "expired": True}

    expiry = row[0]
    plan = row[1]

    return {
        "ok": True,
        "expiry": expiry,
        "plan": plan
    }
    
@app.post("/create")
def create_user(data: dict):

    if data.get("api_key") != API_KEY:
        return {"ok": False}

    user = data["user"]
    pwd = hash_pass(data["pass"])
    days = data["days"]
    plan = data.get("plan", "free")
    discord_id = data.get("discord_id", "unknown")

    expiry = (datetime.now() + timedelta(days=days)).isoformat()

    cur.execute(
        "INSERT OR REPLACE INTO users VALUES (?,?,?,?,?)",
        (user, pwd, expiry, plan, discord_id)
    )

    conn.commit()

    return {"ok": True}

@app.get("/users")
def get_users(api_key: str):

    if api_key != API_KEY:
        return {"ok": False}

    cur.execute("SELECT username, plan, expiry FROM users")
    rows = cur.fetchall()

    return {
        "ok": True,
        "users": [
            {
                "user": r[0],
                "plan": r[1],
                "expiry": r[2]
            }
            for r in rows
        ]
    }

if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
