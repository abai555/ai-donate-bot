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

# === Flask for Railway ===
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

# === Start ===
@bot.message_handler(commands=["start"])
def start(msg):
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🔍 Analyze Match", "💳 Donate & Get Access", "📊 Subscription Status")
    bot.send_message(msg.chat.id,
        "<b>🤖 AI Match Analyzer</b>\n\n"
        "Analyze football matches with AI predictions.\n\n"
        "<b>Payment Plans:</b>\n"
        "• One-time (1 day): $5\n"
        "• Weekly: $25\n"
        "• Monthly: $65\n"
        "• Yearly: $390",
        parse_mode="HTML",
        reply_markup=kb
    )

# === Donate ===
@bot.message_handler(func=lambda m: m.text == "💳 Donate & Get Access")
def donate(msg):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(msg.chat.id,
        f"<b>Send payment to:</b>\n\n"
        f"<b>💳 MIR Card:</b> <code>{MIR_CARD}</code>\n"
        f"<b>🪙 USDT TRC20:</b> <code>{CRYPTO_ADDRESS}</code>\n\n"
        "Then press the button below.",
        parse_mode="HTML",
        reply_markup=kb
    )

# === Confirm Payment ===
@bot.callback_query_handler(func=lambda c: c.data == "paid")
def confirm_payment(call):
    uid = call.message.chat.id
    bot.send_message(uid, "Request sent. Wait for manual approval.")
    bot.send_message(ADMIN_ID,
        f"💰 Payment request from @{call.from_user.username or 'NoUsername'} ({uid})",
        reply_markup=telebot.types.InlineKeyboardMarkup([
            [telebot.types.InlineKeyboardButton("1 Day", callback_data=f"grant_1_{uid}"),
             telebot.types.InlineKeyboardButton("7 Days", callback_data=f"grant_7_{uid}")],
            [telebot.types.InlineKeyboardButton("30 Days", callback_data=f"grant_30_{uid}"),
             telebot.types.InlineKeyboardButton("365 Days", callback_data=f"grant_365_{uid}")],
            [telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]
        ])
    )

# === Grant Access ===
@bot.callback_query_handler(func=lambda c: c.data.startswith("grant_") or c.data.startswith("reject_"))
def grant_access(call):
    parts = call.data.split("_")
    if call.from_user.id != ADMIN_ID:
        return
    uid = int(parts[-1])
    if call.data.startswith("grant_"):
        days = int(parts[1])
        expiry = datetime.now() + timedelta(days=days)
        cursor.execute("REPLACE INTO users (user_id, expires_at) VALUES (?, ?)", (uid, expiry.isoformat()))
        conn.commit()
        bot.send_message(uid, f"✅ Access granted for {days} day(s)!")
        bot.send_message(call.message.chat.id, "User approved.")
    else:
        bot.send_message(uid, "❌ Access denied.")
        bot.send_message(call.message.chat.id, "User rejected.")

# === Subscription Status ===
@bot.message_handler(func=lambda m: m.text == "📊 Subscription Status")
def status(msg):
    cursor.execute("SELECT expires_at FROM users WHERE user_id = ?", (msg.chat.id,))
    row = cursor.fetchone()
    if row:
        exp = datetime.fromisoformat(row[0])
        left = (exp - datetime.now()).days
        if left > 0:
            bot.send_message(msg.chat.id, f"✅ Subscription active.\nExpires in {left} day(s).")
            return
    bot.send_message(msg.chat.id, "❌ No active subscription.")

# === Analyze Match ===
@bot.message_handler(func=lambda m: m.text == "🔍 Analyze Match")
def get_match(msg):
    cursor.execute("SELECT expires_at FROM users WHERE user_id = ?", (msg.chat.id,))
    row = cursor.fetchone()
    if row and datetime.fromisoformat(row[0]) > datetime.now():
        bot.send_message(msg.chat.id, "Send match details (e.g. Real Madrid vs Arsenal, 0:3 first leg)...")
    else:
        bot.send_message(msg.chat.id, "❌ Access denied. Use 💳 Donate & Get Access.")

# === AI Prediction ===
@bot.message_handler(func=lambda m: True)
def analyze(msg):
    cursor.execute("SELECT expires_at FROM users WHERE user_id = ?", (msg.chat.id,))
    row = cursor.fetchone()
    if not row or datetime.fromisoformat(row[0]) < datetime.now():
        return
    bot.send_message(msg.chat.id, "⚡ Analyzing...")
    prompt = f"""
Ты футбольный аналитик. Ответь в следующем формате:

Матч: [Название турнира] — [Команды]
Первая игра закончилась 0:3 в пользу Арсенала.
Матч пройдет на [стадионе и в городе]

Прогноз:
• Основная ставка: [Победа Реала / Ничья / Победа Арсенала]
• Уверенность: [Низкая / Средняя / Высокая]
• Дополнительная Ставка: [Общий тотал / Тотал первого тайма / Тотал команды]

Анализируй: {msg.text}
"""
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response.choices[0].message.content
        bot.send_message(msg.chat.id, answer)
    except Exception as e:
        bot.send_message(msg.chat.id, f"Error: {e}")

bot.polling()
