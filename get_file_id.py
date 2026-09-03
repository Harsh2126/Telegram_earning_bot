from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from telegram import Update
from config import BOT_TOKEN

async def get_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        plan_name = update.message.caption or "Unknown"
        print(f"\n✅ Plan: {plan_name}")
        print(f"📋 File ID: {update.message.video.file_id}\n")
        await update.message.reply_text(f"File ID:\n`{update.message.video.file_id}`", parse_mode="Markdown")

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.VIDEO, get_id))
print("Bot ready — ab apna video bhejo caption mein plan ka naam likhke (Starter/Basic/Pro/Premium)")
app.run_polling()
