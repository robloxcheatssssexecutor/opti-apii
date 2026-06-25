from fastapi import FastAPI
import sqlite3
import hashlib
import threading
import os
from datetime import datetime, timedelta

# ── Configuración ──────────────────────────────────────────────────────────────
API_KEY     = "X9qP_7ZkL_Opt_2026_ProKey#91"
VALID_PLANS = ["free", "premium", "ultra", "owner"]

DB_PATH  = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "users.db"))
_db_lock = threading.Lock()

# ── SQLite ─────────────────────────────────────────────────────────────────────

def _new_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_db():
    with _new_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users(
                username   TEXT PRIMARY KEY,
                password   TEXT NOT NULL,
                expiry     TEXT NOT NULL,
                plan       TEXT NOT NULL DEFAULT 'free',
                discord_id TEXT
            )
        """)
        conn.commit()


_init_db()

# ── Helpers ────────────────────────────────────────────────────────────────────

def hash_pass(p: str) -> str:
    return hashlib.sha256(p.encode()).hexdigest()


def _get_user(username: str):
    with _new_conn() as conn:
        row = conn.execute(
            "SELECT username, password, expiry, plan, discord_id FROM users WHERE username=?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


def _row_to_dict(row) -> dict:
    return {
        "id":         row["rowid"],
        "user":       row["username"],
        "plan":       row["plan"],
        "expiry":     row["expiry"],
        "discord_id": row["discord_id"] or "",
    }

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI()


@app.post("/restore")
def restore(data: dict):
    """El bot llama a este endpoint con el último backup cuando la DB está vacía."""
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    users = data.get("users")
    if not isinstance(users, list):
        return {"ok": False, "error": "users must be a list"}

    with _db_lock:
        with _new_conn() as conn:
            conn.execute("DELETE FROM users")
            for u in users:
                conn.execute(
                    "INSERT OR REPLACE INTO users (username, password, expiry, plan, discord_id) VALUES (?,?,?,?,?)",
                    (u["username"], u["password"], u["expiry"], u["plan"], u.get("discord_id", "")),
                )
            conn.commit()

    print(f"[RESTORE] Restaurados {len(users)} usuarios.")
    return {"ok": True, "restored": len(users)}


@app.get("/db_empty")
def db_empty(api_key: str):
    """El bot consulta esto para saber si tiene que restaurar."""
    if api_key != API_KEY:
        return {"ok": False}
    with _new_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return {"ok": True, "empty": count == 0}


@app.post("/login")
def login(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False}

    user = data.get("user", "")
    pwd  = hash_pass(data.get("pass", ""))

    with _new_conn() as conn:
        row = conn.execute(
            "SELECT expiry, plan FROM users WHERE username=? AND password=?",
            (user, pwd),
        ).fetchone()

    if not row:
        return {"ok": False}

    expiry_dt = datetime.fromisoformat(row["expiry"])
    if datetime.now() > expiry_dt:
        return {"ok": False, "expired": True}

    dias_restantes = (expiry_dt - datetime.now()).days
    return {
        "ok": True,
        "expiry": row["expiry"],
        "plan": row["plan"],
        "days_left": dias_restantes,
    }


@app.post("/create")
def create_user(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    user       = data.get("user", "").strip()
    pwd        = hash_pass(data.get("pass", ""))
    days       = int(data.get("days", 0))
    plan       = (data.get("plan") or "free").lower()
    discord_id = data.get("discord_id", "unknown")

    if not user:
        return {"ok": False, "error": "user required"}
    if plan not in VALID_PLANS:
        return {"ok": False, "error": "invalid plan"}

    expiry = (datetime.now() + timedelta(days=days)).isoformat()

    with _db_lock:
        with _new_conn() as conn:
            existing = conn.execute(
                "SELECT username FROM users WHERE username=?", (user,)
            ).fetchone()
            if existing:
                return {"ok": False, "error": "user already exists"}
            conn.execute(
                "INSERT INTO users (username, password, expiry, plan, discord_id) VALUES (?,?,?,?,?)",
                (user, pwd, expiry, plan, discord_id),
            )
            conn.commit()

    return {"ok": True, "expiry": expiry}


@app.post("/listusers")
def list_users(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    search = (data.get("search") or "").strip().lower()

    with _new_conn() as conn:
        rows = conn.execute(
            "SELECT rowid, username, expiry, plan, discord_id FROM users ORDER BY username"
        ).fetchall()

    users = []
    for row in rows:
        if search and search not in row["username"].lower():
            continue
        users.append({
            "id":         row["rowid"],
            "user":       row["username"],
            "plan":       row["plan"],
            "expiry":     row["expiry"],
            "discord_id": row["discord_id"] or "",
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

    with _db_lock:
        with _new_conn() as conn:
            if old_user != new_user:
                conn.execute(
                    "INSERT OR REPLACE INTO users (username, password, expiry, plan, discord_id) VALUES (?,?,?,?,?)",
                    (new_user, pwd, existing["expiry"], existing["plan"], existing["discord_id"]),
                )
                conn.execute("DELETE FROM users WHERE username=?", (old_user,))
            else:
                conn.execute(
                    "UPDATE users SET password=? WHERE username=?",
                    (pwd, old_user),
                )
            conn.commit()

    return {"ok": True}


@app.post("/changepass")
def change_password(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    user     = data.get("user", "").strip()
    raw_pass = data.get("new_pass") or data.get("pass")

    if not user or not raw_pass:
        return {"ok": False, "error": "user and password required"}
    if not _get_user(user):
        return {"ok": False, "error": "user not found"}

    with _db_lock:
        with _new_conn() as conn:
            conn.execute(
                "UPDATE users SET password=? WHERE username=?",
                (hash_pass(raw_pass), user),
            )
            conn.commit()

    return {"ok": True, "status": "password updated"}


@app.post("/changeplan")
def change_plan(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    user     = data.get("user", "").strip()
    new_plan = (data.get("plan") or "").lower()

    if new_plan not in VALID_PLANS:
        return {"ok": False, "error": "invalid plan"}
    if not _get_user(user):
        return {"ok": False, "error": "user not found"}

    with _db_lock:
        with _new_conn() as conn:
            conn.execute("UPDATE users SET plan=? WHERE username=?", (new_plan, user))
            conn.commit()

    return {"ok": True, "status": "plan updated"}


@app.post("/setlicense")
def set_license(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    user = data.get("user", "").strip()
    days = int(data.get("days", 0))

    if not _get_user(user):
        return {"ok": False, "error": "user not found"}

    new_expiry = (datetime.now() + timedelta(days=days)).isoformat()

    with _db_lock:
        with _new_conn() as conn:
            conn.execute("UPDATE users SET expiry=? WHERE username=?", (new_expiry, user))
            conn.commit()

    return {"ok": True, "status": "license set", "expiry": new_expiry}


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

    with _db_lock:
        with _new_conn() as conn:
            conn.execute("UPDATE users SET expiry=? WHERE username=?", (new_expiry, user))
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
    new_expiry  = (expiry_date - timedelta(days=days)).isoformat()

    with _db_lock:
        with _new_conn() as conn:
            conn.execute("UPDATE users SET expiry=? WHERE username=?", (new_expiry, user))
            conn.commit()

    return {"ok": True, "status": "time removed", "expiry": new_expiry}


@app.post("/delete")
def delete_user(data: dict):
    if data.get("api_key") != API_KEY:
        return {"ok": False, "error": "invalid api key"}

    user = data.get("user", "").strip()

    if not _get_user(user):
        return {"ok": False, "error": "user not found"}

    with _db_lock:
        with _new_conn() as conn:
            conn.execute("DELETE FROM users WHERE username=?", (user,))
            conn.commit()

    return {"ok": True, "status": "user deleted"}


@app.get("/users")
def get_users(api_key: str):
    if api_key != API_KEY:
        return {"ok": False}

    with _new_conn() as conn:
        rows = conn.execute(
            "SELECT rowid, username, expiry, plan, discord_id FROM users"
        ).fetchall()

    return {"ok": True, "users": [_row_to_dict(r) for r in rows]}


@app.get("/users_full")
def get_users_full(api_key: str):
    return get_users(api_key)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
