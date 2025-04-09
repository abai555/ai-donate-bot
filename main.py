import telebot
import sqlite3
from flask import Flask
from threading import Thread
from groq import Groq
import datetime

# === CONFIG ===
TELEGRAM_TOKEN = "7740303549:AAEbHCT-e9scnxi8XNMp6zwXjutAcBMuvJk"
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

# === Logging Function ===
def log_message(user_id, username, message):
    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("bot_message_log.txt", "a", encoding="utf-8") as log_file:
        log_file.write(f"[{time}] {user_id} ({username}): {message}\n")

# === /start ===
@bot.message_handler(commands=['start'])
def start(message):
    log_message(message.chat.id, message.from_user.username, "/start")
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Analyze Match", "💳 Donate & Get Access")
    bot.send_message(
        message.chat.id,
        "<b>🤖 AI Match Analyzer</b>\n\n"
        "Analyze football matches with AI.\n"
        "Access requires a one-time or subscription payment.\n\n"
        "<b>Pricing:</b>\n"
        "• One-time – $5\n"
        "• Weekly – $25\n"
        "• Monthly – $65\n"
        "• Yearly – $390",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Donate & Access ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def donate_info(msg):
    log_message(msg.chat.id, msg.from_user.username, "💳 Donate & Get Access")
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(
        msg.chat.id,
        f"Send donation to:\n\n"
        f"💳 MIR Card: <code>{MIR_CARD}</code>\n"
        f"🪙 USDT TRC20: <code>{CRYPTO_ADDRESS}</code>\n\n"
        "Then press '✅ I Paid'. Access will be granted after manual confirmation.",
        parse_mode="HTML",
        reply_markup=markup
    )

# === I Paid Pressed ===
@bot.callback_query_handler(func=lambda call: call.data == "paid")
def paid_submitted(call):
    uid = call.message.chat.id
    log_message(uid, call.from_user.username, "Pressed I Paid")
    bot.send_message(uid, "🕓 Payment submitted. Please wait for confirmation.")
    bot.send_message(ADMIN_ID,
        f"🧾 <b>New payment request</b>\n"
        f"User: @{call.from_user.username or call.from_user.first_name} ({uid})\n\n"
        f"Confirm access?",
        parse_mode="HTML",
        reply_markup=telebot.types.InlineKeyboardMarkup([
            [telebot.types.InlineKeyboardButton("✅ Grant", callback_data=f"grant_{uid}"),
             telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]
        ])
    )

# === Admin Confirms ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("grant_") or call.data.startswith("reject_"))
def admin_confirm(call):
    uid = int(call.data.split("_")[1])
    if not call.from_user.id == ADMIN_ID:
        return
    if call.data.startswith("grant_"):
        cursor.execute("INSERT OR REPLACE INTO users (user_id, access) VALUES (?, 1)", (uid,))
        conn.commit()
        bot.send_message(uid, "✅ Access granted! You can now analyze matches.")
        bot.send_message(call.message.chat.id, "Access confirmed.")
        log_message(uid, "admin", "Access granted")
    else:
        bot.send_message(uid, "❌ Access denied. Please make sure you paid.")
        bot.send_message(call.message.chat.id, "Access rejected.")
        log_message(uid, "admin", "Access denied")

# === Match Button ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def analyze_check(msg):
    log_message(msg.chat.id, msg.from_user.username, "Clicked Analyze Match")
    uid = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if row and row[0] == 1:
        bot.send_message(uid, "✅ Send the match details (team names, stage, and other context):")
    else:
        bot.send_message(uid, "❌ You must donate first. Click '💳 Donate & Get Access'.")

# === Actual Analysis ===
@bot.message_handler(func=lambda msg: True)
def analyze_match(msg):
    log_message(msg.chat.id, msg.from_user.username, msg.text)
    uid = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if not row or row[0] != 1:
        return
    bot.send_message(uid, "⚡ Analyzing match...")
    try:
        prompt = f"""You are a professional football match analyst.
Analyze this match and respond in this structure:

Match: [Match Name]
Stage: [Tournament stage, round]
Location: [Stadium, City]

—

Key Factors:
• Bullet-point 1
• Bullet-point 2
• Bullet-point 3
• Bullet-point 4
• Bullet-point 5

—

Prediction:
• Outcome: [Both teams to score / Winner]
• Score: [e.g. 2:1]
• Confidence: [Low / Medium / High / Very High]

—

Alternative Express Bet (3+ odds):
• Bet 1
• Bet 2
• Bet 3

Now analyze this match:\n{msg.text}
"""
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response.choices[0].message.content
        for part in range(0, len(answer), 4000):
            bot.send_message(uid, answer[part:part+4000])
    except Exception as e:
        bot.send_message(uid, f"❌ Error:\n{e}")
        log_message(uid, "error", str(e))

bot.polling()
