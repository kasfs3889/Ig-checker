import os
import time
import asyncio
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import database  # Database file import ki hai

# ----------------- Flask App for Render Web Service -----------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Bot is active and running!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ----------------- Bot Configuration & States -----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9108604045:AAGqQJRMLhEypLYnyVRdELsva0er_2npiJI") # Render environment variable se uthayega
PASSWORD = "NexT1010"

# In-memory states for ongoing workflows (like password typing or link inputs)
waiting_for_password = set()
waiting_for_link = set()
active_watchers = {}  # user_id -> True/False control for live stats

# ----------------- Handlers & Logic -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Database se check karein ki user pehle se authenticated hai ya nahi
    if database.is_authenticated(user_id):
        await show_main_menu(update)
    else:
        waiting_for_password.add(user_id)
        await update.message.reply_text(
            "🔒 **Access Locked**\n\nPlease enter the password to unlock the bot:",
            parse_mode="Markdown"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # 1. Password Check
    if user_id in waiting_for_password:
        if text == PASSWORD:
            waiting_for_password.remove(user_id)
            database.add_authenticated_user(user_id)  # Database mein save kar diya
            await update.message.reply_text("✅ Password Verified Successfully!")
            await show_main_menu(update)
        else:
            await update.message.reply_text("❌ Incorrect Password! Try again:")
        return

    # 2. Waiting for Reel/Post Link for Stats Watcher
    if user_id in waiting_for_link:
        waiting_for_link.remove(user_id)
        url = text
        active_watchers[user_id] = True
        
        # Send initial message with Stop button
        keyboard = [[InlineKeyboardButton("🛑 Stop Stats", callback_data="stop_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        msg = await update.message.reply_text(
            f"📊 **Live Stats Watcher Started**\nLink: {url}\n\nFetching initial data...",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        # Start background loop for 1-minute updates
        asyncio.create_task(stats_loop(update, msg, url, user_id))
        return

    if not database.is_authenticated(user_id):
        await update.message.reply_text("Please use /start and enter the password first.")

async def show_main_menu(update: Update):
    keyboard = [
        [InlineKeyboardButton("🚀 Start IDs Generation", callback_data="menu_gen_ids")],
        [InlineKeyboardButton("📊 Watch Stats", callback_data="menu_watch_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if message comes from callback or command
    if update.callback_query:
        await update.callback_query.message.edit_text(
            "🎛 **Main Menu**\nChoose an option below:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "🎛 **Main Menu**\nChoose an option below:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not database.is_authenticated(user_id):
        await query.edit_message_text("Session expired or unauthorized. Please use /start again.")
        return

    if query.data == "menu_gen_ids":
        # Generate dummy/sample generated accounts buttons
        keyboard = [
            [InlineKeyboardButton("ID #1: user_alpha99", callback_data="get_id_1")],
            [InlineKeyboardButton("ID #2: insta_pro_2026", callback_data="get_id_2")],
            [InlineKeyboardButton("ID #3: gamer_x_bot", callback_data="get_id_3")],
            [InlineKeyboardButton("« Back to Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("⚡ **Generated Accounts List**\nClick any ID to view details:", reply_markup=reply_markup, parse_mode="Markdown")

    elif query.data.startswith("get_id_"):
        id_num = query.data.split("_")[-1]
        # Sample account details data
        accounts = {
            "1": {"username": "user_alpha99", "pass": "Pass#9988", "mail": "alpha99@tempmail.com"},
            "2": {"username": "insta_pro_2026", "pass": "Secure#2026", "mail": "pro2026@tempmail.com"},
            "3": {"username": "gamer_x_bot", "pass": "Gamer!123", "mail": "gamerbot@tempmail.com"}
        }
        acc = accounts.get(id_num, {"username": "unknown", "pass": "N/A", "mail": "N/A"})
        
        details = (
            f"🔐 **Account Credentials:**\n\n"
            f"👤 **Username:** `{acc['username']}`\n"
            f"🔑 **Password:** `{acc['pass']}`\n"
            f"📧 **Bonded Mail:** `{acc['mail']}`"
        )
        keyboard = [[InlineKeyboardButton("« Back to IDs List", callback_data="menu_gen_ids")]]
        await query.edit_message_text(details, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "menu_watch_stats":
        waiting_for_link.add(user_id)
        keyboard = [[InlineKeyboardButton("« Back to Menu", callback_data="back_to_menu")]]
        await query.edit_message_text(
            "🔗 Please send the **Instagram Reel or Post Link** in the chat now:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif query.data == "back_to_menu":
        await show_main_menu(update)

    elif query.data == "stop_stats":
        active_watchers[user_id] = False
        await query.edit_message_text("🛑 **Stats Watcher Stopped** successfully.\n\nUse /start to go back to the menu.")

async def stats_loop(update, msg, url, user_id):
    # Simulated live stats tracker loop (Updates every 60 seconds)
    counter = 1
    import random
    views = random.randint(1200, 1500)
    likes = random.randint(150, 200)

    while active_watchers.get(user_id, False):
        await asyncio.sleep(60) # 1 minute interval
        if not active_watchers.get(user_id, False):
            break
        
        views += random.randint(20, 80)
        likes += random.randint(2, 10)
        
        keyboard = [[InlineKeyboardButton("🛑 Stop Stats", callback_data="stop_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            text = (
                f"📊 **Live Stats Update (Minute {counter})**\n"
                f"🔗 Link: {url}\n\n"
                f"👀 **Views:** `{views}`\n"
                f"❤️ **Likes:** `{likes}`\n"
                f"⏱ *Status: Monitoring active...*"
            )
            await msg.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
            counter += 1
        except Exception:
            break

def main():
    # Database initialize karein jab bot start ho
    database.init_db()

    # Start Flask in a background thread so Render port binding succeeds
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Initialize Telegram Bot
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is starting via Polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
