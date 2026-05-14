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

API_KEY = "X9qP_7ZkL_Opt_2026_ProKey#91"
users = {}

def save_users():
    with open("users.json", "w") as f:
        json.dump(users, f)

def load_users():
    global users
    try:
        with open("users.json", "r") as f:
            users = json.load(f)
    except:
        users = {}

load_users()

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

@app.post("/changepass")
def change_password(data: dict):
    user = data.get("user")
    new_pass = data.get("new_pass")
    api_key = data.get("api_key")

    if api_key != API_KEY:
        return {"error": "invalid api key"}

    if user not in users:
        return {"error": "user not found"}

    users[user]["pass"] = new_pass
    save_users()

    return {"status": "password updated"}

@app.post("/changeplan")
def change_plan(data: dict):
    user = data.get("user")
    new_plan = data.get("plan")
    api_key = data.get("api_key")

    if api_key != API_KEY:
        return {"error": "invalid api key"}

    if user not in users:
        return {"error": "user not found"}

    users[user]["plan"] = new_plan
    save_users()

    return {"status": "plan updated"}

@app.post("/addtime")
def add_time(data: dict):
    user = data.get("user")
    days = int(data.get("days", 0))
    api_key = data.get("api_key")

    if api_key != API_KEY:
        return {"error": "invalid api key"}

    if user not in users:
        return {"error": "user not found"}

    current_expiry = users[user].get("expiry")

    if current_expiry:
        expiry_date = datetime.fromisoformat(current_expiry)
    else:
        expiry_date = datetime.now()

    new_expiry = expiry_date + timedelta(days=days)
    users[user]["expiry"] = new_expiry.isoformat()

    save_users()

    return {"status": "time added"}

@app.post("/removetime")
def remove_time(data: dict):
    user = data.get("user")
    days = int(data.get("days", 0))
    api_key = data.get("api_key")

    if api_key != API_KEY:
        return {"error": "invalid api key"}

    if user not in users:
        return {"error": "user not found"}

    expiry_date = datetime.fromisoformat(users[user]["expiry"])
    new_expiry = expiry_date - timedelta(days=days)

    users[user]["expiry"] = new_expiry.isoformat()

    save_users()

    return {"status": "time removed"}

@app.post("/delete")
def delete_user(data: dict):
    user = data.get("user")
    api_key = data.get("api_key")

    if api_key != API_KEY:
        return {"error": "invalid api key"}

    if user not in users:
        return {"error": "user not found"}

    del users[user]
    save_users()

    return {"status": "user deleted"}

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

@app.get("/users_full")
def get_users(api_key: str):

    if api_key != API_KEY:
        return {"ok": False}

    cur.execute("SELECT username, plan, expiry, discord_id FROM users")
    rows = cur.fetchall()

    return {
        "ok": True,
        "users": [
            {
                "user": r[0],
                "plan": r[1],
                "expiry": r[2],
                "discord_id": r[3]
            }
            for r in rows
        ]
    }

if __name__ == "__main__":
    import os
    import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
