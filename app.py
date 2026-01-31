import os
import requests
import telebot
from flask import Flask
import threading

# Configuration
BOT_TOKEN = "8439511623:A4EEynrraSmPULZZQ1RIurKtcYn_7IxALLI"
BASE_URL = "https://selectionway.examsaathi.site"

# Initialize
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "🤖 *Selection Way Bot Started!*\nUse /batches", parse_mode="Markdown")

@bot.message_handler(commands=['batches'])
def batches(message):
    try:
        response = requests.get(f"{BASE_URL}/allbatch", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                batches = data.get("data", [])
                
                msg = "📚 *Batches:*\n\n"
                for batch in batches[:10]:  # First 10 only
                    title = batch.get("title", "Untitled")
                    batch_id = batch.get("id", "")
                    msg += f"*{title}*\n`{batch_id}`\n\n"
                
                msg += "Send any ID above to get TXT file"
                bot.reply_to(message, msg, parse_mode="Markdown")
            else:
                bot.reply_to(message, "❌ Failed to get batches")
        else:
            bot.reply_to(message, f"❌ API Error: {response.status_code}")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(func=lambda m: True)
def handle_id(message):
    bot.reply_to(message, "Processing...")

@app.route('/')
def home():
    return "Bot is running!"

def run_bot():
    print("Starting bot...")
    bot.polling()

if __name__ == '__main__':
    # Start bot in thread
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    
    # Start Flask
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
