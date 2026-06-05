from fastapi import FastAPI
import sqlite3
import hashlib
from datetime import datetime, timedelta

API_KEY = "X9qP_7ZkL_Opt_2026_ProKey#91"
VALID_PLANS = ["free", "premium", "ultra", "owner"]

conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
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


def _get_user(username):
    cur.execute(
        "SELECT username, password, expiry, plan, discord_id FROM users WHERE username=?",
        (username,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "username": row[0],
        "password": row[1],
        "expiry": row[2],
        "plan": row[3],
        "discord_id": row[4],
    }


def _user_row_to_dict(rowid, row):
    return {
        "id": rowid,
        "user": row[0],
        "plan": row[2],
        "expiry": row[3],
        "discord_id": row[4] or "",
    }


app = FastAPI()


@app.post("/login")
def login(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False}

    user = data.get("user", "")
    pwd = hash_pass(data.get("pass", ""))

    cur.execute("SELECT expiry, plan FROM users WHERE username=? AND password=?", (user, pwd))
    row = cur.fetchone()
    if not row:
        return {"ok": False}

    if datetime.now() > datetime.fromisoformat(row[0]):
        return {"ok": False, "expired": True}

    return {"ok": True, "expiry": row[0], "plan": row[1]}


@app.post("/create")
def create_user(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    user = data.get("user", "").strip()
    pwd = hash_pass(data.get("pass", ""))
    days = int(data.get("days", 0))
    plan = (data.get("plan") or "free").lower()
    discord_id = data.get("discord_id", "unknown")

    if not user:
        return {"ok": False, "error": "user required"}
    if plan not in VALID_PLANS:
        return {"ok": False, "error": "invalid plan"}

    expiry = (datetime.now() + timedelta(days=days)).isoformat()
    cur.execute(
        "INSERT OR REPLACE INTO users VALUES (?,?,?,?,?)",
        (user, pwd, expiry, plan, discord_id),
    )
    conn.commit()
    return {"ok": True}


@app.post("/listusers")
def list_users(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    search = (data.get("search") or "").strip().lower()
    cur.execute("SELECT rowid, username, password, expiry, plan, discord_id FROM users ORDER BY username")
    rows = cur.fetchall()

    users = []
    for rowid, username, _pwd, expiry, plan, discord_id in rows:
        if search and search not in username.lower():
            continue
        users.append({
            "id": rowid,
            "user": username,
            "plan": plan,
            "expiry": expiry,
            "discord_id": discord_id or "",
        })

    return {"ok": True, "users": users}


@app.post("/edituser")
def edit_user(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    old_user = data.get("old_user", "").strip()
    new_user = (data.get("new_user") or old_user).strip()
    new_pass = data.get("new_pass")

    existing = _get_user(old_user)
    if not existing:
        return {"ok": False, "error": "user not found"}

    pwd = hash_pass(new_pass) if new_pass else existing["password"]

    if old_user != new_user:
        cur.execute("DELETE FROM users WHERE username=?", (old_user,))

    cur.execute(
        "INSERT OR REPLACE INTO users VALUES (?,?,?,?,?)",
        (new_user, pwd, existing["expiry"], existing["plan"], existing["discord_id"]),
    )
    conn.commit()
    return {"ok": True}


@app.post("/changepass")
def change_password(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    user = data.get("user", "").strip()
    raw_pass = data.get("new_pass") or data.get("pass")
    if not user or not raw_pass:
        return {"ok": False, "error": "user and password required"}

    existing = _get_user(user)
    if not existing:
        return {"ok": False, "error": "user not found"}

    cur.execute(
        "UPDATE users SET password=? WHERE username=?",
        (hash_pass(raw_pass), user),
    )
    conn.commit()
    return {"ok": True, "status": "password updated"}


@app.post("/changeplan")
def change_plan(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    user = data.get("user", "").strip()
    new_plan = (data.get("plan") or "").lower()

    if new_plan not in VALID_PLANS:
        return {"ok": False, "error": "invalid plan"}
    if not _get_user(user):
        return {"ok": False, "error": "user not found"}

    cur.execute("UPDATE users SET plan=? WHERE username=?", (new_plan, user))
    conn.commit()
    return {"ok": True, "status": "plan updated"}


@app.post("/addtime")
def add_time(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    user = data.get("user", "").strip()
    days = int(data.get("days", 0))
    existing = _get_user(user)
    if not existing:
        return {"ok": False, "error": "user not found"}

    expiry_date = datetime.fromisoformat(existing["expiry"])
    if expiry_date < datetime.now():
        expiry_date = datetime.now()
    new_expiry = (expiry_date + timedelta(days=days)).isoformat()

    cur.execute("UPDATE users SET expiry=? WHERE username=?", (new_expiry, user))
    conn.commit()
    return {"ok": True, "status": "time added", "expiry": new_expiry}


@app.post("/removetime")
def remove_time(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    user = data.get("user", "").strip()
    days = int(data.get("days", 0))
    existing = _get_user(user)
    if not existing:
        return {"ok": False, "error": "user not found"}

    expiry_date = datetime.fromisoformat(existing["expiry"])
    new_expiry = (expiry_date - timedelta(days=days)).isoformat()

    cur.execute("UPDATE users SET expiry=? WHERE username=?", (new_expiry, user))
    conn.commit()
    return {"ok": True, "status": "time removed", "expiry": new_expiry}


@app.post("/delete")
def delete_user(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    user = data.get("user", "").strip()
    if not _get_user(user):
        return {"ok": False, "error": "user not found"}

    cur.execute("DELETE FROM users WHERE username=?", (user,))
    conn.commit()
    return {"ok": True, "status": "user deleted"}


@app.get("/users")
def get_users(api_key: str):
    if api_key != API_KEY:
        return {"ok": False}

    cur.execute("SELECT rowid, username, password, expiry, plan, discord_id FROM users")
    rows = cur.fetchall()
    return {
        "ok": True,
        "users": [_user_row_to_dict(r[0], (r[1], r[2], r[4], r[3], r[5])) for r in rows],
    }


@app.get("/users_full")
def get_users_full(api_key: str):
    return get_users(api_key)


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
