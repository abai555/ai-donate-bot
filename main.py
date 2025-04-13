import telebot
import sqlite3
from flask import Flask
from threading import Thread
from groq import Groq
import time

# === CONFIG ===
TELEGRAM_TOKEN = "7241781324:AAFOgQ8QgTiCOC1efBUoPeu7UzM7Yu2UXvo"
GROQ_API_KEY = "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"
ADMIN_ID = 1023932092  # Replace with your Telegram ID
MIR_CARD = "2200701901154812"
CRYPTO_ADDRESS = "TH92J3hUqbAgpXiC5NtkxFHGe2vB9yUonH"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# === Flask Uptime ===
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"
def run():
    app.run(host="0.0.0.0", port=8080)
Thread(target=run).start()

# === DB ===
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    access INTEGER DEFAULT 0,
    expiry INTEGER DEFAULT 0
)
""")
conn.commit()

# === START ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Analyze Match", "💳 Donate & Get Access", "📊 Subscription Status")
    bot.send_message(message.chat.id,
        "<b>🤖 AI Match Analyzer</b>\n\n"
        "Analyze football matches using AI predictions.\n\n"
        "<b>Pricing:</b>\n"
        "• One-time – $5 (1 day)\n"
        "• Weekly – $25 (7 days)\n"
        "• Monthly – $65 (30 days)\n"
        "• Yearly – $390 (365 days)",
        parse_mode="HTML",
        reply_markup=markup
    )

# === STATUS ===
@bot.message_handler(func=lambda msg: msg.text == "📊 Subscription Status")
def check_status(msg):
    cursor.execute("SELECT expiry FROM users WHERE user_id = ?", (msg.chat.id,))
    row = cursor.fetchone()
    now = int(time.time())
    if row and row[0] > now:
        remaining = row[0] - now
        days = remaining // 86400
        bot.send_message(msg.chat.id, f"✅ Subscription active.\nExpires in {days} day(s).")
    else:
        bot.send_message(msg.chat.id, "❌ You don't have an active subscription.")

# === Donate ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def donate_info(msg):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(msg.chat.id,
        f"Send payment to:\n\n"
        f"💳 MIR Card: <code>{MIR_CARD}</code>\n"
        f"🪙 USDT TRC20: <code>{CRYPTO_ADDRESS}</code>\n\n"
        "Then press the button below to request access.",
        parse_mode="HTML",
        reply_markup=markup
    )

# === I Paid pressed ===
@bot.callback_query_handler(func=lambda call: call.data == "paid")
def handle_paid(call):
    uid = call.message.chat.id
    bot.send_message(uid, "🕓 Payment request sent. Please wait for admin confirmation.")
    bot.send_message(ADMIN_ID,
        f"💰 New payment request:\nUser: @{call.from_user.username or 'no_username'}\nID: {uid}\n\nSelect access level:",
        reply_markup=telebot.types.InlineKeyboardMarkup([
            [telebot.types.InlineKeyboardButton("✅ One-time", callback_data=f"grant_{uid}_1")],
            [telebot.types.InlineKeyboardButton("✅ Weekly", callback_data=f"grant_{uid}_7")],
            [telebot.types.InlineKeyboardButton("✅ Monthly", callback_data=f"grant_{uid}_30")],
            [telebot.types.InlineKeyboardButton("✅ Yearly", callback_data=f"grant_{uid}_365")],
            [telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]
        ])
    )

# === Admin handles access ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("grant_") or call.data.startswith("reject_"))
def handle_access(call):
    if call.from_user.id != ADMIN_ID:
        return
    data = call.data.split("_")
    uid = int(data[1])
    if "reject" in call.data:
        bot.send_message(uid, "❌ Access denied.")
        bot.send_message(call.message.chat.id, "User rejected.")
    else:
        days = int(data[2])
        expiry = int(time.time()) + days * 86400
        cursor.execute("INSERT OR REPLACE INTO users (user_id, access, expiry) VALUES (?, 1, ?)", (uid, expiry))
        conn.commit()
        bot.send_message(uid, f"✅ Access granted for {days} day(s). You can now analyze matches.")
        bot.send_message(call.message.chat.id, "Access granted successfully.")

# === Analyze Match ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def match_request(msg):
    cursor.execute("SELECT expiry FROM users WHERE user_id = ?", (msg.chat.id,))
    row = cursor.fetchone()
    now = int(time.time())
    if row and row[0] > now:
        bot.send_message(msg.chat.id, "Send match details (teams, stage, etc):")
    else:
        bot.send_message(msg.chat.id, "❌ Access expired or missing. Click 💳 Donate & Get Access.")

# === Final Analysis ===
@bot.message_handler(func=lambda msg: True)
def analyze_match(msg):
    cursor.execute("SELECT expiry FROM users WHERE user_id = ?", (msg.chat.id,))
    row = cursor.fetchone()
    now = int(time.time())
    if not row or row[0] < now:
        return
    bot.send_message(msg.chat.id, "⚡ Analyzing the match...")
    try:
        prompt = f"""
Ты профессиональный футбольный аналитик. Ответь строго в таком формате:

Match: [Название турнира — команды]
Context: Ответный матч. Первая игра закончилась [счёт].
Location: [Город, стадион]

—

Прогноз:
• Основная ставка: [например, Победа Реала Мадрида]
• Уверенность: [Низкая / Средняя / Высокая]
• Дополнительная Ставка: [например, Тотал больше 2.5]

Now analyze:\n{msg.text}
"""
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response.choices[0].message.content
        for chunk in range(0, len(answer), 4000):
            bot.send_message(msg.chat.id, answer[chunk:chunk+4000])
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Error:\n{e}")

bot.polling()
