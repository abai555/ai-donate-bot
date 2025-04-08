import telebot
from groq import Groq
from flask import Flask
from threading import Thread
import time
import sqlite3

# === CONFIG ===
TELEGRAM_TOKEN = "7710632976:AAEf3KbdDQ8lV6LAR8A2iRKGNcIFbrUQa8A"
GROQ_API_KEY = "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"
CRYPTO_ADDRESS = "TH92J3hUqbAgpXiC5NtkxFHGe2vB9yUonH"
MIR_CARD = "2200701901154812"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# === Flask for Railway Uptime ===
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
    subscription TEXT,
    expiry_date INTEGER
)
""")
conn.commit()

# === /start ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Analyze Match", "💳 Donate & Get Access")
    bot.send_message(
        message.chat.id,
        "<b>🤖 AI Match Analyzer</b>\n\n"
        "🔶 Analyze matches using AI and Groq\n\n"
        "<b>💠 Features:</b>\n"
        "- AI-based predictions\n"
        "- Manual payments via MIR card or crypto\n"
        "- Subscriptions: Weekly / Monthly / Yearly\n\n"
        "👇 Press the button to start analyzing!",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Payment Instructions ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def show_payment_info(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(
        message.chat.id,
        f"To activate access, send payment to:\n\n"
        f"💳 MIR Card: <code>{MIR_CARD}</code>\n"
        f"🪙 USDT TRC20: <code>{CRYPTO_ADDRESS}</code>\n\n"
        f"Then click the button below.",
        parse_mode="HTML",
        reply_markup=markup
    )

# === After payment confirmation ===
@bot.callback_query_handler(func=lambda call: call.data == "paid")
def confirm_payment(call):
    bot.send_message(call.message.chat.id, "✅ Please wait while we verify your payment (manual review).")

# === Analyze Match Prompt ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def ask_for_match(message):
    bot.send_message(message.chat.id, "✅ Send match info to analyze:")

# === Handle User Message ===
@bot.message_handler(func=lambda msg: True)
def analyze_match(msg):
    bot.send_message(msg.chat.id, "⚡ Analyzing match...")
    try:
        prompt = f"Analyze this match briefly and provide predictions:\n{msg.text}"
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content
        for i in range(0, len(result), 4096):
            bot.send_message(msg.chat.id, result[i:i+4096])
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Error: {e}")

# === Polling ===
bot.polling(none_stop=True)
