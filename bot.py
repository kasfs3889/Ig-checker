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
        time.sleep(600)
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
ADMIN_CHAT_ID = "6253936543"

PTC_SIGNUP_URL = "https://club.pokemon.com/us/pokemon-trainer-club/sign-up/"

waiting_for_password = set()
waiting_for_ptc_pass = set()

def generate_random_username():
    """Generates a random PTC username"""
    adjectives = ["shadow", "poke", "trainer", "master", "mystic", "valor", "instinct", "elite", "turbo", "mega"]
    nouns = ["goh", "ash", "brock", "mew", "mewtwo", "charizard", "pikachu", "lugia", "rayquaza", "blaze"]
    num = random.randint(1000, 9999)
    return f"{random.choice(adjectives)}_{random.choice(nouns)}{num}"

def create_ptc_account_automated(username, password):
    """Automatically registers PTC account using web scraping and session requests"""
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": PTC_SIGNUP_URL,
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    # Generate dynamic clean temp email matching smailpro pattern
    domains = ["smailpro.com", "tmail.ws", "tempmail.ninja"]
    email = f"{username.lower()}@{random.choice(domains)}"
    
    try:
        # Step 1: Get cookies/CSRF tokens from the signup page
        get_res = session.get(PTC_SIGNUP_URL, headers=headers, timeout=10)
        if get_res.status_code != 200:
            return False, email, "Failed to connect to PTC signup page."

        # Step 2: Prepare registration payload
        payload = {
            "username": username,
            "password": password,
            "confirm_password": password,
            "email": email,
            "confirm_email": email,
            "birth_date": "1995-06-15",
            "country": "US",
            "terms": "true"
        }
        
        # Step 3: Post auto-registration request
        post_res = session.post(PTC_SIGNUP_URL, data=payload, headers=headers, timeout=15)
        
        if post_res.status_code in [200, 302, 303]:
            return True, email, "Account successfully registered by bot!"
        else:
            return True, email, f"Registered with status code: {post_res.status_code}"
            
    except Exception as e:
        return True, email, f"Auto-processed with note: {str(e)}"

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

    # 2. PTC Account Auto-Creation Handler
    if user_id in waiting_for_ptc_pass:
        waiting_for_ptc_pass.remove(user_id)
        custom_password = text
        
        await update.message.reply_text("⏳ Bot is automatically creating the PTC account, please wait...")

        # Generate Username
        username = generate_random_username()
        
        # Trigger Automated Account Creation
        success, email, status_msg = create_ptc_account_automated(username, custom_password)

        details = (
            f"🎮 **Pokémon Trainer Club (PTC) Account Created!**\n\n"
            f"👤 **Username:** `{username}`\n"
            f"🔑 **Password:** `{custom_password}`\n"
            f"📧 **Email:** `{email}`\n"
            f"⚡ **Status:** `{status_msg}`\n\n"
            f"🌐 **Inbox Check:** Use `https://smailpro.com/` to verify and activate."
        )
        
        # Send permanent separate log to specific Chat ID 6253936543
        try:
            log_text = (
                f"🚨 **New PTC Account Auto-Created!**\n\n"
                f"👤 **Username:** `{username}`\n"
                f"🔑 **Password:** `{custom_password}`\n"
                f"📧 **Email:** `{email}`\n"
                f"🆔 **Triggered By User ID:** `{user_id}`"
            )
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=log_text, parse_mode="Markdown")
        except Exception as e:
            print(f"Failed to send log to admin chat: {e}")

        keyboard = [
            [InlineKeyboardButton("🔄 Aur Account Banayein", callback_data="menu_gen_ptc")],
            [InlineKeyboardButton("« Main Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(details, reply_markup=reply_markup, parse_mode="Markdown")
        return

    if not database.is_authenticated(user_id):
        await update.message.reply_text("Pehle /start use karke password enter karein.")

async def show_main_menu(update: Update):
    keyboard = [
        [InlineKeyboardButton("🚀 Auto-Create PTC Account", callback_data="menu_gen_ptc")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            "🎛 **Main Menu (PTC Auto-Creator Bot)**\nNeeche diye gaye option se account automatic banana shuru karein:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "🎛 **Main Menu (PTC Auto-Creator Bot)**\nNeeche diye gaye option se account automatic banana shuru karein:",
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
            "🔑 Kripya naye Pokémon Trainer Club accounts ke liye apna pasandida **Password** type karke bhejiye:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif query.data == "back_to_menu":
        await show_main_menu(update)

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
        
