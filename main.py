import os
import sqlite3
import datetime
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

if not TELEGRAM_TOKEN or not GROQ_API_KEY or not ADMIN_ID:
    print("Warning: One or more environment variables are missing.")

admin_id_raw = os.getenv("ADMIN_ID")
if admin_id_raw is None:
    raise ValueError("ADMIN_ID is not set in environment variables")
ADMIN_ID = int(admin_id_raw)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if TELEGRAM_TOKEN is None:
    raise ValueError("TELEGRAM_TOKEN is not set in environment variables")
client = Groq(api_key=GROQ_API_KEY)

# === Flask App for Railway Uptime ===
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
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, access INTEGER DEFAULT 0)")
conn.commit()

# === Log Messages ===
def log_message(uid, username, msg):
    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("bot_log.txt", "a", encoding="utf-8") as f:
        f.write(f"[{time}] {uid} ({username}): {msg}\n")

# === /start ===
@bot.message_handler(commands=["start"])
def handle_start(msg):
    log_message(msg.chat.id, msg.from_user.username, "/start")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Analyze Match", "💳 Donate & Get Access")
    bot.send_message(msg.chat.id,
        "<b>Welcome to AI Match Predictor!</b>\n\n"
        "Access via one-time or subscription:\n"
        "• One-time: $5\n"
        "• Week: $25\n"
        "• Month: $65\n"
        "• Year: $390",
        parse_mode="HTML", reply_markup=markup)

# === Donate & Access ===
@bot.message_handler(func=lambda m: m.text == "💳 Donate & Get Access")
def handle_donate(msg):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(msg.chat.id,
        f"Send payment to:\n"
        f"💳 MIR: <code>{MIR_CARD}</code>\n"
        f"USDT (TRC20): <code>{CRYPTO_ADDRESS}</code>\n\n"
        "After payment, click '✅ I Paid'. Admin will verify manually.",
        parse_mode="HTML", reply_markup=markup)

# === Payment Request ===
@bot.callback_query_handler(func=lambda call: call.data == "paid")
def handle_paid(call):
    uid = call.message.chat.id
    log_message(uid, call.from_user.username, "Clicked I Paid")
    bot.send_message(uid, "Waiting for admin confirmation...")
    markup = types.InlineKeyboardMarkup([
        [types.InlineKeyboardButton("✅ Grant", callback_data=f"grant_{uid}"),
         types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]
    ])
    bot.send_message(ADMIN_ID,
        f"User @{call.from_user.username or call.from_user.first_name} ({uid}) submitted payment.",
        parse_mode="HTML", reply_markup=markup)

# === Admin Confirmation ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("grant_") or call.data.startswith("reject_"))
def admin_confirm(call):
    if call.from_user.id != ADMIN_ID:
        return
    uid = int(call.data.split("_")[1])
    if call.data.startswith("grant_"):
        cursor.execute("INSERT OR REPLACE INTO users (user_id, access) VALUES (?, 1)", (uid,))
        conn.commit()
        bot.send_message(uid, "✅ Access granted! You can now analyze matches.")
    else:
        bot.send_message(uid, "❌ Access denied.")

# === Match Analysis Button ===
@bot.message_handler(func=lambda m: m.text == "🔍 Analyze Match")
def handle_analysis_request(msg):
    uid = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id = ?", (uid,))
    row = cursor.fetchone()
    if row and row[0] == 1:
        bot.send_message(uid, "Send match details:")
    else:
        bot.send_message(uid, "❌ Access denied. Please donate first.")

# === Match Analysis ===
@bot.message_handler(func=lambda m: True)
def handle_analysis(msg):
    uid = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id = ?", (uid,))
    row = cursor.fetchone()
    if not row or row[0] != 1:
        return
    log_message(uid, msg.from_user.username, msg.text)
    bot.send_message(uid, "Analyzing match, please wait...")

    prompt = f"""
You are a professional football analyst.
Generate a high-confidence prediction using this format:

Match: [Name]
Stage: [Stage]
—
Key Points:
• ...
• ...
—
Prediction:
• Result: [Win / Total / Handicap]
• Confidence: [High]
—
Input: {msg.text}
"""

    try:
        res = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        answer = res.choices[0].message.content
        for part in range(0, len(answer), 4000):
            bot.send_message(uid, answer[part:part+4000])
    except Exception as e:
        bot.send_message(uid, f"Error: {e}")
        log_message(uid, "ERROR", str(e))

bot.polling(none_stop=True)
