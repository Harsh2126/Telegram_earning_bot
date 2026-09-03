import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler,
    PreCheckoutQueryHandler, filters
)
from database import (
    init_db, create_user, get_investments,
    add_investment, update_earnings, get_balance,
    add_withdrawal, get_all_withdrawals, get_all_users,
    set_balance, ban_user, unban_user, is_banned,
    boost_referral, get_user_stats,
    get_referrer, give_referral_bonus, get_referral_stats, has_bought_plan,
    get_user_full_data, silent_user, is_silent, force_expire_plans, reset_user
)
from config import BOT_TOKEN, ADMIN_ID, ADMIN_USERNAME, MIN_WITHDRAW, INVESTMENT_PLANS, REFERRAL_BONUS
from datetime import datetime

logging.basicConfig(level=logging.INFO)

WITHDRAW_AMOUNT, WITHDRAW_UPI = range(2)

# ─── START ────────────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Referral link se aaya hai? e.g. /start ref_12345
    referred_by = None
    if ctx.args and ctx.args[0].startswith("ref_"):
        try:
            referred_by = int(ctx.args[0].split("_")[1])
            if referred_by == user.id:
                referred_by = None  # Khud ko refer nahi kar sakte
        except:
            referred_by = None
    create_user(user.id, user.username or user.first_name, referred_by)
    if is_banned(user.id):
        await update.message.reply_text("🚫 Aapka account banned hai. Admin se contact karo.")
        return
    keyboard = [
        [InlineKeyboardButton("💰 Invest", callback_data="invest"),
         InlineKeyboardButton("📊 Dashboard", callback_data="dashboard")],
        [InlineKeyboardButton("💸 Withdraw", callback_data="withdraw"),
         InlineKeyboardButton("ℹ️ How it Works", callback_data="howworks")],
        [InlineKeyboardButton("👥 Refer & Earn ₹20", callback_data="refer")],
    ]
    await update.message.reply_text(
        f"👋 Welcome *{user.first_name}*!\n\n"
        f"💹 4 Investment Plans available hain!\n"
        f"⭐ Payment Telegram Stars se hogi\n"
        f"📥 Min Withdrawal: ₹{MIN_WITHDRAW}\n\n"
        "Neeche se option choose karo 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── HOW IT WORKS ─────────────────────────────────────────────────────────────

async def how_works(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    plans_text = ""
    for p in INVESTMENT_PLANS:
        plans_text += f"🔹 *{p['name']}* — ₹{p['amount']} ({p['stars']}⭐) | ₹{p['daily']}/day | {p['days']} din\n"
    await q.message.reply_text(
        "📖 *How It Works:*\n\n"
        f"{plans_text}\n"
        "📈 Sabhi plans pe *25% daily* return\n"
        "⭐ Stars se plan buy karo → video milega\n"
        "⏱ Earning har ghante update hoti hai\n"
        f"💸 ₹{MIN_WITHDRAW}+ hone pe withdraw karo\n\n"
        "⚠️ Stars Indian Rupees mein Telegram app se buy ho sakte hain.",
        parse_mode="Markdown"
    )

# ─── REFER & EARN ────────────────────────────────────────────────────────────

async def refer_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    bot_username = (await ctx.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    ref_count = get_referral_stats(user_id)
    total_earned = ref_count * REFERRAL_BONUS
    await q.message.reply_text(
        f"👥 *Refer & Earn Program*\n\n"
        f"💰 Har successful referral pe: *₹{REFERRAL_BONUS}*\n"
        f"⚠️ Bonus tabhi milega jab referred user *koi bhi plan buy kare*\n\n"
        f"🔗 *Aapka Referral Link:*\n`{ref_link}`\n\n"
        f"📊 *Aapki Stats:*\n"
        f"✅ Successful Referrals: {ref_count}\n"
        f"💵 Total Referral Earning: ₹{total_earned}",
        parse_mode="Markdown"
    )

# ─── INVEST — PLAN LIST ───────────────────────────────────────────────────────

async def invest_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    keyboard = []
    for p in INVESTMENT_PLANS:
        keyboard.append([InlineKeyboardButton(
            f"{p['name']} — ₹{p['amount']} | {p['stars']}⭐ | {p['days']} din",
            callback_data=f"plan_{p['id']}"
        )])
    await q.message.reply_text(
        "💰 *Investment Plan Choose Karo:*\n\n"
        "⭐ = Telegram Stars (INR mein buy hote hain)\n"
        "Plan select karne pe payment screen khulegi 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── PLAN SELECTED — SEND INVOICE ─────────────────────────────────────────────

async def plan_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    plan_id = int(q.data.split("_")[1])
    plan = next(p for p in INVESTMENT_PLANS if p["id"] == plan_id)
    total = plan["daily"] * plan["days"]

    await ctx.bot.send_invoice(
        chat_id=q.from_user.id,
        title=f"{plan['name']} Investment Plan",
        description=(
            f"💰 Investment: ₹{plan['amount']}\n"
            f"📈 Daily Earning: ₹{plan['daily']}\n"
            f"📅 Duration: {plan['days']} din\n"
            f"💵 Total Return: ₹{total}"
        ),
        payload=f"invest_{plan['id']}",
        currency="XTR",
        prices=[LabeledPrice(label=f"{plan['name']} Plan", amount=plan["stars"])],
    )

# ─── PRE CHECKOUT ─────────────────────────────────────────────────────────────

async def pre_checkout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

# ─── SUCCESSFUL PAYMENT ───────────────────────────────────────────────────────

async def successful_payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    plan_id = int(payload.split("_")[1])
    plan = next(p for p in INVESTMENT_PLANS if p["id"] == plan_id)
    user = update.effective_user

    per_hour = round(plan["daily"] / 24, 4)
    add_investment(user.id, plan["amount"], per_hour, plan["days"])

    # Referral bonus — sirf pehli plan purchase pe milega
    referrer_id = get_referrer(user.id)
    if referrer_id and not has_bought_plan(user.id):
        give_referral_bonus(referrer_id, REFERRAL_BONUS)
        try:
            await ctx.bot.send_message(
                chat_id=referrer_id,
                text=f"🎉 *Referral Bonus!*\n\n"
                     f"👤 Aapke referral ne *{plan['name']} Plan* buy kiya!\n"
                     f"💰 Aapko *₹{REFERRAL_BONUS}* bonus mil gaya! 🎉",
                parse_mode="Markdown"
            )
        except:
            pass

    if plan["video"] and not plan["video"].endswith("VIDEO_FILE_ID"):
        await update.message.reply_video(
            video=plan["video"],
            caption=(
                f"🎬 *{plan['name']} Plan — Welcome Video*\n\n"
                f"✅ Plan Activated!\n"
                f"💰 ₹{plan['amount']} | 📈 ₹{plan['daily']}/day | 📅 {plan['days']} din\n\n"
                "Earning shuru ho gayi! Dashboard /start se dekho 📊"
            ),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"🎉 *Payment Successful!*\n\n"
            f"✅ *{plan['name']} Plan Activated!*\n\n"
            f"💰 Amount: ₹{plan['amount']}\n"
            f"📈 Earning: ₹{per_hour:.2f}/hour | ₹{plan['daily']}/day\n"
            f"📅 Duration: {plan['days']} din\n"
            f"💵 Total Return: ₹{plan['daily'] * plan['days']}\n\n"
            "Dashboard /start se dekho 📊",
            parse_mode="Markdown"
        )

    await ctx.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"⭐ *New Stars Payment*\n\n"
             f"👤 User: @{user.username or user.first_name} (ID: `{user.id}`)\n"
             f"📦 Plan: {plan['name']}\n"
             f"⭐ Stars: {plan['stars']}\n"
             f"💰 Amount: ₹{plan['amount']}",
        parse_mode="Markdown"
    )

# ─── DASHBOARD ────────────────────────────────────────────────────────────────

async def dashboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    update_earnings()

    user_id = q.from_user.id
    balance = get_balance(user_id)
    investments = get_investments(user_id)

    if not investments:
        await q.message.reply_text(
            "📊 *Dashboard*\n\n"
            "❌ Koi active investment nahi hai.\n"
            "Invest karo /start se!",
            parse_mode="Markdown"
        )
        return

    text = "📊 *Your Dashboard*\n\n"
    total_invested = 0
    total_hourly = 0
    now = datetime.now()

    for inv in investments:
        inv_id, uid, amount, per_hour, started_at, last_updated, expires_at = inv
        plan = next((p for p in INVESTMENT_PLANS if p["amount"] == amount), None)
        daily = plan["daily"] if plan else round(per_hour * 24, 2)
        expired = expires_at and now >= datetime.fromisoformat(expires_at)
        days_left = 0
        if expires_at and not expired:
            days_left = (datetime.fromisoformat(expires_at) - now).days + 1
        status = "⛔ Expired" if expired else f"✅ Active | {days_left} din bache"
        text += (
            f"💼 ₹{amount:.0f} | {status}\n"
            f"   📈 ₹{per_hour:.2f}/hr | ₹{daily:.0f}/day\n"
            f"   📅 Started: {started_at[:10]}\n\n"
        )
        total_invested += amount
        if not expired:
            total_hourly += per_hour

    text += (
        f"━━━━━━━━━━━━━━\n"
        f"💰 Total Invested: ₹{total_invested:.0f}\n"
        f"⚡ Active Earning: ₹{total_hourly:.2f}/hr\n"
        f"💵 Available Balance: ₹{balance:.2f}"
    )
    await q.message.reply_text(text, parse_mode="Markdown")

# ─── WITHDRAW FLOW ────────────────────────────────────────────────────────────

async def withdraw_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    update_earnings()

    user_id = q.from_user.id
    balance = get_balance(user_id)

    if balance < MIN_WITHDRAW:
        await q.message.reply_text(
            f"❌ Minimum withdrawal ₹{MIN_WITHDRAW} hai.\n"
            f"Aapka balance: ₹{balance:.2f}"
        )
        return ConversationHandler.END

    await q.message.reply_text(
        f"💸 *Withdrawal*\n\n"
        f"Available Balance: ₹{balance:.2f}\n"
        f"Min Withdrawal: ₹{MIN_WITHDRAW}\n\n"
        "Kitna withdraw karna hai? Amount daalo 👇",
        parse_mode="Markdown"
    )
    return WITHDRAW_AMOUNT

async def withdraw_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Sirf number daalo.")
        return WITHDRAW_AMOUNT

    update_earnings()
    balance = get_balance(update.effective_user.id)

    if amount < MIN_WITHDRAW:
        await update.message.reply_text(f"❌ Minimum ₹{MIN_WITHDRAW} withdraw kar sakte ho.")
        return WITHDRAW_AMOUNT
    if amount > balance:
        await update.message.reply_text(f"❌ Insufficient balance. Aapka balance: ₹{balance:.2f}")
        return WITHDRAW_AMOUNT

    ctx.user_data["withdraw_amount"] = amount
    await update.message.reply_text(
        "📱 Apna *UPI ID* daalo jahan paisa chahiye:\n(Example: name@upi)",
        parse_mode="Markdown"
    )
    return WITHDRAW_UPI

async def withdraw_upi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    upi = update.message.text.strip()
    amount = ctx.user_data.get("withdraw_amount", 0)
    user = update.effective_user

    add_withdrawal(user.id, amount, upi)

    keyboard = [[InlineKeyboardButton("✅ Mark as Paid", callback_data=f"paid_{user.id}_{amount}")]]
    await ctx.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"💸 *Withdrawal Request*\n\n"
             f"👤 User: @{user.username or user.first_name} (ID: `{user.id}`)\n"
             f"💰 Amount: ₹{amount:.0f}\n"
             f"📱 UPI: `{upi}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    await update.message.reply_text(
        f"✅ Withdrawal request submit ho gayi!\n\n"
        f"💰 Amount: ₹{amount:.0f}\n"
        f"📱 UPI: {upi}\n\n"
        "Admin 24 hours mein process karega. ⏳"
    )
    return ConversationHandler.END

# ─── ADMIN MARK PAID ──────────────────────────────────────────────────────────

async def admin_paid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        await q.answer("❌ Sirf admin.", show_alert=True)
        return
    await q.answer()
    parts = q.data.split("_")
    user_id, amount = int(parts[1]), float(parts[2])
    await q.edit_message_text(q.message.text + "\n\n✅ *PAID*", parse_mode="Markdown")
    await ctx.bot.send_message(
        chat_id=user_id,
        text=f"🎉 Aapka ₹{amount:.0f} ka withdrawal process ho gaya!\nUPI pe check karo. 💳"
    )

# ─── ADMIN PANEL ──────────────────────────────────────────────────────────────

async def admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    keyboard = [
        [InlineKeyboardButton("📋 Pending Withdrawals", callback_data="sec_withdrawals")],
        [InlineKeyboardButton("👥 All Users", callback_data="sec_users"),
         InlineKeyboardButton("📊 Bot Stats", callback_data="sec_stats")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="sec_ban"),
         InlineKeyboardButton("✅ Unban User", callback_data="sec_unban")],
        [InlineKeyboardButton("🔇 Silent User", callback_data="sec_silent"),
         InlineKeyboardButton("🔊 Unsilent User", callback_data="sec_unsilent")],
        [InlineKeyboardButton("💰 Set Balance", callback_data="sec_setbal"),
         InlineKeyboardButton("🔄 Reset User", callback_data="sec_reset")],
        [InlineKeyboardButton("🚀 Referral Boost", callback_data="sec_refboost"),
         InlineKeyboardButton("💣 Force Expire Plan", callback_data="sec_expire")],
        [InlineKeyboardButton("🔍 Ghost: View User", callback_data="sec_ghost"),
         InlineKeyboardButton("💬 DM User", callback_data="sec_dm")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="sec_broadcast")],
    ]
    await update.message.reply_text(
        "🔐 *Secret Admin Panel*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── SECRET STATES ────────────────────────────────────────────────────────────

SEC_BAN, SEC_UNBAN, SEC_SETBAL_ID, SEC_SETBAL_AMT, SEC_GHOST, SEC_BROADCAST, SEC_REFBOOST_ID, SEC_REFBOOST_CNT, SEC_SILENT, SEC_UNSILENT, SEC_EXPIRE, SEC_RESET, SEC_DM_ID, SEC_DM_MSG = range(9, 23)

async def secret_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        await q.answer("❌ Access denied.", show_alert=True)
        return
    await q.answer()
    data = q.data

    if data == "sec_withdrawals":
        withdrawals = get_all_withdrawals()
        if not withdrawals:
            await q.message.reply_text("✅ Koi pending withdrawal nahi hai.")
            return
        text = "📋 *Pending Withdrawals:*\n\n"
        for w in withdrawals:
            wid, uid, amount, wallet, status, req_at = w
            text += f"ID:{wid} | User:{uid} | ₹{amount:.0f} | UPI:{wallet}\n"
        await q.message.reply_text(text, parse_mode="Markdown")

    elif data == "sec_users":
        users = get_all_users()
        text = f"👥 *Total Users: {len(users)}*\n\n"
        for u in users[:20]:
            uid, uname, bal, invested, joined = u
            banned = "🚫" if uname and uname.startswith("BANNED_") else "✅"
            text += f"{banned} `{uid}` | @{uname} | ₹{bal:.0f} bal | ₹{invested:.0f} inv\n"
        await q.message.reply_text(text, parse_mode="Markdown")

    elif data == "sec_ban":
        await q.message.reply_text("🚫 Ban karne ke liye User ID daalo:")
        return SEC_BAN

    elif data == "sec_unban":
        await q.message.reply_text("✅ Unban karne ke liye User ID daalo:")
        return SEC_UNBAN

    elif data == "sec_setbal":
        await q.message.reply_text("💰 Balance set karne ke liye User ID daalo:")
        return SEC_SETBAL_ID

    elif data == "sec_ghost":
        await q.message.reply_text("🔍 Jis user ka stats dekhna hai uska User ID daalo:")
        return SEC_GHOST

    elif data == "sec_broadcast":
        await q.message.reply_text("📢 Broadcast message likho (sabhi users ko jayega):")
        return SEC_BROADCAST

    elif data == "sec_refboost":
        await q.message.reply_text("🚀 Referral boost ke liye User ID daalo:")
        return SEC_REFBOOST_ID

    elif data == "sec_stats":
        users = get_all_users()
        withdrawals = get_all_withdrawals()
        total_invested = sum(u[3] for u in users)
        total_bal = sum(u[2] for u in users)
        await q.message.reply_text(
            f"📊 *Bot Stats*\n\n"
            f"👥 Total Users: {len(users)}\n"
            f"💰 Total Invested: ₹{total_invested:.0f}\n"
            f"💵 Total Balance (all users): ₹{total_bal:.0f}\n"
            f"⏳ Pending Withdrawals: {len(withdrawals)}",
            parse_mode="Markdown"
        )

    elif data == "sec_silent":
        await q.message.reply_text("🔇 Silent karne ke liye User ID daalo:")
        return SEC_SILENT

    elif data == "sec_unsilent":
        await q.message.reply_text("🔊 Unsilent karne ke liye User ID daalo:")
        return SEC_UNSILENT

    elif data == "sec_expire":
        await q.message.reply_text("💣 Force expire ke liye User ID daalo:")
        return SEC_EXPIRE

    elif data == "sec_reset":
        await q.message.reply_text("🔄 Reset karne ke liye User ID daalo (balance + investments zero ho jayenge):")
        return SEC_RESET

    elif data == "sec_dm":
        await q.message.reply_text("💬 DM ke liye User ID daalo:")
        return SEC_DM_ID

async def sec_ban_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
        ban_user(uid)
        await update.message.reply_text(f"🚫 User `{uid}` banned kar diya.", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Invalid ID.")
    return ConversationHandler.END

async def sec_unban_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
        unban_user(uid)
        await update.message.reply_text(f"✅ User `{uid}` unban kar diya.", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Invalid ID.")
    return ConversationHandler.END

async def sec_setbal_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["setbal_uid"] = int(update.message.text.strip())
        await update.message.reply_text("💰 Naya balance amount daalo (₹):")
        return SEC_SETBAL_AMT
    except:
        await update.message.reply_text("❌ Invalid ID.")
        return ConversationHandler.END

async def sec_setbal_amt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        uid = ctx.user_data["setbal_uid"]
        set_balance(uid, amount)
        await update.message.reply_text(f"✅ User `{uid}` ka balance ₹{amount:.0f} set kar diya.", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Error.")
    return ConversationHandler.END

async def sec_ghost_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
        user, investments, withdrawals = get_user_stats(uid)
        if not user:
            await update.message.reply_text("❌ User nahi mila.")
            return ConversationHandler.END
        uid_, uname, bal, invested, joined = user[0], user[1], user[2], user[3], user[4]
        text = (
            f"🔍 *Ghost View — User `{uid_}`*\n\n"
            f"👤 @{uname}\n"
            f"💰 Balance: ₹{bal:.2f}\n"
            f"📈 Total Invested: ₹{invested:.0f}\n"
            f"📅 Joined: {joined[:10]}\n"
            f"📦 Investments: {len(investments)}\n"
            f"💸 Withdrawals: {len(withdrawals)}"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Error.")
    return ConversationHandler.END

async def sec_broadcast_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip()
    users = get_all_users()
    sent, failed = 0, 0
    for u in users:
        try:
            await ctx.bot.send_message(chat_id=u[0], text=f"📢 *Admin Message:*\n\n{msg}", parse_mode="Markdown")
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(f"📢 Broadcast done!\n✅ Sent: {sent} | ❌ Failed: {failed}")
    return ConversationHandler.END

async def sec_refboost_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["refboost_uid"] = int(update.message.text.strip())
        await update.message.reply_text("🚀 Kitne referrals add karne hain? (number daalo):")
        return SEC_REFBOOST_CNT
    except:
        await update.message.reply_text("❌ Invalid ID.")
        return ConversationHandler.END

async def sec_refboost_cnt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text.strip())
        uid = ctx.user_data["refboost_uid"]
        boost_referral(uid, count)
        await update.message.reply_text(f"🚀 User `{uid}` ko {count} referrals boost kar diye.", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Error.")
    return ConversationHandler.END

async def sec_silent_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
        silent_user(uid, True)
        await update.message.reply_text(f"🔇 User `{uid}` ko silent kar diya. Ab use koi notification nahi milegi.", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Invalid ID.")
    return ConversationHandler.END

async def sec_unsilent_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
        silent_user(uid, False)
        await update.message.reply_text(f"🔊 User `{uid}` unsilent kar diya.", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Invalid ID.")
    return ConversationHandler.END

async def sec_expire_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
        count = force_expire_plans(uid)
        await update.message.reply_text(f"💣 User `{uid}` ke {count} plan(s) force expire kar diye.", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Invalid ID.")
    return ConversationHandler.END

async def sec_reset_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
        reset_user(uid)
        await update.message.reply_text(f"🔄 User `{uid}` ka balance aur investments reset kar diye.", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Invalid ID.")
    return ConversationHandler.END

async def sec_dm_id_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["dm_uid"] = int(update.message.text.strip())
        await update.message.reply_text("💬 Ab message likho jo user ko bhejna hai:")
        return SEC_DM_MSG
    except:
        await update.message.reply_text("❌ Invalid ID.")
        return ConversationHandler.END

async def sec_dm_msg_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = ctx.user_data.get("dm_uid")
    msg = update.message.text.strip()
    try:
        await ctx.bot.send_message(chat_id=uid, text=f"📩 *Admin Message:*\n\n{msg}", parse_mode="Markdown")
        await update.message.reply_text(f"✅ Message user `{uid}` ko bhej diya.", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Message nahi bheja ja saka. User ne bot block kiya hoga.")
    return ConversationHandler.END

# ─── AUTO EXPIRE NOTIFY ───────────────────────────────────────────────────────

async def check_expired_plans(ctx: ContextTypes.DEFAULT_TYPE):
    import sqlite3
    from database import DB
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    now = datetime.now()
    c.execute("SELECT id, user_id, amount, expires_at FROM investments WHERE expires_at IS NOT NULL")
    for inv_id, user_id, amount, expires_at in c.fetchall():
        exp = datetime.fromisoformat(expires_at)
        diff = (exp - now).total_seconds()
        if 0 < diff <= 3600:
            try:
                await ctx.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ Aapka ₹{amount:.0f} wala plan *1 ghante mein expire* hone wala hai!\nAbhi withdraw karo! 💸",
                    parse_mode="Markdown"
                )
            except:
                pass
    conn.close()

# ─── CANCEL ───────────────────────────────────────────────────────────────────

MU_SETBAL, MU_DM, MU_REFBOOST = range(23, 26)

def build_user_report(uid: int):
    update_earnings()
    user, investments, withdrawals = get_user_full_data(uid)
    if not user:
        return f"\u274c User `{uid}` nahi mila.", None
    user_id, username, balance, total_invested, joined_at, referred_by, referral_count = user
    now = datetime.now()
    banned = is_banned(uid)
    muted = is_silent(uid)
    clean_name = (username or "N/A").replace("BANNED_", "")
    status_icon = "\U0001f6ab" if banned else ("\U0001f507" if muted else "\u2705")
    status_text = "BANNED" if banned else ("Silent" if muted else "Active")
    text = (
        f"\U0001f464 *USER REPORT*\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"\U0001f194 ID: `{user_id}`\n"
        f"\U0001f464 Name: @{clean_name}\n"
        f"{status_icon} Status: {status_text}\n"
        f"\U0001f4c5 Joined: {joined_at[:10]}\n"
        f"\U0001f465 Referred By: `{referred_by or 'None'}`\n"
        f"\U0001f517 Referrals: {referral_count or 0}\n"
        f"\U0001f4b0 Balance: \u20b9{balance:.2f}\n"
        f"\U0001f4b3 Total Invested: \u20b9{total_invested:.0f}\n"
    )
    text += f"\n\U0001f4c8 *INVESTMENTS ({len(investments)})*\n"
    active_hr = 0
    for i, inv in enumerate(investments, 1):
        amount, per_hour, started_at, expires_at = inv
        expired = expires_at and now >= datetime.fromisoformat(expires_at)
        if not expired:
            active_hr += per_hour
        days_left = ""
        if expires_at and not expired:
            d = (datetime.fromisoformat(expires_at) - now).days + 1
            days_left = f" | {d}d left"
        st = "\u26d4" if expired else "\u2705"
        text += f"  {i}. {st} \u20b9{amount:.0f} | \u20b9{per_hour:.2f}/hr{days_left} | {started_at[:10]}\n"
    text += f"  \u26a1 Active: \u20b9{active_hr:.2f}/hr | \u20b9{active_hr*24:.0f}/day\n"
    text += f"\n\U0001f4b8 *WITHDRAWALS ({len(withdrawals)})*\n"
    paid_total = pending_total = 0
    for i, w in enumerate(withdrawals, 1):
        amount, wallet, wstatus, req_at = w
        em = "\u2705" if wstatus == "paid" else "\u23f3"
        text += f"  {i}. {em} \u20b9{amount:.0f} \u2192 `{wallet}` | {req_at[:10]}\n"
        if wstatus == "paid": paid_total += amount
        else: pending_total += amount
    if withdrawals:
        text += f"  \u2705 Paid: \u20b9{paid_total:.0f} | \u23f3 Pending: \u20b9{pending_total:.0f}\n"
    ban_btn = InlineKeyboardButton("\u2705 Unban", callback_data=f"mu_unban_{uid}") if banned else InlineKeyboardButton("\U0001f6ab Ban", callback_data=f"mu_ban_{uid}")
    mute_btn = InlineKeyboardButton("\U0001f50a Unsilent", callback_data=f"mu_unsilent_{uid}") if muted else InlineKeyboardButton("\U0001f507 Silent", callback_data=f"mu_silent_{uid}")
    keyboard = [
        [ban_btn, mute_btn],
        [InlineKeyboardButton("\U0001f4b0 Set Balance", callback_data=f"mu_setbal_{uid}"),
         InlineKeyboardButton("\U0001f4a3 Expire Plans", callback_data=f"mu_expire_{uid}")],
        [InlineKeyboardButton("\U0001f504 Reset User", callback_data=f"mu_reset_{uid}"),
         InlineKeyboardButton("\U0001f4ac DM User", callback_data=f"mu_dm_{uid}")],
        [InlineKeyboardButton("\U0001f680 Ref Boost", callback_data=f"mu_refboost_{uid}"),
         InlineKeyboardButton("\U0001f504 Refresh", callback_data=f"mu_refresh_{uid}")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


async def user_full_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not ctx.args:
        await update.message.reply_text("\u274c Usage: /user <user_id>")
        return
    try:
        uid = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("\u274c Sirf number daalo. Example: /user 123456789")
        return
    text, markup = build_user_report(uid)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def manage_user_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        await q.answer("\u274c Access denied.", show_alert=True)
        return
    await q.answer()
    parts = q.data.split("_")
    action = parts[1]
    uid = int(parts[2])
    if action == "ban":
        ban_user(uid)
        await q.answer("\U0001f6ab Banned!", show_alert=True)
    elif action == "unban":
        unban_user(uid)
        await q.answer("\u2705 Unbanned!", show_alert=True)
    elif action == "silent":
        silent_user(uid, True)
        await q.answer("\U0001f507 Silenced!", show_alert=True)
    elif action == "unsilent":
        silent_user(uid, False)
        await q.answer("\U0001f50a Unsilenced!", show_alert=True)
    elif action == "expire":
        count = force_expire_plans(uid)
        await q.answer(f"\U0001f4a3 {count} plan(s) expired!", show_alert=True)
    elif action == "reset":
        reset_user(uid)
        await q.answer("\U0001f504 User reset!", show_alert=True)
    elif action == "setbal":
        ctx.user_data["mu_setbal_uid"] = uid
        await q.message.reply_text(f"\U0001f4b0 User `{uid}` ka naya balance daalo (\u20b9):", parse_mode="Markdown")
        return MU_SETBAL
    elif action == "dm":
        ctx.user_data["mu_dm_uid"] = uid
        await q.message.reply_text(f"\U0001f4ac User `{uid}` ko message likho:", parse_mode="Markdown")
        return MU_DM
    elif action == "refboost":
        ctx.user_data["mu_refboost_uid"] = uid
        await q.message.reply_text(f"\U0001f680 User `{uid}` ko kitne referrals add karne hain?", parse_mode="Markdown")
        return MU_REFBOOST
    text, markup = build_user_report(uid)
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def mu_setbal_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        uid = ctx.user_data["mu_setbal_uid"]
        set_balance(uid, amount)
        text, markup = build_user_report(uid)
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
    except:
        await update.message.reply_text("\u274c Invalid amount.")
    return ConversationHandler.END


async def mu_dm_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = ctx.user_data.get("mu_dm_uid")
    msg = update.message.text.strip()
    try:
        await ctx.bot.send_message(chat_id=uid, text=f"\U0001f4e9 *Admin Message:*\n\n{msg}", parse_mode="Markdown")
        await update.message.reply_text(f"\u2705 Message user `{uid}` ko bhej diya.", parse_mode="Markdown")
    except:
        await update.message.reply_text("\u274c Message nahi bheja ja saka.")
    return ConversationHandler.END


async def mu_refboost_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text.strip())
        uid = ctx.user_data["mu_refboost_uid"]
        boost_referral(uid, count)
        text, markup = build_user_report(uid)
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
    except:
        await update.message.reply_text("\u274c Invalid number.")
    return ConversationHandler.END


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled. /start se dobara shuru karo.")
    return ConversationHandler.END

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    withdraw_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(withdraw_start, pattern="^withdraw$")],
        states={
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount)],
            WITHDRAW_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_upi)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    secret_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(secret_callback, pattern="^sec_")],
        states={
            SEC_BAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, sec_ban_handler)],
            SEC_UNBAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, sec_unban_handler)],
            SEC_SETBAL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, sec_setbal_id)],
            SEC_SETBAL_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sec_setbal_amt)],
            SEC_GHOST: [MessageHandler(filters.TEXT & ~filters.COMMAND, sec_ghost_handler)],
            SEC_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, sec_broadcast_handler)],
            SEC_REFBOOST_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, sec_refboost_id)],
            SEC_REFBOOST_CNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sec_refboost_cnt)],
            SEC_SILENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sec_silent_handler)],
            SEC_UNSILENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sec_unsilent_handler)],
            SEC_EXPIRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sec_expire_handler)],
            SEC_RESET: [MessageHandler(filters.TEXT & ~filters.COMMAND, sec_reset_handler)],
            SEC_DM_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, sec_dm_id_handler)],
            SEC_DM_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, sec_dm_msg_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    manage_user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(manage_user_callback, pattern="^mu_")],
        states={
            MU_SETBAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, mu_setbal_handler)],
            MU_DM: [MessageHandler(filters.TEXT & ~filters.COMMAND, mu_dm_handler)],
            MU_REFBOOST: [MessageHandler(filters.TEXT & ~filters.COMMAND, mu_refboost_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("user", user_full_info))
    app.add_handler(CallbackQueryHandler(invest_start, pattern="^invest$"))
    app.add_handler(CallbackQueryHandler(plan_selected, pattern="^plan_"))
    app.add_handler(CallbackQueryHandler(dashboard, pattern="^dashboard$"))
    app.add_handler(CallbackQueryHandler(how_works, pattern="^howworks$"))
    app.add_handler(CallbackQueryHandler(refer_panel, pattern="^refer$"))
    app.add_handler(CallbackQueryHandler(admin_paid, pattern="^paid_"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(withdraw_conv)
    app.add_handler(secret_conv)
    app.add_handler(manage_user_conv)

    if app.job_queue:
        app.job_queue.run_repeating(check_expired_plans, interval=3600, first=10)

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
