import telebot
import sqlite3
from flask import Flask
from threading import Thread
from groq import Groq
import datetime

# === CONFIG ===
TELEGRAM_TOKEN = "7241781324:AAFOgQ8QgTiCOC1efBUoPeu7UzM7Yu2UXvo"
GROQ_API_KEY = "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"
ADMIN_ID = 1023932092  # Replace with your Telegram ID
CRYPTO_ADDRESS = "TH92J3hUqbAgpXiC5NtkxFHGe2vB9yUonH"
MIR_CARD = "2200701901154812"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# === Flask Uptime ===
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is alive!"
def run():
    app.run(host="0.0.0.0", port=8080)
Thread(target=run).start()

# === Database ===
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    access INTEGER DEFAULT 0
)
""")
conn.commit()

# === Logging ===
def log_message(user_id, username, message):
    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("bot_log.txt", "a", encoding="utf-8") as f:
        f.write(f"[{time}] {user_id} ({username}): {message}\n")

# === /start ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Analyze Match", "💳 Donate & Get Access")
    bot.send_message(
        message.chat.id,
        "<b>🤖 AI Match Analyzer</b>\n\n"
        "Analyze football matches using Groq AI.\n"
        "Pay once or get a subscription.\n\n"
        "<b>Prices:</b>\n"
        "• One-time – $5\n"
        "• Weekly – $25\n"
        "• Monthly – $65\n"
        "• Yearly – $390",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Donate Info ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def donate_info(msg):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(
        msg.chat.id,
        f"Send your donation to:\n\n"
        f"💳 MIR Card: <code>{MIR_CARD}</code>\n"
        f"🪙 USDT (TRC20): <code>{CRYPTO_ADDRESS}</code>\n\n"
        "Then click '✅ I Paid'. Access is given manually.",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Payment Confirmed ===
@bot.callback_query_handler(func=lambda call: call.data == "paid")
def confirm_request(call):
    uid = call.message.chat.id
    bot.send_message(uid, "🕓 Payment submitted. Please wait for manual approval.")
    bot.send_message(ADMIN_ID,
        f"💰 New payment request from @{call.from_user.username or call.from_user.first_name} ({uid})",
        reply_markup=telebot.types.InlineKeyboardMarkup([
            [telebot.types.InlineKeyboardButton("✅ Grant", callback_data=f"grant_{uid}"),
             telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]
        ])
    )

# === Grant or Reject Access ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("grant_") or call.data.startswith("reject_"))
def access_manage(call):
    uid = int(call.data.split("_")[1])
    if call.from_user.id != ADMIN_ID:
        return
    if call.data.startswith("grant_"):
        cursor.execute("INSERT OR REPLACE INTO users (user_id, access) VALUES (?, 1)", (uid,))
        conn.commit()
        bot.send_message(uid, "✅ Access granted! Send a match to analyze.")
        bot.send_message(call.message.chat.id, "Confirmed.")
    else:
        bot.send_message(uid, "❌ Access denied.")
        bot.send_message(call.message.chat.id, "Rejected.")

# === Match Access Check ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def match_access(msg):
    uid = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id=?", (uid,))
    if cursor.fetchone() and cursor.fetchone()[0] == 1:
        bot.send_message(uid, "Send match details (teams, stage, etc):")
    else:
        bot.send_message(uid, "❌ You need to donate first. Tap '💳 Donate & Get Access'.")

# === Match Analysis (Realistic) ===
@bot.message_handler(func=lambda msg: True)
def analyze(msg):
    uid = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id=?", (uid,))
    if not cursor.fetchone() or cursor.fetchone()[0] != 1:
        return
    bot.send_message(uid, "⚡ Analyzing match...")
    try:
        prompt = f"""
You are a football betting expert. Your task is to predict a match based on form, tournament, and realistic stats.

Do not invent crazy or random scores.

Only give safe, high-probability betting suggestions like:
• Over/Under 2.5
• Handicap (-1)
• Draw No Bet
• Double Chance
• Both Teams to Score
• Total Goals Range

Avoid exotic bets or fantasy outcomes.

—

Analyze this match strictly and reply in this format:

Match: [Team A vs Team B]  
Tournament: [Name]  
Date: [Approximate date]

—

Prediction:  
• Bet: [e.g., Over 2.5 goals, BTTS, Handicap -1]  
• Odds: [Approximate realistic odds]  
• Confidence: [Low / Medium / High]  

—

Short Reason:
• Factor 1  
• Factor 2  
• Factor 3

Now analyze:\n{msg.text}
"""
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content
        for part in range(0, len(result), 4000):
            bot.send_message(uid, result[part:part+4000])
    except Exception as e:
        bot.send_message(uid, f"❌ Error:\n{e}")

bot.polling()
