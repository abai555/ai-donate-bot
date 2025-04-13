import telebot
import sqlite3
import os
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta
from groq import GroqClient

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MIR_CARD = os.getenv("MIR_CARD")
CRYPTO_ADDRESS = os.getenv("CRYPTO_ADDRESS")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = GroqClient(api_key=GROQ_API_KEY)

# === Flask for Uptime ===
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"
Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# === DB ===
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    until TIMESTAMP
)
""")
conn.commit()

# === Start ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Analyze Match", "💳 Donate & Get Access", "📊 Subscription Status")
    bot.send_message(message.chat.id, 
        "🤖 <b>AI Match Predictor</b>\n\n"
        "Get predictions for football matches using AI.\n\n"
        "<b>Prices:</b>\n"
        "• One-time — $5\n"
        "• Weekly — $25\n"
        "• Monthly — $65\n"
        "• Yearly — $390", 
        parse_mode="HTML", reply_markup=markup)

# === Donate Info ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def donate(msg):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(msg.chat.id,
        f"Send payment to:\n\n"
        f"💳 MIR Card: <code>{MIR_CARD}</code>\n"
        f"🪙 Crypto (TRC20): <code>{CRYPTO_ADDRESS}</code>\n\n"
        f"Then click the button below to confirm.",
        parse_mode="HTML", reply_markup=markup)

# === Paid Confirmation ===
@bot.callback_query_handler(func=lambda c: c.data == "paid")
def confirm_payment(c):
    uid = c.message.chat.id
    bot.send_message(ADMIN_ID, 
        f"🧾 Payment from @{c.from_user.username or 'user'} ({uid})",
        reply_markup=telebot.types.InlineKeyboardMarkup([
            [telebot.types.InlineKeyboardButton("✅ Grant 1 day", callback_data=f"grant_{uid}_1"),
             telebot.types.InlineKeyboardButton("✅ Grant 7 days", callback_data=f"grant_{uid}_7")],
            [telebot.types.InlineKeyboardButton("✅ Grant 30 days", callback_data=f"grant_{uid}_30"),
             telebot.types.InlineKeyboardButton("✅ Grant 365 days", callback_data=f"grant_{uid}_365")],
            [telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]
        ])
    )
    bot.send_message(uid, "Your request has been sent. Please wait for confirmation.")

# === Admin Response ===
@bot.callback_query_handler(func=lambda c: c.data.startswith("grant_") or c.data.startswith("reject_"))
def admin_response(c):
    if c.from_user.id != ADMIN_ID: return
    if c.data.startswith("reject_"):
        uid = int(c.data.split("_")[1])
        bot.send_message(uid, "❌ Access denied.")
        bot.send_message(c.message.chat.id, "User rejected.")
    else:
        uid, days = int(c.data.split("_")[1]), int(c.data.split("_")[2])
        until = datetime.now() + timedelta(days=days)
        cursor.execute("INSERT OR REPLACE INTO users (user_id, until) VALUES (?, ?)", (uid, until))
        conn.commit()
        bot.send_message(uid, f"✅ Access granted for {days} day(s).")
        bot.send_message(c.message.chat.id, f"Access granted until {until.date()}.")

# === Check Subscription ===
@bot.message_handler(func=lambda m: m.text == "📊 Subscription Status")
def status(m):
    uid = m.chat.id
    cursor.execute("SELECT until FROM users WHERE user_id = ?", (uid,))
    result = cursor.fetchone()
    if result:
        expires = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S.%f")
        if expires > datetime.now():
            left = (expires - datetime.now()).days
            bot.send_message(uid, f"✅ Subscription active.\nExpires in {left} day(s).")
            return
    bot.send_message(uid, "❌ No active subscription.")

# === Analyze Match ===
@bot.message_handler(func=lambda m: m.text == "🔍 Analyze Match")
def ask_match(m):
    cursor.execute("SELECT until FROM users WHERE user_id = ?", (m.chat.id,))
    result = cursor.fetchone()
    if not result or datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S.%f") < datetime.now():
        bot.send_message(m.chat.id, "❌ No access. Please subscribe first.")
        return
    bot.send_message(m.chat.id, "Send match info like:\nReal Madrid vs Arsenal, UCL, 1st leg ended 0:3")

# === AI Analysis ===
@bot.message_handler(func=lambda m: True)
def handle_analysis(m):
    cursor.execute("SELECT until FROM users WHERE user_id = ?", (m.chat.id,))
    result = cursor.fetchone()
    if not result or datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S.%f") < datetime.now():
        return
    bot.send_message(m.chat.id, "⚡ Generating prediction...")
    try:
        prompt = f"""
Ты — аналитик матчей. Ответь кратко по следующему шаблону:

—

Прогноз:
• Победа одной из команд или ничья
• Общий тотал матча
• Тотал 1-го или 2-го тайма
• Тотал одной из команд

Контекст: {m.text}
"""
        chat = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": prompt}]
        )
        bot.send_message(m.chat.id, chat.choices[0].message.content)
    except Exception as e:
        bot.send_message(m.chat.id, f"Error: {e}")

bot.polling()
