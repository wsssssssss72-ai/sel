
import os
import requests
import telebot
import tempfile
import time
from flask import Flask
from threading import Thread

# ===================== CONFIG =====================
BOT_TOKEN = "8439511623:A4EEynrraSmPULZZQ1RIurKtcYn_7IxALLI"
BASE_URL = "https://selectionway.examsaathi.site"
# ==================================================

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Flask app
app = Flask(__name__)

# User states
user_data = {}

# ===================== API FUNCTIONS =====================
def get_all_batches():
    """Get all batches from API"""
    try:
        url = f"{BASE_URL}/allbatch"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return True, data.get("data", [])
        return False, []
    except:
        return False, []

def get_pdfs(batch_id):
    """Get PDFs for batch"""
    try:
        url = f"{BASE_URL}/pdf/{batch_id}"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return True, data.get("topics", [])
        return False, []
    except:
        return False, []

def get_videos(batch_id):
    """Get videos for batch"""
    try:
        url = f"{BASE_URL}/chapter/{batch_id}"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return True, data.get("classes", [])
        return False, []
    except:
        return False, []

# ===================== BOT HANDLERS =====================
@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    chat_id = message.chat.id
    
    welcome_msg = """
🎓 <b>Welcome to Selection Way Bot!</b>
━━━━━━━━━━━━━━━━━━━━━━━━
I can help you download batch materials in TXT format.

<b>How to use:</b>
1. Click /batches to see all available batches
2. Copy the Batch ID
3. Send the Batch ID to me
4. I'll create a TXT file with all links

<b>Available Commands:</b>
/batches - Show all batches
/help - Show this help message

📌 <b>Note:</b> All Batch IDs are copyable (click to copy)
━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    bot.send_message(chat_id, welcome_msg)
    # Auto show batches
    batches_command(message)

@bot.message_handler(commands=['batches'])
def batches_command(message):
    chat_id = message.chat.id
    
    # Show loading
    msg = bot.send_message(chat_id, "⏳ Fetching batches...")
    
    # Get batches
    success, batches = get_all_batches()
    
    if not success or not batches:
        bot.edit_message_text(
            "❌ Failed to fetch batches. Try again later.",
            chat_id, msg.message_id
        )
        return
    
    # Store batches for user
    user_data[chat_id] = {"batches": batches, "state": "waiting_id"}
    
    # Create message
    message_text = "📚 <b>Available Batches:</b>\n"
    message_text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, batch in enumerate(batches, 1):
        title = batch.get("title", "Untitled Batch")
        batch_id = batch.get("id", "N/A")
        
        message_text += f"<b>{i}. {title}</b>\n"
        message_text += f"   🆔 <code>{batch_id}</code>\n"
        message_text += "   ──────────────────────\n"
    
    message_text += "\n📋 <b>Instructions:</b>\n"
    message_text += "1. Copy any Batch ID above\n"
    message_text += "2. Paste and send it here\n"
    message_text += "3. Get TXT file with all links\n\n"
    message_text += "💡 <b>Tip:</b> Click on ID to copy!"
    
    bot.edit_message_text(
        message_text,
        chat_id,
        msg.message_id,
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get("state") == "waiting_id")
def handle_batch_input(message):
    chat_id = message.chat.id
    batch_id = message.text.strip()
    
    if chat_id not in user_data:
        bot.send_message(chat_id, "❌ Please use /batches first")
        return
    
    # Find batch
    batches = user_data[chat_id]["batches"]
    selected_batch = None
    batch_title = ""
    
    for batch in batches:
        if batch.get("id") == batch_id:
            selected_batch = batch
            batch_title = batch.get("title", "Unknown")
            break
    
    if not selected_batch:
        bot.reply_to(message, f"❌ Invalid Batch ID: <code>{batch_id}</code>", parse_mode="HTML")
        return
    
    # Start processing
    processing_msg = bot.send_message(
        chat_id,
        f"⏳ Processing: <b>{batch_title}</b>\n"
        f"🆔 ID: <code>{batch_id}</code>\n"
        f"📁 Fetching data...",
        parse_mode="HTML"
    )
    
    # Fetch data
    pdf_success, pdfs = get_pdfs(batch_id)
    video_success, videos = get_videos(batch_id)
    
    # Create TXT file
    txt_content = f"Selection Way Batch Export\n"
    txt_content += "=" * 50 + "\n"
    txt_content += f"Batch: {batch_title}\n"
    txt_content += f"ID: {batch_id}\n"
    txt_content += "=" * 50 + "\n\n"
    
    total_links = 0
    
    # Add PDFs
    if pdf_success and pdfs:
        txt_content += "[PDF DOCUMENTS]\n"
        txt_content += "-" * 40 + "\n"
        
        for topic in pdfs:
            topic_name = topic.get("topicName", "PDFs")
            pdf_list = topic.get("pdfs", [])
            
            for pdf in pdf_list:
                title = pdf.get("title", "Untitled")
                url = pdf.get("uploadPdf", "")
                
                if url:
                    txt_content += f"[{topic_name}] {title} : {url}\n"
                    total_links += 1
        
        txt_content += "\n"
    
    # Add Videos
    if video_success and videos:
        txt_content += "[VIDEO CLASSES]\n"
        txt_content += "-" * 40 + "\n"
        
        for chapter in videos:
            topic_name = chapter.get("topicName", "Videos")
            classes = chapter.get("classes", [])
            
            for video in classes:
                title = video.get("title", "Untitled")
                url = video.get("class_link", "")
                
                if url:
                    txt_content += f"[{topic_name}] {title} : {url}\n"
                    total_links += 1
        
        txt_content += "\n"
    
    # Add summary
    txt_content += "=" * 50 + "\n"
    txt_content += "EXPORT SUMMARY\n"
    txt_content += f"Total Links: {total_links}\n"
    txt_content += f"Generated: {time.ctime()}\n"
    txt_content += "Bot: @selection_way_free_txt_bot\n"
    txt_content += "=" * 50
    
    # Check if we have content
    if total_links == 0:
        bot.edit_message_text(
            f"❌ No content found for: <b>{batch_title}</b>",
            chat_id,
            processing_msg.message_id,
            parse_mode="HTML"
        )
        return
    
    # Update message
    bot.edit_message_text(
        f"✅ Data fetched!\n"
        f"🔗 Found {total_links} links\n"
        f"📦 Creating TXT file...",
        chat_id,
        processing_msg.message_id,
        parse_mode="HTML"
    )
    
    # Save to temp file
    try:
        import re
        safe_title = re.sub(r'[^\w\s-]', '', batch_title).strip().replace(' ', '_')
        filename = f"SelectionWay_{safe_title}.txt"
        
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.txt', delete=False) as f:
            f.write(txt_content)
            temp_path = f.name
        
        # Send file
        with open(temp_path, 'rb') as file:
            caption = (
                f"✅ <b>Batch Export Complete!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📚 <b>Batch:</b> {batch_title}\n"
                f"🆔 <b>ID:</b> <code>{batch_id}</code>\n"
                f"🔗 <b>Total Links:</b> {total_links}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 File auto-deletes from server"
            )
            
            bot.send_document(
                chat_id,
                file,
                caption=caption,
                parse_mode="HTML",
                visible_file_name=filename
            )
        
        # Cleanup
        import os
        os.unlink(temp_path)
        
        # Success message
        bot.send_message(
            chat_id,
            "🎉 <b>File sent successfully!</b>\n\n"
            "To download another batch:\n"
            "1. Use /batches command\n"
            "2. Copy new Batch ID\n"
            "3. Send it here\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML"
        )
        
    except Exception as e:
        bot.edit_message_text(
            f"❌ Error creating file:\n{str(e)[:100]}",
            chat_id,
            processing_msg.message_id
        )
    
    finally:
        # Clean user data
        if chat_id in user_data:
            del user_data[chat_id]

@bot.message_handler(func=lambda m: True)
def handle_other_messages(message):
    """Handle all other messages"""
    chat_id = message.chat.id
    
    # Check if message might be a batch ID
    text = message.text.strip()
    if len(text) == 24 and all(c in '0123456789abcdef' for c in text.lower()):
        # It looks like a batch ID
        user_data[chat_id] = {"state": "waiting_id", "batches": []}
        handle_batch_input(message)
    else:
        # Show help
        bot.send_message(
            chat_id,
            "🤖 <b>Selection Way Bot</b>\n\n"
            "I help you download batch materials.\n\n"
            "<b>Commands:</b>\n"
            "/start - Start the bot\n"
            "/batches - Show all batches\n"
            "/help - Show help\n\n"
            "Or send a Batch ID directly",
            parse_mode="HTML"
        )

# ===================== FLASK ROUTES =====================
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Selection Way Bot</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 50px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .container {
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                padding: 40px;
                max-width: 600px;
                margin: 0 auto;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            }
            h1 {
                color: #fff;
                margin-bottom: 20px;
            }
            .status {
                background: rgba(76, 175, 80, 0.2);
                border: 2px solid #4CAF50;
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
            }
            .bot-link {
                display: inline-block;
                background: #0088cc;
                color: white;
                padding: 15px 30px;
                border-radius: 10px;
                text-decoration: none;
                font-weight: bold;
                margin-top: 20px;
                transition: background 0.3s;
            }
            .bot-link:hover {
                background: #006699;
                transform: scale(1.05);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Selection Way Bot</h1>
            <div class="status">
                <h2>✅ Bot Status: RUNNING</h2>
                <p>Server time: <span id="time"></span></p>
            </div>
            <p>This bot helps you download Selection Way batch materials in TXT format.</p>
            <a href="https://t.me/selection_way_free_txt_bot" class="bot-link" target="_blank">
                🔗 Start Using the Bot
            </a>
            <div style="margin-top: 30px; font-size: 12px; opacity: 0.7;">
                <p>Powered by Render • Selection Way API</p>
            </div>
        </div>
        <script>
            function updateTime() {
                const now = new Date();
                document.getElementById('time').textContent = now.toLocaleString();
            }
            updateTime();
            setInterval(updateTime, 1000);
        </script>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return {"status": "healthy", "bot": "@selection_way_free_txt_bot", "time": time.time()}

# ===================== START BOT =====================
def run_bot():
    """Run the Telegram bot"""
    print("🤖 Starting Telegram Bot...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Bot error: {e}")
        import time as t
        t.sleep(10)
        run_bot()

# ===================== MAIN =====================
if __name__ == '__main__':
    print("🚀 Initializing Selection Way Bot...")
    print(f"📱 Bot: @selection_way_free_txt_bot")
    
    # Start bot in separate thread
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("✅ Bot thread started")
    
    # Start Flask app
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port)
