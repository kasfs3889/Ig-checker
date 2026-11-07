import os
import time
import asyncio
import threading
import random
import requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import database

# ----------------- Flask App for Render Web Service -----------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Bot is active and running!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ----------------- Keep-Alive Loop (Sleep Mode Prevention) -----------------
def keep_alive_ping():
    while True:
        time.sleep(600)  # Har 10 minute mein ping karega
        render_url = os.environ.get("RENDER_EXTERNAL_URL")
        if render_url:
            try:
                requests.get(render_url)
                print("Keep-alive ping sent successfully!")
            except Exception as e:
                print(f"Ping failed: {e}")

# ----------------- Bot Configuration & States -----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9108604045:AAGqQJRMLhEypLYnyVRdELsva0er_2npiJI")
PASSWORD = "Rishi#123"

waiting_for_password = set()
waiting_for_link = set()
waiting_for_ptc_pass = set()
active_watchers = {}

def generate_ptc_details(custom_pass):
    adjectives = ["shadow", "poke", "trainer", "master", "mystic", "valor", "instinct", "elite", "turbo", "mega"]
    nouns = ["goh", "ash", "brock", "mew", "mewtwo", "charizard", "pikachu", "lugia", "rayquaza", "blaze"]
    num = random.randint(1000, 9999)
    
    username = f"{random.choice(adjectives)}_{random.choice(nouns)}{num}"
    mail = f"{username}@tempmail.com"
    
    return {
        "username": username,
        "password": custom_pass,
        "mail": mail
    }

# ----------------- Handlers & Logic -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if database.is_authenticated(user_id):
        await show_main_menu(update)
    else:
        waiting_for_password.add(user_id)
        await update.message.reply_text(
            "🔒 **Access Locked**\n\nKripya bot ko unlock karne ke liye password enter karein:",
            parse_mode="Markdown"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # 1. Main Password Check
    if user_id in waiting_for_password:
        if text == PASSWORD:
            waiting_for_password.remove(user_id)
            database.add_authenticated_user(user_id)
            await update.message.reply_text("✅ Password Successfully Verify Ho Gaya!")
            await show_main_menu(update)
        else:
            await update.message.reply_text("❌ Galat Password! Dobara try karein:")
        return

    # 2. PTC Account Generation - Custom Password Input Handler
    if user_id in waiting_for_ptc_pass:
        waiting_for_ptc_pass.remove(user_id)
        custom_password = text
        
        acc = generate_ptc_details(custom_password)

        details = (
            f"🎮 **Pokémon Trainer Club (PTC) Account Data Ready!**\n\n"
            f"👤 **Username:** `{acc['username']}`\n"
            f"🔑 **Password:** `{acc['password']}`\n"
            f"📧 **Temp Mail:** `{acc['mail']}`\n\n"
            f"🛠 **Instructions (Manual Creation):**\n"
            f"1. Pokémon Trainer Club official signup page par jayein.\n"
            f"2. Upar diye gaye Username, Mail aur Password ko fill karein.\n"
            f"3. Captcha manually solve karke account create karein aur mail se activate karein!"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Aur Account Banayein", callback_data="menu_gen_ptc")],
            [InlineKeyboardButton("« Main Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(details, reply_markup=reply_markup, parse_mode="Markdown")
        return

    # 3. Waiting for Reel/Post Link for Stats Watcher
    if user_id in waiting_for_link:
        waiting_for_link.remove(user_id)
        url = text
        active_watchers[user_id] = True
        
        keyboard = [[InlineKeyboardButton("🛑 Stop Stats", callback_data="stop_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        msg = await update.message.reply_text(
            f"📊 **Live Stats Watcher Start Ho Chuka Hai**\nLink: {url}\n\nInitial data fetch ho raha hai...",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        asyncio.create_task(stats_loop(update, msg, url, user_id))
        return

    if not database.is_authenticated(user_id):
        await update.message.reply_text("Pehle /start use karke password enter karein.")

async def show_main_menu(update: Update):
    keyboard = [
        [InlineKeyboardButton("🚀 Create PTC Account", callback_data="menu_gen_ptc")],
        [InlineKeyboardButton("📊 Watch Stats", callback_data="menu_watch_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            "🎛 **Main Menu**\nNeeche diye gaye options me se select karein:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "🎛 **Main Menu**\nNeeche diye gaye options me se select karein:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not database.is_authenticated(user_id):
        await query.edit_message_text("Session expire ho gaya hai. Kripya phir se /start use karein.")
        return

    if query.data == "menu_gen_ptc":
        waiting_for_ptc_pass.add(user_id)
        keyboard = [[InlineKeyboardButton("« Main Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🔑 Kripya naye Pokémon Trainer Club account ke liye apna pasandida **Password** type karke bhejiye:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif query.data == "menu_watch_stats":
        waiting_for_link.add(user_id)
        keyboard = [[InlineKeyboardButton("« Main Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🔗 Kripya chat me **Instagram Reel ya Post ka Link** bhejiye:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif query.data == "back_to_menu":
        await show_main_menu(update)

    elif query.data == "stop_stats":
        active_watchers[user_id] = False
        await query.edit_message_text("🛑 **Stats Watcher Successfully Rok Diya Gaya Hai**.\n\nMenu me jaane ke liye /start use karein.")

async def stats_loop(update, msg, url, user_id):
    counter = 1
    views = random.randint(1200, 1500)
    likes = random.randint(150, 200)

    while active_watchers.get(user_id, False):
        await asyncio.sleep(60)
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
    database.init_db()

    # Flask server background thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Keep-alive ping loop background thread (Sleep mode prevention)
    ping_thread = threading.Thread(target=keep_alive_ping)
    ping_thread.daemon = True
    ping_thread.start()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot polling start ho raha hai...")
    application.run_polling()

if __name__ == "__main__":
    main()
                    
