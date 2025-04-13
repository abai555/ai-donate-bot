import telebot
import sqlite3
from flask import Flask
from threading import Thread
from groq import Groq
import os
from datetime import datetime, timedelta

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MIR_CARD = os.getenv("MIR_CARD")
CRYPTO_ADDRESS = os.getenv("CRYPTO_ADDRESS")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# === Flask App for Railway Uptime ===
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"
Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# === Database ===
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    access_until TEXT
)
""")
conn.commit()

# === /start ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Analyze Match", "💳 Donate & Get Access", "📊 Subscription Status")
    bot.send_message(message.chat.id,
        "🤖 AI Match Predictor\n\n"
        "Get AI-based predictions for football matches.\n\n"
        "💸 Access Plans:\n"
        "• One-time: $5\n"
        "• Weekly: $25\n"
        "• Monthly: $65\n"
        "• Yearly: $390",
        reply_markup=markup
    )

# === Payment Info ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def donate_info(msg):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(msg.chat.id,
        f"Send payment to:\n\n"
        f"💳 MIR Card: <code>{MIR_CARD}</code>\n"
        f"🪙 USDT TRC20: <code>{CRYPTO_ADDRESS}</code>\n\n"
        "After payment, click the button below.",
        parse_mode="HTML",
        reply_markup=markup
    )

# === User clicked "I Paid" ===
@bot.callback_query_handler(func=lambda call: call.data == "paid")
def confirm_payment(call):
    uid = call.message.chat.id
    bot.send_message(uid, "Your payment request has been sent for manual review.")
    bot.send_message(ADMIN_ID,
        f"🧾 Payment request from @{call.from_user.username or 'NoUsername'} ({uid})",
        reply_markup=telebot.types.InlineKeyboardMarkup([
            [telebot.types.InlineKeyboardButton("✅ 1 Day", callback_data=f"grant_{uid}_1"),
             telebot.types.InlineKeyboardButton("🕓 7 Days", callback_data=f"grant_{uid}_7")],
            [telebot.types.InlineKeyboardButton("📅 30 Days", callback_data=f"grant_{uid}_30"),
             telebot.types.InlineKeyboardButton("📈 365 Days", callback_data=f"grant_{uid}_365")],
            [telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]
        ])
    )

# === Admin Approves Access ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("grant_") or call.data.startswith("reject_"))
def handle_admin_action(call):
    if call.from_user.id != ADMIN_ID:
        return
    data = call.data.split("_")
    uid = int(data[1])
    if data[0] == "reject":
        bot.send_message(uid, "❌ Access denied.")
        bot.send_message(call.message.chat.id, "User rejected.")
    else:
        days = int(data[2])
        expires = (datetime.utcnow() + timedelta(days=days)).isoformat()
        cursor.execute("INSERT OR REPLACE INTO users (user_id, access_until) VALUES (?, ?)", (uid, expires))
        conn.commit()
        bot.send_message(uid, f"✅ Access granted for {days} day(s).")
        bot.send_message(call.message.chat.id, f"Access granted for {days} day(s).")

# === Subscription Status ===
@bot.message_handler(func=lambda msg: msg.text == "📊 Subscription Status")
def check_subscription(msg):
    uid = msg.chat.id
    cursor.execute("SELECT access_until FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if row:
        until = datetime.fromisoformat(row[0])
        days_left = (until - datetime.utcnow()).days
        if days_left >= 0:
            bot.send_message(uid, f"✅ Subscription active.\nExpires in {days_left} day(s).")
            return
    bot.send_message(uid, "❌ No active subscription.")

# === Match Analysis Entry ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def match_entry(msg):
    cursor.execute("SELECT access_until FROM users WHERE user_id=?", (msg.chat.id,))
    row = cursor.fetchone()
    if row:
        until = datetime.fromisoformat(row[0])
        if until > datetime.utcnow():
            bot.send_message(msg.chat.id, "Send the match (e.g. Real Madrid vs Arsenal, context, etc):")
            return
    bot.send_message(msg.chat.id, "❌ Access denied. Use 💳 Donate & Get Access first.")

# === Match Analyzer ===
@bot.message_handler(func=lambda msg: True)
def analyze_match(msg):
    cursor.execute("SELECT access_until FROM users WHERE user_id=?", (msg.chat.id,))
    row = cursor.fetchone()
    if not row or datetime.fromisoformat(row[0]) < datetime.utcnow():
        return
    try:
        bot.send_message(msg.chat.id, "Analyzing...")
        prompt = f"""
Ты спортивный аналитик ИИ. На основе описания матча верни прогноз в кратком формате:

Match: [Название и турнир]
—
• Победа: [Одна из команд или ничья]
• Тотал матча: [Больше/меньше X]
• Тотал 1-го или 2-го тайма: [Больше/меньше X]
• Тотал одной из команд: [Больше/меньше X]

Матч: {msg.text}
"""
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content.strip()
        bot.send_message(msg.chat.id, result)
    except Exception as e:
        bot.send_message(msg.chat.id, f"Error: {e}")

bot.polling()
