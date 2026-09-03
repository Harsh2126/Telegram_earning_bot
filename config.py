import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

MIN_WITHDRAW = 200
REFERRAL_BONUS = 20  # ₹20 referral bonus (tabhi milega jab referred user plan buy kare)
ADMIN_USERNAME = "your_username"  # Apna Telegram username (bina @)

# 4 Investment Plans: (name, amount, daily_return, percent, duration_days, stars, video_file_id)
INVESTMENT_PLANS = [
    {"id": 1, "name": "Starter",  "amount": 200,  "daily": 50,   "percent": 25, "days": 6,  "stars": 134,  "video": "BAACAgUAAxkBAAMHapkCb2LzlRQN2qZDI4RgJMp9L5gAAoEdAAIdGMlU2ZX4Ju4IkL89BA"},
    {"id": 2, "name": "Basic",    "amount": 500,  "daily": 125,  "percent": 25, "days": 10, "stars": 334,  "video": "BAACAgUAAxkBAAMHapkCb2LzlRQN2qZDI4RgJMp9L5gAAoEdAAIdGMlU2ZX4Ju4IkL89BA"},
    {"id": 3, "name": "Pro",      "amount": 1000, "daily": 250,  "percent": 25, "days": 15, "stars": 667,  "video": "BAACAgUAAxkBAAMHapkCb2LzlRQN2qZDI4RgJMp9L5gAAoEdAAIdGMlU2ZX4Ju4IkL89BA"},
    {"id": 4, "name": "Premium",  "amount": 2000, "daily": 500,  "percent": 25, "days": 20, "stars": 1334, "video": "BAACAgUAAxkBAAMHapkCb2LzlRQN2qZDI4RgJMp9L5gAAoEdAAIdGMlU2ZX4Ju4IkL89BA"},
]
