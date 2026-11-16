import sqlite3, os
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.db")
x=10
y=20
sum=x+y

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance REAL DEFAULT 0,
        total_invested REAL DEFAULT 0,
        joined_at TEXT,
        referred_by INTEGER DEFAULT NULL,
        referral_count INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS investments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        per_hour REAL,
        started_at TEXT,
        last_updated TEXT,
        expires_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        wallet TEXT,
        status TEXT DEFAULT 'pending',
        requested_at TEXT
    )''')
    # Existing DB ke liye columns add karo agar nahi hain
    for col, definition in [("referred_by", "INTEGER DEFAULT NULL"), ("referral_count", "INTEGER DEFAULT 0")]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
        except:
            pass
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def create_user(user_id, username, referred_by=None):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, joined_at, referred_by) VALUES (?,?,?,?)",
              (user_id, username, datetime.now().isoformat(), referred_by))
    conn.commit()
    conn.close()

def get_investments(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM investments WHERE user_id=?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def add_investment(user_id, amount, per_hour, days):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    now = datetime.now()
    expires = (now + __import__('datetime').timedelta(days=days)).isoformat()
    c.execute("INSERT INTO investments (user_id, amount, per_hour, started_at, last_updated, expires_at) VALUES (?,?,?,?,?,?)",
              (user_id, amount, per_hour, now.isoformat(), now.isoformat(), expires))
    c.execute("UPDATE users SET total_invested=total_invested+? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def update_earnings():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, user_id, per_hour, last_updated, expires_at FROM investments")
    investments = c.fetchall()
    now = datetime.now()
    for inv in investments:
        inv_id, user_id, per_hour, last_updated, expires_at = inv
        if expires_at and now >= datetime.fromisoformat(expires_at):
            continue  # Plan expire ho gaya, earning band
        last = datetime.fromisoformat(last_updated)
        hours = (now - last).total_seconds() / 3600
        if hours >= 1:
            earned = per_hour * int(hours)
            c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (earned, user_id))
            c.execute("UPDATE investments SET last_updated=? WHERE id=?", (now.isoformat(), inv_id))
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def add_withdrawal(user_id, amount, wallet):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, user_id))
    c.execute("INSERT INTO withdrawals (user_id, amount, wallet, requested_at) VALUES (?,?,?,?)",
              (user_id, amount, wallet, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_all_withdrawals():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM withdrawals WHERE status='pending'")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_users():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT user_id, username, balance, total_invested, joined_at FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

def set_balance(user_id, amount):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE users SET balance=? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def ban_user(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE users SET username='BANNED_' || username WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE users SET username=REPLACE(username,'BANNED_','') WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def is_banned(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] and row[0].startswith("BANNED_")

def boost_referral(user_id, count):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE users SET referral_count=COALESCE(referral_count,0)+? WHERE user_id=?", (count, user_id))
    conn.commit()
    conn.close()

def get_referrer(user_id):
    """Kiska referral hai ye user?"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT referred_by FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else None

def give_referral_bonus(referrer_id, bonus):
    """Referrer ko bonus do aur count badhao — sirf ek baar per referred user"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE users SET balance=balance+?, referral_count=COALESCE(referral_count,0)+1 WHERE user_id=?",
              (bonus, referrer_id))
    conn.commit()
    conn.close()

def has_bought_plan(user_id):
    """Check karo kya user ne pehle koi plan buy kiya hai"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM investments WHERE user_id=?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count > 0

def get_referral_stats(user_id):
    """User ke referral count aur total bonus"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT referral_count FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def silent_user(user_id, mute: bool):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE users ADD COLUMN is_silent INTEGER DEFAULT 0")
    except:
        pass
    c.execute("UPDATE users SET is_silent=? WHERE user_id=?", (1 if mute else 0, user_id))
    conn.commit()
    conn.close()

def is_silent(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    try:
        c.execute("SELECT is_silent FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
        conn.close()
        return row and row[0] == 1
    except:
        conn.close()
        return False

def force_expire_plans(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("UPDATE investments SET expires_at=? WHERE user_id=? AND (expires_at IS NULL OR expires_at > ?)",
              (now, user_id, now))
    count = c.rowcount
    conn.commit()
    conn.close()
    return count

def reset_user(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE users SET balance=0, total_invested=0, referral_count=0 WHERE user_id=?", (user_id,))
    now = datetime.now().isoformat()
    c.execute("UPDATE investments SET expires_at=? WHERE user_id=?", (now, user_id))
    conn.commit()
    conn.close()

def get_user_full_data(user_id):
    """Ek user ka poora data ek saath"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT user_id, username, balance, total_invested, joined_at, referred_by, referral_count FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    c.execute("SELECT amount, per_hour, started_at, expires_at FROM investments WHERE user_id=? ORDER BY started_at DESC", (user_id,))
    investments = c.fetchall()
    c.execute("SELECT amount, wallet, status, requested_at FROM withdrawals WHERE user_id=? ORDER BY requested_at DESC", (user_id,))
    withdrawals = c.fetchall()
    conn.close()
    return user, investments, withdrawals

def get_user_stats(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    c.execute("SELECT * FROM investments WHERE user_id=?", (user_id,))
    investments = c.fetchall()
    c.execute("SELECT * FROM withdrawals WHERE user_id=?", (user_id,))
    withdrawals = c.fetchall()
    conn.close()
    return user, investments, withdrawals
