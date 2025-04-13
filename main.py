import telebot
import sqlite3
import os
from flask import Flask
from threading import Thread
from groq import GroqClient
from datetime import datetime, timedelta

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MIR_CARD = os.getenv("MIR_CARD")
CRYPTO_ADDRESS = os.getenv("CRYPTO_ADDRESS")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# === Flask server ===
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
    expires_at TEXT
)
""")
conn.commit()

# === Pricing ===
PRICING = {
    "one-time": (5, 1),
    "weekly": (25, 7),
    "monthly": (65, 30),
    "yearly": (390, 365)
}

# === Start ===
@bot.message_handler(commands=['start'])
def start(msg):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Analyze Match", "💳 Donate & Get Access", "📊 Subscription Status")
    bot.send_message(msg.chat.id,
        "<b>🤖 AI Match Predictor</b>\n\n"
        "Predict football matches using AI.\n\n"
        "<b>Pricing:</b>\n"
        "• One-time — $5\n"
        "• Weekly — $25\n"
        "• Monthly — $65\n"
        "• Yearly — $390",
        parse_mode="HTML", reply_markup=markup)

# === Subscription Status ===
@bot.message_handler(func=lambda msg: msg.text == "📊 Subscription Status")
def sub_status(msg):
    cursor.execute("SELECT expires_at FROM users WHERE user_id=?", (msg.chat.id,))
    row = cursor.fetchone()
    if row:
        until = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        days_left = (until - datetime.utcnow()).days
        if days_left > 0:
            bot.send_message(msg.chat.id, f"✅ Subscription active.\nExpires in {days_left} day(s).")
        else:
            bot.send_message(msg.chat.id, "❌ Subscription expired.")
    else:
        bot.send_message(msg.chat.id, "❌ No subscription found.")

# === Donate Info ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def donate(msg):
    markup = telebot.types.InlineKeyboardMarkup()
    for plan, (price, days) in PRICING.items():
        markup.add(telebot.types.InlineKeyboardButton(f"{plan.capitalize()} — ${price}", callback_data=f"pay_{plan}"))
    bot.send_message(msg.chat.id,
        f"Send payment to:\n\n"
        f"💳 MIR: <code>{MIR_CARD}</code>\n"
        f"🪙 USDT TRC20: <code>{CRYPTO_ADDRESS}</code>\n\n"
        f"Then press a plan below:",
        parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def pay_selected(call):
    plan = call.data.split("_")[1]
    price, days = PRICING[plan]
    uid = call.from_user.id
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ Grant Access", callback_data=f"grant_{uid}_{days}"))
    markup.add(telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}"))
    bot.send_message(uid, "Your request has been sent. Wait for approval.")
    bot.send_message(ADMIN_ID,
        f"🧾 {call.from_user.first_name} (@{call.from_user.username or 'NoUsername'})\n"
        f"wants to buy: {plan} (${price})\nUser ID: <code>{uid}</code>",
        parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("grant_") or c.data.startswith("reject_"))
def approve(c):
    if c.from_user.id != ADMIN_ID: return
    if c.data.startswith("grant_"):
        _, uid, days = c.data.split("_")
        uid = int(uid)
        days = int(days)
        expires = datetime.utcnow() + timedelta(days=days)
        cursor.execute("REPLACE INTO users (user_id, expires_at) VALUES (?, ?)", (uid, expires.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        bot.send_message(uid, "✅ Access granted!")
        bot.send_message(c.message.chat.id, "User approved.")
    else:
        uid = int(c.data.split("_")[1])
        bot.send_message(uid, "❌ Access denied.")
        bot.send_message(c.message.chat.id, "User rejected.")

# === Analyze Match ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def ask_match(msg):
    if not has_access(msg.chat.id):
        bot.send_message(msg.chat.id, "❌ Access denied. Subscribe first.")
        return
    bot.send_message(msg.chat.id, "Send match info:")

# === Match Prediction ===
@bot.message_handler(func=lambda msg: True)
def analyze_match(msg):
    if not has_access(msg.chat.id): return
    try:
        prompt = f"""
Ты — футбольный аналитик. Ответь кратко на русском, строго в этом формате:

Матч: [название команд]
Прогноз:
• Исход: [победа одной из команд или ничья]
• Тотал матча: [Б/М и число]
• Тотал 1 или 2 тайма: [Б/М и число]
• Тотал одной из команд: [Б/М и число]

Контекст: {msg.text}
"""
        res = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        text = res.choices[0].message.content
        for chunk in range(0, len(text), 4000):
            bot.send_message(msg.chat.id, text[chunk:chunk+4000])
    except Exception as e:
        bot.send_message(msg.chat.id, f"Error: {e}")

# === Access Checker ===
def has_access(uid):
    cursor.execute("SELECT expires_at FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if not row: return False
    try:
        return datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S") > datetime.utcnow()
    except:
        return False

bot.polling()
