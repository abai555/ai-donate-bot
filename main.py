import telebot
import sqlite3
from flask import Flask
from threading import Thread
from groq import Groq

# === API KEYS ===
TELEGRAM_TOKEN = "7710632976:AAEf3KbdDQ8lV6LAR8A2iRKGNcIFbrUQa8A"
GROQ_API_KEY = "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"
CRYPTO_ADDRESS = "TH92J3hUqbAgpXiC5NtkxFHGe2vB9yUonH"
MIR_CARD = "2200701901154812"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# === Flask App ===
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run).start()

# === Database ===
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    paid INTEGER DEFAULT 0
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
        "🤖 <b>AI Match Analyzer</b>\n\n"
        "🔶 <b>Analyze matches using AI and Groq</b>\n\n"
        "🧊 <b>Features:</b>\n"
        "- AI-based predictions\n"
        "- Manual payments via MIR card or crypto\n"
        "- Subscriptions: Weekly / Monthly / Yearly\n\n"
        "👇 Press the button to start analyzing!",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Donate Button ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def donate(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(
        message.chat.id,
        "<b>To activate access, send payment to:</b>\n\n"
        f"💳 MIR Card: <code>{MIR_CARD}</code>\n"
        f"🪙 USDT TRC20: <code>{CRYPTO_ADDRESS}</code>\n\n"
        "💰 <b>Prices:</b>\n"
        "• One-time access – $5\n"
        "• Weekly – $25\n"
        "• Monthly – $65\n"
        "• Yearly – $390\n\n"
        "Then click the button below.",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Confirm Payment ===
@bot.callback_query_handler(func=lambda call: call.data == "paid")
def confirm_payment(call):
    user_id = call.message.chat.id
    cursor.execute("INSERT OR REPLACE INTO users (user_id, paid) VALUES (?, ?)", (user_id, 1))
    conn.commit()
    bot.send_message(user_id, "✅ Access granted! You can now use Analyze Match.")

# === Analyze Button ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def analyze_access(msg):
    cursor.execute("SELECT paid FROM users WHERE user_id = ?", (msg.chat.id,))
    user = cursor.fetchone()
    if user and user[0] == 1:
        bot.send_message(msg.chat.id, "✅ Send match info to analyze:")
    else:
        bot.send_message(msg.chat.id, "❌ Access denied. Please pay first by clicking '💳 Donate & Get Access'.")

# === Analysis ===
@bot.message_handler(func=lambda msg: True)
def analyze(msg):
    cursor.execute("SELECT paid FROM users WHERE user_id = ?", (msg.chat.id,))
    user = cursor.fetchone()
    if not user or user[0] != 1:
        return
    bot.send_message(msg.chat.id, "⚡ Analyzing...")
    try:
        prompt = f"Briefly analyze this match and predict the outcome:\n{msg.text}"
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content
        for x in range(0, len(result), 4000):
            bot.send_message(msg.chat.id, result[x:x+4000])
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Error:\n{e}")

bot.polling()
