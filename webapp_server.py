from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3, hmac, hashlib, json
from datetime import datetime
from database import DB, update_earnings
from config import BOT_TOKEN, INVESTMENT_PLANS, MIN_WITHDRAW, REFERRAL_BONUS

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="webapp"), name="static")

# ── Telegram initData verify ──────────────────────────────────────────────────

def verify_telegram_data(init_data: str) -> dict | None:
    try:
        parsed = {}
        for part in init_data.split("&"):
            k, v = part.split("=", 1)
            parsed[k] = v
        hash_val = parsed.pop("hash", "")
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, hash_val):
            import urllib.parse
            user_str = parsed.get("user", "{}")
            return json.loads(urllib.parse.unquote(user_str))
        return None
    except:
        return None

def get_uid(request: Request) -> int:
    init_data = request.headers.get("X-Init-Data", "")
    user = verify_telegram_data(init_data)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user["id"]

# ── DB helpers ────────────────────────────────────────────────────────────────

def db_query(sql, params=()):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return rows

def db_exec(sql, params=()):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(sql, params)
    conn.commit()
    conn.close()

# ── API Routes ────────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
def dashboard(request: Request):
    uid = get_uid(request)
    update_earnings()
    rows = db_query("SELECT user_id, username, balance, total_invested, joined_at, referral_count FROM users WHERE user_id=?", (uid,))
    if not rows:
        raise HTTPException(status_code=404, detail="User not found")
    u = rows[0]
    invs = db_query("SELECT amount, per_hour, started_at, expires_at FROM investments WHERE user_id=?", (uid,))
    now = datetime.now()
    investments = []
    active_hourly = 0
    for inv in invs:
        amount, per_hour, started_at, expires_at = inv
        expired = expires_at and now >= datetime.fromisoformat(expires_at)
        days_left = 0
        if expires_at and not expired:
            days_left = (datetime.fromisoformat(expires_at) - now).days + 1
            active_hourly += per_hour
        plan = next((p for p in INVESTMENT_PLANS if p["amount"] == amount), None)
        investments.append({
            "amount": amount,
            "per_hour": per_hour,
            "daily": plan["daily"] if plan else round(per_hour * 24, 2),
            "started_at": started_at[:10],
            "expires_at": expires_at[:10] if expires_at else None,
            "expired": bool(expired),
            "days_left": days_left,
            "plan_name": plan["name"] if plan else "Custom"
        })
    ref_rows = db_query("SELECT user_id, username FROM users WHERE referred_by=?", (uid,))
    return {
        "user_id": u[0],
        "username": u[1],
        "balance": round(u[2], 2),
        "total_invested": u[3],
        "joined_at": u[4][:10],
        "referral_count": u[5] or 0,
        "referral_bonus_total": (u[5] or 0) * REFERRAL_BONUS,
        "active_hourly": round(active_hourly, 2),
        "active_daily": round(active_hourly * 24, 2),
        "investments": investments,
        "referrals": [{"id": r[0], "username": r[1]} for r in ref_rows],
        "plans": INVESTMENT_PLANS,
        "min_withdraw": MIN_WITHDRAW,
        "referral_bonus": REFERRAL_BONUS,
    }

@app.get("/api/withdrawals")
def get_withdrawals(request: Request):
    uid = get_uid(request)
    rows = db_query("SELECT amount, wallet, status, requested_at FROM withdrawals WHERE user_id=? ORDER BY requested_at DESC", (uid,))
    return [{"amount": r[0], "wallet": r[1], "status": r[2], "date": r[3][:10]} for r in rows]

class WithdrawReq(BaseModel):
    amount: float
    upi: str

@app.post("/api/withdraw")
def withdraw(req: WithdrawReq, request: Request):
    uid = get_uid(request)
    update_earnings()
    rows = db_query("SELECT balance FROM users WHERE user_id=?", (uid,))
    if not rows:
        raise HTTPException(status_code=404)
    balance = rows[0][0]
    if req.amount < MIN_WITHDRAW:
        raise HTTPException(status_code=400, detail=f"Minimum ₹{MIN_WITHDRAW} withdraw kar sakte ho")
    if req.amount > balance:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    db_exec("UPDATE users SET balance=balance-? WHERE user_id=?", (req.amount, uid))
    db_exec("INSERT INTO withdrawals (user_id, amount, wallet, requested_at) VALUES (?,?,?,?)",
            (uid, req.amount, req.upi, datetime.now().isoformat()))
    return {"ok": True, "message": "Withdrawal request submit ho gayi!"}
