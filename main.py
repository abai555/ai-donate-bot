import os
import sqlite3
from flask import Flask
from threading import Thread
from telebot import TeleBot, types
from groq import Groq

# === ENV CONFIG ===
TELEGRAM_TOKEN = os.getenv("7241781324:AAFOgQ8QgTiCOC1efBUoPeu7UzM7Yu2UXvo")
GROQ_API_KEY = os.getenv("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")
ADMIN_ID = os.getenv("1023932092")
CRYPTO_ADDRESS = os.getenv("TH92J3hUqbAgpXiC5NtkxFHGe2vB9yUonH")
MIR_CARD = os.getenv("2200701901154812")

if not all([TELEGRAM_TOKEN, GROQ_API_KEY, ADMIN_ID]):
    raise ValueError("TELEGRAM_TOKEN, GROQ_API_KEY, ADMIN_ID must be set in environment variables")

bot = TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# === Flask App for Railway Uptime ===
app = Flask(__name__)
@app.route("/")
def home():
    return "Bot is live!"

Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# === SQLite Users DB ===
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, access INTEGER DEFAULT 0)")
conn.commit()

# === Start ===
@bot.message_handler(commands=['start'])
def start(msg):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Analyze Match", "💳 Donate & Get Access")
    bot.send_message(
        msg.chat.id,
        "<b>🤖 AI Match Analyzer</b>\n\n"
        "Predict matches using AI.\n"
        "Access requires donation:\n"
        "• One-time – $5\n"
        "• Weekly – $25\n"
        "• Monthly – $65\n"
        "• Yearly – $390",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Donate Button ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def donate(msg):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(
        msg.chat.id,
        f"Send payment to:\n\n"
        f"💳 MIR: <code>{MIR_CARD}</code>\n"
        f"🪙 USDT (TRC20): <code>{CRYPTO_ADDRESS}</code>\n\n"
        "Then press '✅ I Paid'. Access will be granted after approval.",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Manual Payment Confirmation ===
@bot.callback_query_handler(func=lambda call: call.data == "paid")
def check_payment(call):
    uid = call.from_user.id
    bot.send_message(uid, "🕓 Waiting for confirmation...")
    bot.send_message(
        int(ADMIN_ID),
        f"🧾 New request\nUser: @{call.from_user.username} ({uid})\n\nGrant access?",
        reply_markup=types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("✅ Grant", callback_data=f"grant_{uid}"),
             types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]
        ]),
        parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("grant_") or call.data.startswith("reject_"))
def handle_admin_decision(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        return
    uid = int(call.data.split("_")[1])
    if call.data.startswith("grant_"):
        cursor.execute("INSERT OR REPLACE INTO users (user_id, access) VALUES (?, 1)", (uid,))
        conn.commit()
        bot.send_message(uid, "✅ Access granted.")
        bot.send_message(call.message.chat.id, "User confirmed.")
    else:
        bot.send_message(uid, "❌ Access denied.")
        bot.send_message(call.message.chat.id, "User rejected.")

# === Match Prediction ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def ask_match(msg):
    uid = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id=?", (uid,))
    access = cursor.fetchone()
    if access and access[0] == 1:
        bot.send_message(uid, "Send the match details (teams, stage, etc.):")
    else:
        bot.send_message(uid, "❌ Access denied. Please click 'Donate & Get Access'.")

@bot.message_handler(func=lambda msg: True)
def analyze(msg):
    uid = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id=?", (uid,))
    access = cursor.fetchone()
    if not access or access[0] != 1:
        return

    prompt = f"""
You are a football analyst. Generate a safe and realistic prediction for this match with betting tips (winner, total, handicap).

Match: {msg.text}
"""
    try:
        bot.send_message(uid, "⚡ Analyzing match...")
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response.choices[0].message.content
        bot.send_message(uid, answer[:4096])
    except Exception as e:
        bot.send_message(uid, f"❌ Error:\n{e}")

bot.polling()
