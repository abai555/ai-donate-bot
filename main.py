import telebot
import sqlite3
from flask import Flask
from threading import Thread
from groq import Groq

# === CONFIG ===
TELEGRAM_TOKEN = "7241781324:AAFOgQ8QgTiCOC1efBUoPeu7UzM7Yu2UXvo"
GROQ_API_KEY = "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"
ADMIN_ID = 1023932092  # Замени на свой Telegram ID
MIR_CARD = "2200701901154812"
CRYPTO_ADDRESS = "TH92J3hUqbAgpXiC5NtkxFHGe2vB9yUonH"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# === Flask для UptimeRobot / Railway ===
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"
def run():
    app.run(host="0.0.0.0", port=8080)
Thread(target=run).start()

# === SQLite база данных ===
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, access INTEGER DEFAULT 0)""")
conn.commit()

# === Команда /start ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Analyze Match", "💳 Donate & Get Access")
    bot.send_message(
        message.chat.id,
        "<b>🤖 AI Match Analyzer</b>\n\n"
        "Get professional football match predictions using AI.\n"
        "Access is granted after one-time or recurring donation.\n\n"
        "<b>Prices:</b>\n"
        "• One-time – $5\n"
        "• Weekly – $25\n"
        "• Monthly – $65\n"
        "• Yearly – $390",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Донат и доступ ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def donate(msg):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(
        msg.chat.id,
        f"<b>Payment Instructions:</b>\n\n"
        f"💳 MIR Card: <code>{MIR_CARD}</code>\n"
        f"🪙 USDT TRC20: <code>{CRYPTO_ADDRESS}</code>\n\n"
        "After sending payment, click the button below.",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Кнопка "I Paid" ===
@bot.callback_query_handler(func=lambda call: call.data == "paid")
def handle_paid(call):
    user_id = call.message.chat.id
    bot.send_message(user_id, "🕓 Payment submitted. Please wait for confirmation.")
    bot.send_message(
        ADMIN_ID,
        f"🧾 New access request:\nUser: @{call.from_user.username or 'NoUsername'}\nID: {user_id}",
        reply_markup=telebot.types.InlineKeyboardMarkup([
            [telebot.types.InlineKeyboardButton("✅ Grant Access", callback_data=f"grant_{user_id}"),
             telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")]
        ])
    )

# === Подтверждение/отказ админом ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("grant_") or call.data.startswith("reject_"))
def handle_admin_decision(call):
    if call.from_user.id != ADMIN_ID:
        return
    user_id = int(call.data.split("_")[1])
    if call.data.startswith("grant_"):
        cursor.execute("INSERT OR REPLACE INTO users (user_id, access) VALUES (?, 1)", (user_id,))
        conn.commit()
        bot.send_message(user_id, "✅ Access granted! You can now analyze matches.")
    else:
        bot.send_message(user_id, "❌ Access denied.")
    bot.send_message(call.message.chat.id, "✅ Handled.")

# === Проверка доступа ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def check_access(msg):
    user_id = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result and result[0] == 1:
        bot.send_message(user_id, "✅ Send the match details to analyze (teams, stage, context).")
    else:
        bot.send_message(user_id, "❌ Access denied. Please donate first.")

# === Анализ матча ===
@bot.message_handler(func=lambda msg: True)
def analyze_match(msg):
    user_id = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if not result or result[0] != 1:
        return
    bot.send_message(user_id, "⚡ Analyzing match...")

    try:
        prompt = f"""
You are a betting AI. Provide a realistic football prediction using only this format:

Match: [Team A vs Team B]  
Tournament: [Tournament Name]  
Date: [Approximate Date]

—

Prediction:  
• Bet: [e.g. Over 2.5 goals / Both Teams to Score]  
• Odds: ~[Approx. odds like 1.80]  
• Confidence: [High / Medium / Low]

—

Reasoning:
• 1 short fact  
• 2nd short fact  
• 3rd short fact

Match: {msg.text}
"""
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content
        for chunk in range(0, len(result), 4000):
            bot.send_message(user_id, result[chunk:chunk+4000])
    except Exception as e:
        bot.send_message(user_id, f"❌ Error:\n{e}")

bot.polling()
