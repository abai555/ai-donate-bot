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

# === Flask uptime ===
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

# === Helpers ===
def has_subscription(user_id):
    cursor.execute("SELECT expires_at FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row:
        return datetime.strptime(row[0], "%Y-%m-%d") >= datetime.now()
    return False

def grant_subscription(user_id, days):
    expires = datetime.now() + timedelta(days=days)
    cursor.execute("INSERT OR REPLACE INTO users (user_id, expires_at) VALUES (?, ?)", (user_id, expires.date()))
    conn.commit()

# === /start ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Analyze Match", "💳 Donate & Get Access")
    markup.row("📊 Subscription Status")
    bot.send_message(message.chat.id,
        "🤖 <b>AI Football Predictions</b>\n\n"
        "Get accurate match analysis and tips.\n\n"
        "<b>Pricing:</b>\n"
        "• One-time: $5\n"
        "• Weekly: $25\n"
        "• Monthly: $65\n"
        "• Yearly: $390",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "📊 Subscription Status")
def check_status(msg):
    cursor.execute("SELECT expires_at FROM users WHERE user_id=?", (msg.chat.id,))
    row = cursor.fetchone()
    if row:
        bot.send_message(msg.chat.id, f"✅ Subscription active.\nExpires in {(datetime.strptime(row[0], '%Y-%m-%d') - datetime.now()).days} day(s).")
    else:
        bot.send_message(msg.chat.id, "❌ No active subscription.")

# === Donate ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def donate_info(msg):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(msg.chat.id,
        f"<b>💳 Payment Info</b>\n\n"
        f"MIR: <code>{MIR_CARD}</code>\n"
        f"USDT TRC20: <code>{CRYPTO_ADDRESS}</code>\n\n"
        "Press the button when payment is done.",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "paid")
def confirm_payment(call):
    bot.send_message(call.message.chat.id, "Your request was sent for manual approval.")
    bot.send_message(ADMIN_ID,
        f"User @{call.from_user.username or 'NoUsername'} ({call.from_user.id}) requests access.",
        reply_markup=telebot.types.InlineKeyboardMarkup([
            [telebot.types.InlineKeyboardButton("✅ One-time", callback_data=f"grant_{call.from_user.id}_1")],
            [telebot.types.InlineKeyboardButton("📅 Week", callback_data=f"grant_{call.from_user.id}_7")],
            [telebot.types.InlineKeyboardButton("🗓️ Month", callback_data=f"grant_{call.from_user.id}_30")],
            [telebot.types.InlineKeyboardButton("🗓️ Year", callback_data=f"grant_{call.from_user.id}_365")],
            [telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{call.from_user.id}")]
        ])
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("grant_") or call.data.startswith("reject_"))
def handle_admin_action(call):
    parts = call.data.split("_")
    uid = int(parts[1])
    if call.from_user.id != ADMIN_ID:
        return
    if parts[0] == "grant":
        days = int(parts[2])
        grant_subscription(uid, days)
        bot.send_message(uid, "✅ Subscription granted!")
        bot.send_message(call.message.chat.id, "Access approved.")
    else:
        bot.send_message(uid, "❌ Access denied.")
        bot.send_message(call.message.chat.id, "User rejected.")

# === Analyze Match ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def request_match_info(msg):
    if has_subscription(msg.chat.id):
        bot.send_message(msg.chat.id, "Send match info (e.g. Real Madrid vs Arsenal, first leg 0:3).")
    else:
        bot.send_message(msg.chat.id, "❌ No access. Use 💳 Donate & Get Access.")

@bot.message_handler(func=lambda msg: True)
def handle_analysis(msg):
    if not has_subscription(msg.chat.id):
        return
    bot.send_message(msg.chat.id, "⚡ Analyzing...")
    try:
        prompt = f"""
Ты футбольный аналитик. Ответь кратко и строго по шаблону на русском языке:

Match: [Название турнира — команды. Упомяни результат первого матча и где пройдет ответный.]

Прогноз:
• Основная ставка: [Победа одной из команд или ничья]
• Уверенность: [Низкая/Средняя/Высокая]
• Дополнительная ставка: [Например, Тотал матча, Тотал первого тайма, Тотал команды]

Используй этот шаблон и проанализируй матч: {msg.text}
"""
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content
        bot.send_message(msg.chat.id, result)
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Error:\n{e}")

bot.polling()
