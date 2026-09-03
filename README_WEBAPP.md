# Telegram Mini App Setup Guide

## Step 1 — Dependencies install karo
```
pip install -r requirements.txt
```

## Step 2 — Server deploy karo (HTTPS zaroori hai)

### Option A: ngrok (local testing ke liye)
```
ngrok http 8000
```
Tumhe milega: `https://abc123.ngrok.io`

### Option B: Railway / Render (free hosting)
- railway.app ya render.com pe deploy karo
- `webapp_server.py` ko main file banao

## Step 3 — config.py mein domain set karo
```python
WEBAPP_URL = "https://YOUR_DOMAIN"
```

## Step 4 — bot.py mein URL update karo
`start()` function mein ye line update karo:
```python
web_app=WebAppInfo(url="https://YOUR_DOMAIN/static/index.html")
```

## Step 5 — webapp/index.html mein bot username update karo
Line dhundo:
```js
refLink = `https://t.me/YourBotUsername?start=ref_${botUser}`;
```
`YourBotUsername` ko apne bot ke username se replace karo.

## Step 6 — Server run karo
```
uvicorn webapp_server:app --host 0.0.0.0 --port 8000
```

## Step 7 — Bot run karo (alag terminal mein)
```
python bot.py
```

## BotFather mein Menu Button set karo (optional)
1. @BotFather pe jao
2. /mybots → apna bot → Bot Settings → Menu Button
3. URL daalo: `https://YOUR_DOMAIN/static/index.html`
4. Button text: `🌐 Open App`

## Features in Web App
- 🏠 Home — Balance, earnings, quick actions
- 💰 Invest — Sabhi plans dekhna
- 📈 Portfolio — Active/expired investments with progress bar
- 💸 Withdraw — UPI withdrawal + history
- 👥 Refer — Referral link copy + referral list
