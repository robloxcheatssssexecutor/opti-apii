from fastapi import FastAPI
import sqlite3
import hashlib
from datetime import datetime, timedelta

API_KEY = "X9qP_7ZkL_Opt_2026_ProKey#91"

app = FastAPI()

conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()

# ================= DATABASE =================

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    username TEXT UNIQUE,
    password TEXT,
    plan TEXT,
    expiry TEXT
)
""")

conn.commit()

# ================= UTILS =================

def hash_pass(p):
    return hashlib.sha256(p.encode()).hexdigest()

# ================= LOGIN =================

@app.post("/login")
def login(data: dict):

    if data.get("api_key") != API_KEY:
        return {"ok": False}

    user = data["user"]
    pwd = hash_pass(data["pass"])

    cur.execute(
        "SELECT plan, expiry FROM users WHERE username=? AND password=?",
        (user, pwd)
    )

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

# ================= CREATE USER =================

@app.post("/create")
def create_user(data: dict):

    if data.get("api_key") != API_KEY:
        return {"ok": False}

    user = data["user"]
    pwd = hash_pass(data["pass"])
    plan = data["plan"]
    days = data["days"]

    expiry = (datetime.now() + timedelta(days=days)).isoformat()

    cur.execute(
        "INSERT OR REPLACE INTO users VALUES (?,?,?,?)",
        (user, pwd, plan, expiry)
    )

    conn.commit()

    return {"ok": True}

# ================= CHANGE PLAN =================

@app.post("/changeplan")
def change_plan(data: dict):

    if data.get("api_key") != API_KEY:
        return {"ok": False}

    user = data["user"]
    plan = data["plan"]

    cur.execute(
        "UPDATE users SET plan=? WHERE username=?",
        (plan, user)
    )

    conn.commit()

    return {"ok": True}

# ================= ADD TIME =================

@app.post("/addtime")
def add_time(data: dict):

    if data.get("api_key") != API_KEY:
        return {"ok": False}

    user = data["user"]
    days = int(data["days"])

    cur.execute("SELECT expiry FROM users WHERE username=?", (user,))
    row = cur.fetchone()

    if not row:
        return {"ok": False}

    expiry = datetime.fromisoformat(row[0])
    new_expiry = expiry + timedelta(days=days)

    cur.execute(
        "UPDATE users SET expiry=? WHERE username=?",
        (new_expiry.isoformat(), user)
    )

    conn.commit()

    return {"ok": True}

# ================= REMOVE TIME =================

@app.post("/removetime")
def remove_time(data: dict):

    if data.get("api_key") != API_KEY:
        return {"ok": False}

    user = data["user"]
    days = int(data["days"])

    cur.execute("SELECT expiry FROM users WHERE username=?", (user,))
    row = cur.fetchone()

    if not row:
        return {"ok": False}

    expiry = datetime.fromisoformat(row[0])
    new_expiry = expiry - timedelta(days=days)

    cur.execute(
        "UPDATE users SET expiry=? WHERE username=?",
        (new_expiry.isoformat(), user)
    )

    conn.commit()

    return {"ok": True}

# ================= DELETE USER =================

@app.post("/delete")
def delete_user(data: dict):

    if data.get("api_key") != API_KEY:
        return {"ok": False}

    user = data["user"]

    cur.execute(
        "DELETE FROM users WHERE username=?",
        (user,)
    )

    conn.commit()

    return {"ok": True}

# ================= CHANGE PASSWORD =================

@app.post("/changepass")
def change_pass(data: dict):

    if data.get("api_key") != API_KEY:
        return {"ok": False}

    user = data["user"]
    new_pass = hash_pass(data["pass"])

    cur.execute(
        "UPDATE users SET password=? WHERE username=?",
        (new_pass, user)
    )

    conn.commit()

    return {"ok": True}

# ================= EDIT USER =================

@app.post("/edituser")
def edit_user(data: dict):

    if data.get("api_key") != API_KEY:
        return {"ok": False}

    old_user = data["old_user"]
    new_user = data["new_user"]
    new_pass = hash_pass(data["new_pass"])

    cur.execute(
        "UPDATE users SET username=?, password=? WHERE username=?",
        (new_user, new_pass, old_user)
    )

    conn.commit()

    return {"ok": True}

# ================= LIST USERS =================

@app.post("/listusers")
def list_users(data: dict):

    if data.get("api_key") != API_KEY:
        return {"ok": False}

    search = data.get("search","")

    cur.execute(
        "SELECT rowid, username, plan, expiry FROM users WHERE username LIKE ?",
        (f"%{search}%",)
    )

    rows = cur.fetchall()

    users = []

    for r in rows:
        users.append({
            "id": r[0],
            "user": r[1],
            "plan": r[2],
            "expiry": r[3]
        })

    return {"users": users}

# ================= RUN =================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
