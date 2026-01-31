import os
import tempfile
import logging
import requests
import telebot
import re
import time
from pathlib import Path
from flask import Flask
from threading import Thread

# ===================== CONFIGURATION =====================
BOT_TOKEN = "8439511623:AAEEynrraSmPUlZZQ1RIurKtcYn_7IxAllI"  # Replace with your bot token
BASE_URL = "https://selectionway.examsaathi.site"
# =========================================================

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Initialize Flask app for Render
app = Flask(__name__)

# User state management
user_states = {}
user_batch_data = {}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===================== API FUNCTIONS =====================
def fetch_all_batches():
    """Fetch all available batches from Selection Way API"""
    try:
        response = requests.get(f"{BASE_URL}/allbatch", timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return {"success": True, "data": data.get("data", [])}
        return {"success": False, "error": "Failed to fetch batches"}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timeout"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Connection error"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def fetch_pdfs(batch_id):
    """Fetch PDFs for a specific batch"""
    try:
        response = requests.get(f"{BASE_URL}/pdf/{batch_id}", timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return {"success": True, "data": data.get("topics", [])}
        return {"success": False, "error": "No PDFs found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def fetch_videos(batch_id):
    """Fetch videos for a specific batch"""
    try:
        response = requests.get(f"{BASE_URL}/chapter/{batch_id}", timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return {"success": True, "data": data.get("classes", [])}
        return {"success": False, "error": "No videos found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ===================== HELPER FUNCTIONS =====================
def create_batch_list_message(batches):
    """Create formatted message with batch list"""
    if not batches:
        return "❌ No batches available at the moment."
    
    message_lines = [
        "📚 <b>Available Batches:</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        ""
    ]
    
    for idx, batch in enumerate(batches, 1):
        title = batch.get("title", "Untitled Batch")
        batch_id = batch.get("id", "")
        
        # Format batch entry
        batch_entry = f"<b>{idx}. {title}</b>\n"
        batch_entry += f"   🆔 <code>{batch_id}</code>\n"
        batch_entry += "   ──────────────────────"
        
        message_lines.append(batch_entry)
    
    message_lines.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "📋 <b>Instructions:</b>",
        "1. Copy the Batch ID above",
        "2. Paste and send it here",
        "3. Bot will create TXT file",
        "",
        "💡 <b>Tip:</b> Click on ID to copy easily!",
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    ])
    
    return "\n".join(message_lines)

def extract_topic_name(topic_data):
    """Extract topic name from different possible keys"""
    possible_keys = ["topicName", "name", "title", "subject"]
    for key in possible_keys:
        if key in topic_data:
            return topic_data[key]
    return "General"

def clean_filename(filename):
    """Clean filename for safe saving"""
    # Remove invalid characters
    cleaned = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # Trim to reasonable length
    if len(cleaned) > 100:
        cleaned = cleaned[:100]
    return cleaned.strip()

def generate_txt_content(batch_title, batch_id, pdfs_data, videos_data):
    """Generate TXT file content from batch data"""
    content_lines = []
    
    # Counters
    pdf_count = 0
    video_count = 0
    
    # Add header
    content_lines.append("=" * 60)
    content_lines.append(f"BATCH: {batch_title}")
    content_lines.append(f"ID: {batch_id}")
    content_lines.append("=" * 60)
    content_lines.append("")
    
    # Process PDFs
    if pdfs_data.get("success") and pdfs_data.get("data"):
        content_lines.append("[PDF DOCUMENTS]")
        content_lines.append("-" * 40)
        
        for topic in pdfs_data["data"]:
            topic_name = extract_topic_name(topic)
            pdfs = topic.get("pdfs", [])
            
            for pdf in pdfs:
                pdf_title = pdf.get("title", "Untitled PDF")
                pdf_url = pdf.get("uploadPdf", "")
                
                if pdf_url and pdf_url.startswith("http"):
                    content_lines.append(f"[{topic_name}] {pdf_title} : {pdf_url}")
                    pdf_count += 1
        
        content_lines.append("")
    
    # Process Videos
    if videos_data.get("success") and videos_data.get("data"):
        content_lines.append("[VIDEO CLASSES]")
        content_lines.append("-" * 40)
        
        for chapter in videos_data["data"]:
            topic_name = extract_topic_name(chapter)
            classes = chapter.get("classes", [])
            
            for video in classes:
                video_title = video.get("title", "Untitled Video")
                video_url = video.get("class_link", "")
                
                if video_url and video_url.startswith("http"):
                    content_lines.append(f"[{topic_name}] {video_title} : {video_url}")
                    video_count += 1
        
        content_lines.append("")
    
    # Add summary
    content_lines.append("=" * 60)
    content_lines.append("SUMMARY:")
    content_lines.append(f"Total PDFs: {pdf_count}")
    content_lines.append(f"Total Videos: {video_count}")
    content_lines.append(f"Total Links: {pdf_count + video_count}")
    content_lines.append("=" * 60)
    content_lines.append("Generated by Selection Way Bot")
    content_lines.append(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return "\n".join(content_lines), pdf_count, video_count

# ===================== BOT HANDLERS =====================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Handle /start command"""
    chat_id = message.chat.id
    
    welcome_message = """
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
    
    bot.send_message(chat_id, welcome_message)
    
    # Automatically fetch and show batches
    send_batch_list(message)

@bot.message_handler(commands=['batches'])
def send_batch_list(message):
    """Show all available batches"""
    chat_id = message.chat.id
    
    # Send loading message
    msg = bot.send_message(chat_id, "⏳ Fetching available batches...")
    
    # Fetch batches
    result = fetch_all_batches()
    
    if result["success"]:
        batches = result["data"]
        if batches:
            # Store batch data for this user
            user_batch_data[chat_id] = batches
            
            # Create and send batch list
            batch_message = create_batch_list_message(batches)
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg.message_id,
                text=batch_message
            )
            
            # Set user state to wait for batch ID
            user_states[chat_id] = "awaiting_batch_id"
        else:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg.message_id,
                text="❌ No batches available at the moment. Please try again later."
            )
    else:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg.message_id,
            text=f"❌ Error: {result.get('error', 'Failed to fetch batches')}"
        )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "awaiting_batch_id")
def handle_batch_id(message):
    """Handle batch ID input from user"""
    chat_id = message.chat.id
    batch_id = message.text.strip()
    
    # Check if we have batch data for this user
    if chat_id not in user_batch_data:
        bot.send_message(chat_id, "❌ Please use /batches first to see available batches.")
        return
    
    # Find the batch
    batches = user_batch_data[chat_id]
    selected_batch = None
    batch_title = ""
    
    for batch in batches:
        if batch.get("id") == batch_id:
            selected_batch = batch
            batch_title = batch.get("title", "Unknown Batch")
            break
    
    if not selected_batch:
        bot.reply_to(message, 
                     f"❌ Invalid Batch ID: <code>{batch_id}</code>\n"
                     f"Please copy the exact ID from the list above.",
                     parse_mode="HTML")
        return
    
    # Start processing
    processing_msg = bot.send_message(
        chat_id,
        f"⏳ Processing batch: <b>{batch_title}</b>\n"
        f"📁 Fetching PDFs and videos...\n"
        f"🆔 ID: <code>{batch_id}</code>",
        parse_mode="HTML"
    )
    
    # Fetch data in parallel (simulated with threads)
    pdfs_data = fetch_pdfs(batch_id)
    videos_data = fetch_videos(batch_id)
    
    # Check if we have any data
    has_pdfs = pdfs_data.get("success") and pdfs_data.get("data")
    has_videos = videos_data.get("success") and videos_data.get("data")
    
    if not has_pdfs and not has_videos:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=processing_msg.message_id,
            text=f"❌ No content found for batch: <b>{batch_title}</b>\n"
                 f"The batch might be empty or not accessible.",
            parse_mode="HTML"
        )
        user_states.pop(chat_id, None)
        return
    
    # Update processing message
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=processing_msg.message_id,
        text=f"✅ Data fetched successfully!\n"
             f"📦 Preparing TXT file for: <b>{batch_title}</b>",
        parse_mode="HTML"
    )
    
    # Generate TXT content
    txt_content, pdf_count, video_count = generate_txt_content(
        batch_title, batch_id, pdfs_data, videos_data
    )
    
    # Check if content is valid
    if len(txt_content.strip()) < 100:  # Minimum content check
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=processing_msg.message_id,
            text=f"❌ Insufficient content in batch: <b>{batch_title}</b>\n"
                 f"PDFs: {pdf_count}, Videos: {video_count}",
            parse_mode="HTML"
        )
        user_states.pop(chat_id, None)
        return
    
    # Create temporary file
    try:
        # Clean filename
        safe_title = clean_filename(batch_title)
        filename = f"SelectionWay_{safe_title}_{int(time.time())}.txt"
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', 
                                         suffix='.txt', delete=False) as f:
            f.write(txt_content)
            temp_file_path = f.name
        
        # Send file
        with open(temp_file_path, 'rb') as file:
            caption = (
                f"✅ <b>Batch Export Complete!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📚 <b>Batch:</b> {batch_title}\n"
                f"🆔 <b>ID:</b> <code>{batch_id}</code>\n"
                f"📄 <b>PDFs:</b> {pdf_count}\n"
                f"🎬 <b>Videos:</b> {video_count}\n"
                f"🔗 <b>Total Links:</b> {pdf_count + video_count}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 File will auto-delete from server"
            )
            
            bot.send_document(
                chat_id,
                file,
                caption=caption,
                parse_mode="HTML",
                visible_file_name=filename
            )
        
        # Clean up
        os.unlink(temp_file_path)
        
        # Send completion message
        completion_msg = (
            f"🎉 <b>File sent successfully!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"The TXT file contains all PDF and video links.\n"
            f"\n"
            f"To download another batch:\n"
            f"1. Use /batches command\n"
            f"2. Copy new Batch ID\n"
            f"3. Send it here\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        bot.send_message(chat_id, completion_msg, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error creating file: {e}")
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=processing_msg.message_id,
            text=f"❌ Error creating file: {str(e)[:100]}"
        )
    
    finally:
        # Cleanup user state
        user_states.pop(chat_id, None)
        user_batch_data.pop(chat_id, None)

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    """Handle all other messages"""
    chat_id = message.chat.id
    
    # If not waiting for batch ID, show help
    if user_states.get(chat_id) != "awaiting_batch_id":
        help_text = (
            "🤖 <b>Selection Way Bot</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "I help you download batch materials.\n"
            "\n"
            "<b>Available Commands:</b>\n"
            "/start - Start the bot\n"
            "/batches - Show all batches\n"
            "/help - Show help\n"
            "\n"
            "To download a batch:\n"
            "1. Use /batches command\n"
            "2. Copy Batch ID\n"
            "3. Send Batch ID here\n"
            "4. Receive TXT file\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        bot.send_message(chat_id, help_text, parse_mode="HTML")

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
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .container {
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                padding: 30px;
                margin-top: 50px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            }
            h1 {
                color: #fff;
                text-align: center;
                margin-bottom: 30px;
            }
            .status {
                background: rgba(76, 175, 80, 0.2);
                border: 1px solid #4CAF50;
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
                text-align: center;
            }
            .instructions {
                background: rgba(33, 150, 243, 0.2);
                border: 1px solid #2196F3;
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
            }
            .bot-link {
                display: block;
                text-align: center;
                background: #0088cc;
                color: white;
                padding: 15px;
                border-radius: 10px;
                text-decoration: none;
                font-weight: bold;
                margin-top: 20px;
                transition: background 0.3s;
            }
            .bot-link:hover {
                background: #006699;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Selection Way Telegram Bot</h1>
            
            <div class="status">
                <h2>✅ Bot Status: RUNNING</h2>
                <p>Server time: <span id="time"></span></p>
            </div>
            
            <div class="instructions">
                <h3>📋 How to use:</h3>
                <ol>
                    <li>Start the bot on Telegram</li>
                    <li>Use /batches command</li>
                    <li>Copy Batch ID</li>
                    <li>Send Batch ID to bot</li>
                    <li>Receive TXT file with all links</li>
                </ol>
            </div>
            
            <a href="https://t.me/your_bot_username" class="bot-link" target="_blank">
                🔗 Start Using the Bot
            </a>
            
            <div style="text-align: center; margin-top: 30px; font-size: 12px; opacity: 0.7;">
                <p>Powered by Render • Selection Way API</p>
            </div>
        </div>
        
        <script>
            function updateTime() {
                const now = new Date();
                document.getElementById('time').textContent = 
                    now.toLocaleString('en-US', { 
                        timeZone: 'Asia/Kolkata',
                        dateStyle: 'full',
                        timeStyle: 'long'
                    });
            }
            updateTime();
            setInterval(updateTime, 1000);
        </script>
    </body>
    </html>
    """

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    return {"status": "healthy", "service": "selection-way-bot", "timestamp": time.time()}

# ===================== BOT POLLING =====================
def start_bot_polling():
    """Start the bot polling in a separate thread"""
    logger.info("Starting Telegram bot polling...")
    
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
            logger.info("Restarting bot in 10 seconds...")
            time.sleep(10)

# ===================== MAIN =====================
if __name__ == "__main__":
    logger.info("Initializing Selection Way Bot...")
    
    # Check if bot token is set
    if not BOT_TOKEN or BOT_TOKEN == "8308791539:AAH8S1LvRK_LY27-ylWdsixvECHiBAf-sCU":
        logger.warning("Please set your actual BOT_TOKEN!")
    
    # Start bot in background thread
    bot_thread = Thread(target=start_bot_polling, daemon=True)
    bot_thread.start()
    
    # Start Flask app
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port)
