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

SECMAIL_API = "https://www.1secmail.com/api/v1/"

waiting_for_password = set()
waiting_for_ptc_pass = set()

def generate_random_username():
    """Generates a random PTC username"""
    adjectives = ["shadow", "poke", "trainer", "master", "mystic", "valor", "instinct", "elite", "turbo", "mega"]
    nouns = ["goh", "ash", "brock", "mew", "mewtwo", "charizard", "pikachu", "lugia", "rayquaza", "blaze"]
    num = random.randint(1000, 9999)
    return f"{random.choice(adjectives)}_{random.choice(nouns)}{num}"

def generate_temp_email():
    """Generates a real working temp email from 1SecMail API for unlimited accounts"""
    try:
        response = requests.get(f"{SECMAIL_API}?action=genRandomMail&count=1")
        if response.status_code == 200:
            mail_list = response.json()
            if mail_list:
                full_email = mail_list[0]
                login, domain = full_email.split('@')
                return login, domain
    except Exception as e:
        print(f"Error generating email: {e}")
    return None, None

def check_inbox(login, domain):
    """Checks inbox for incoming verification mail/OTP"""
    try:
        url = f"{SECMAIL_API}?action=getMessages&login={login}&domain={domain}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error checking inbox: {e}")
    return []

def read_message(login, domain, message_id):
    """Reads specific message content"""
    try:
        url = f"{SECMAIL_API}?action=readMessage&login={login}&domain={domain}&id={message_id}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error reading message: {e}")
    return None

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
        
        # Generate Username
        username = generate_random_username()
        
        # Generate Real 1SecMail Temp Email
        login, domain = generate_temp_email()
        if not login or not domain:
            await update.message.reply_text("❌ Temp mail generate karne me fail ho gaya. Dobara try karein.")
            return

        email = f"{login}@{domain}"

        details = (
            f"🎮 **Pokémon Trainer Club (PTC) Account Data Ready!**\n\n"
            f"👤 **Username:** `{username}`\n"
            f"🔑 **Password:** `{custom_password}`\n"
            f"📧 **Temp Mail:** `{email}`\n\n"
            f"📥 **Inbox Checking Command:**\n"
            f"`/checkmail {login} {domain}`\n\n"
            f"🛠 **Instructions:**\n"
            f"1. PTC official signup page par jayein.\n"
            f"2. Upar diye gaye details fill karein.\n"
            f"3. Mail aane par upar di gayi command se inbox check karke account activate karein!"
        )
        
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
        [InlineKeyboardButton("🚀 Create Unlimited PTC Accounts", callback_data="menu_gen_ptc")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            "🎛 **Main Menu (PTC Generator Bot)**\nNeeche diye gaye option se account generate karna shuru karein:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "🎛 **Main Menu (PTC Generator Bot)**\nNeeche diye gaye option se account generate karna shuru karein:",
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
            "🔑 Kripya naye Pokémon Trainer Club accounts ke liye apna pasandida **Password** type karke bhejiye (yeh password sabhi naye accounts ke liye use hoga):",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif query.data == "back_to_menu":
        await show_main_menu(update)

async def checkmail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to check inbox manually: /checkmail <login> <domain>"""
    user_id = update.effective_user.id
    if not database.is_authenticated(user_id):
        await update.message.reply_text("Pehle /start karke login karein.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("⚠️ Sahi format use karein:\n`/checkmail <login> <domain>`")
        return

    login = args[0]
    domain = args[1]
    
    await update.message.reply_text(f"🔍 Inbox check kiya ja raha hai: `{login}@{domain}`...")

    messages = check_inbox(login, domain)
    if not messages:
        await update.message.reply_text("📭 Inbox abhi khali hai. Kuch der baad dobara check karein.")
        return

    response_text = "📬 **Received Messages:**\n\n"
    for msg in messages:
        msg_id = msg.get('id')
        subject = msg.get('subject')
        sender = msg.get('from')
        
        mail_data = read_message(login, domain, msg_id)
        body_snippet = mail_data.get('body', '')[:150] if mail_data else "Read error"

        response_text += f"🆔 **ID:** {msg_id}\n👤 **From:** {sender}\n📌 **Subject:** {subject}\n📝 **Snippet:** {body_snippet}...\n\n"

    await update.message.reply_text(response_text, parse_mode="Markdown")

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
    application.add_handler(CommandHandler("checkmail", checkmail_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot polling start ho raha hai...")
    application.run_polling()

if __name__ == "__main__":
    main()
                             
