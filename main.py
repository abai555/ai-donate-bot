import telebot
from flask import Flask
from threading import Thread
from groq import Groq
import time
import sqlite3

# === CONFIG ===
TELEGRAM_TOKEN = "7710632976:AAEf3KbdDQ8lV6LAR8A2iRKGNcIFbrUQa8A"
GROQ_API_KEY = "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"
ADMIN_ID =1023932092
MIR_CARD = "2200701901154812"
CRYPTO_ADDRESS = "148rExWeZAAujT7z9BNwv3ERhJTgk2zEJz"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# === Flask for uptime ===
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"
def run():
    app.run(host='0.0.0.0', port=8080)
Thread(target=run).start()

# === Database ===
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    subscription TEXT,
    expiry_date INTEGER
)
""")
conn.commit()

# === /start ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Analyze Match", "💳 Donate & Get Access")
    
    bot.send_message(
        message.chat.id,
        "<b>🤖 AI Match Analyzer</b> — an AI-powered match analysis bot.\n\n"
        "♦️ <b>Features:</b>\n"
        "- Analyze matches using AI and Groq.\n"
        "- Get predictions\n"
        "- Pay via MIR card or crypto\n"
        "- Subscriptions: Weekly / Monthly / Yearly.\n\n"
        "👇 Press the button to start analyzing!",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Donation instructions ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def show_payment(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(
        message.chat.id,
        f"💰 To unlock access, send payment to:

"
        f"💳 MIR Card: <code>{MIR_CARD}</code>
"
        f"🪙 USDT TRC20: <code>{CRYPTO_ADDRESS}</code>

"
        f"Then press the button below.",
        parse_mode="HTML",
        reply_markup=markup
    )

# === User clicked "I Paid" ===
@bot.callback_query_handler(func=lambda call: call.data == "paid")
def confirm_payment(call):
    user = call.message.chat
    bot.send_message(ADMIN_ID, f"⚠️ @{user.username or user.first_name} ({user.id}) clicked 'I Paid'.")
    bot.send_message(user.id, "✅ Thank you! Your request will be verified soon.")

# === Analyze button ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def analyze_btn(msg):
    user_id = msg.chat.id
    cursor.execute("SELECT expiry_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row and row[0] > int(time.time()):
        bot.send_message(user_id, "✅ Send the match details:")
    else:
        show_payment(msg)

# === Handle match text ===
@bot.message_handler(func=lambda msg: True)
def analyze_match(msg):
    user_id = msg.chat.id
    cursor.execute("SELECT expiry_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row or row[0] < int(time.time()):
        return show_payment(msg)

    bot.send_message(user_id, "⚡ Analyzing...")
    try:
        prompt = f"Give a brief analysis with expected odds:\n\n{msg.text}"
        res = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        result = res.choices[0].message.content
        for x in range(0, len(result), 4000):
            bot.send_message(user_id, result[x:x+4000])
    except Exception as e:
        bot.send_message(user_id, f"❌ Error: {e}")

bot.polling()
