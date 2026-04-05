import os
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from supabase import create_client, Client

app = Flask(__name__)

# Config from Environment Variables
TOKEN = os.environ.get("TELEGRAM_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY")
CHANNEL_ID = "@YourChannelHandle" # Change this to your channel's username

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
telegram_app = Application.builder().token(TOKEN).build()

@app.route('/api/index', methods=['POST'])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        await telegram_app.process_update(update)
    return "ok"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    referrer_id = context.args[0] if context.args else None
    
    # Save/Update user in Supabase
    supabase.table("users").upsert({
        "telegram_id": user_id, 
        "invited_by": referrer_id
    }, on_conflict="telegram_id").execute()

    keyboard = [
        [InlineKeyboardButton("1. Join Channel", url="https://t.me/YourChannelHandle")],
        [InlineKeyboardButton("2. Verify & Enter", callback_data="verify")]
    ]
    await update.message.reply_text(
        "Welcome! To enter the competition:\n1. Join our channel\n2. Click verify below.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
    
    if member.status in ['member', 'administrator', 'creator']:
        # Mark as verified
        res = supabase.table("users").update({"is_verified": True}).eq("telegram_id", user_id).execute()
        
        # Reward the person who invited them
        invited_by = res.data[0].get("invited_by")
        if invited_by:
            supabase.rpc("increment_points", {"row_id": invited_by}).execute()

        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        await query.message.edit_text(f"✅ Verified! You are in.\n\nYour Referral Link: `{ref_link}`", parse_mode="Markdown")
    else:
        await query.answer("❌ Please join the channel first!", show_alert=True)

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(verify))
