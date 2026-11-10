import os
import time
import asyncio
import threading
import random
import requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from playwright.async_api import async_playwright
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

async def create_ptc_account_playwright(username, password, email):
    """Automates PTC form filling using Playwright browser"""
    async with async_playwright() as p:
        # Launch browser in headless mode for server environment
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # Navigate to PTC signup page
            await page.goto(PTC_SIGNUP_URL, timeout=60000)
            await page.wait_for_load_state("networkidle")

            # Fill form fields (Selectors based on PTC standard signup form)
            # Note: Selectors might need minor adjustments based on PTC's exact HTML IDs
            await page.fill("input[name='username']", username)
            await page.fill("input[name='password']", password)
            await page.fill("input[name='confirm_password']", password)
            await page.fill("input[name='email']", email)
            await page.fill("input[name='confirm_email']", email)
            
            # Select Birth Date (Example: Year, Month, Day selectors)
            # PTC uses dropdowns or inputs for DOB, let's select birth year if available
            try:
                await page.select_option("select[name='birth_year']", "1995")
                await page.select_option("select[name='birth_month']", "6")
                await page.select_option("select[name='birth_day']", "15")
            except:
                pass

            # Check terms and conditions checkbox if present
            try:
                await page.check("input[name='terms']")
            except:
                pass

            # Take screenshot of the filled form for proof/debugging
            screenshot_path = f"{username}.png"
            await page.screenshot(path=screenshot_path, full_page=True)

            # Check if Cloudflare or Captcha is blocking
            page_content = await page.content()
            if "captcha" in page_content.lower() or "cloudflare" in page_content.lower():
                await browser.close()
                return False, screenshot_path, "Account not created, please try again (Blocked by Captcha/Cloudflare)."

            # Attempt to click submit button
            try:
                await page.click("button[type='submit'], input[type='submit']")
                await page.wait_for_timeout(5000)
                # Take post-submit screenshot
                await page.screenshot(path=screenshot_path, full_page=True)
            except Exception as sub_err:
                print(f"Submit click note: {sub_err}")

            await browser.close()
            return True, screenshot_path, "Form filled and submitted via Playwright!"

        except Exception as e:
            try:
                await browser.close()
            except:
                pass
            return False, None, f"Account not created, please try again."

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

    # 2. PTC Account Auto-Creation Handler (Playwright)
    if user_id in waiting_for_ptc_pass:
        waiting_for_ptc_pass.remove(user_id)
        custom_password = text
        
        await update.message.reply_text("⏳ Browser automation started, filling PTC form...")

        username = generate_random_username()
        domains = ["smailpro.com", "tmail.ws", "tempmail.ninja"]
        email = f"{username.lower()}@{random.choice(domains)}"
        
        # Run Playwright async function
        success, img_path, status_msg = await create_ptc_account_playwright(username, custom_password, email)

        if success:
            details = (
                f"🎮 **Pokémon Trainer Club (PTC) Form Processed!**\n\n"
                f"👤 **Username:** `{username}`\n"
                f"🔑 **Password:** `{custom_password}`\n"
                f"📧 **Email:** `{email}`\n"
                f"⚡ **Status:** `{status_msg}`\n\n"
                f"🌐 **Inbox Check:** Use `https://smailpro.com/` to verify."
            )
            
            # Send screenshot and log to admin/user
            try:
                if img_path and os.path.exists(img_path):
                    with open(img_path, 'rb') as photo:
                        await update.message.reply_photo(photo=photo, caption=details, parse_mode="Markdown")
                    os.remove(img_path)
                else:
                    await update.message.reply_text(details, parse_mode="Markdown")
            except Exception as ex:
                await update.message.reply_text(details, parse_mode="Markdown")
        else:
            details = (
                f"❌ **Account not created, please try again.**\n\n"
                f"👤 **Username Attempted:** `{username}`\n"
                f"⚠️ **Reason:** `{status_msg}`"
            )
            try:
                if img_path and os.path.exists(img_path):
                    with open(img_path, 'rb') as photo:
                        await update.message.reply_photo(photo=photo, caption=details, parse_mode="Markdown")
                    os.remove(img_path)
                else:
                    await update.message.reply_text(details, parse_mode="Markdown")
            except:
                await update.message.reply_text(details, parse_mode="Markdown")

        keyboard = [
            [InlineKeyboardButton("🔄 Phir se Try Karein", callback_data="menu_gen_ptc")],
            [InlineKeyboardButton("« Main Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Neeche diye gaye option ko chunein:", reply_markup=reply_markup)
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
            "🎛 **Main Menu (PTC Auto-Creator Bot)**\nNeeche diye gaye option se account banana shuru karein:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "🎛 **Main Menu (PTC Auto-Creator Bot)**\nNeeche diye gaye option se account banana shuru karein:",
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
