import telebot
import sqlite3
from flask import Flask
from threading import Thread
from groq import Groq

# === CONFIG ===
TELEGRAM_TOKEN = "7740303549:AAFqFSEBwJ7wQlFlp_8vrBQl7x0R2HzPlUE"
GROQ_API_KEY = "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"
ADMIN_ID = 1023932092  # Replace with your Telegram ID
CRYPTO_ADDRESS = "TH92J3hUqbAgpXiC5NtkxFHGe2vB9yUonH"
MIR_CARD = "2200701901154812"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# === Flask uptime ===
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

# === /start ===
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Welcome!", reply_markup=telebot.types.ReplyKeyboardRemove())
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

# === Donate ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def donate_info(msg):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(
        msg.chat.id,
        f"Send payment to:\n\n"
        f"💳 MIR Card: <code>{MIR_CARD}</code>\n"
        f"🪙 USDT TRC20: <code>{CRYPTO_ADDRESS}</code>\n\n"
        "Then click '✅ I Paid'",
        parse_mode="HTML",
        reply_markup=markup
    )

# === I Paid button ===
@bot.callback_query_handler(func=lambda call: call.data == "paid")
def paid_submitted(call):
    uid = call.message.chat.id
    bot.send_message(uid, "🕓 Payment submitted. Please wait for confirmation.")
    bot.send_message(ADMIN_ID,
        f"🧾 New payment request\n"
        f"User: @{call.from_user.username or call.from_user.first_name} ({uid})\n"
        f"Confirm access?",
        reply_markup=telebot.types.InlineKeyboardMarkup([
            [telebot.types.InlineKeyboardButton("✅ Grant", callback_data=f"grant_{uid}"),
             telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]
        ])
    )

# === Admin confirms ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("grant_") or call.data.startswith("reject_"))
def admin_confirm(call):
    uid = int(call.data.split("_")[1])
    if not call.from_user.id == ADMIN_ID:
        return
    if call.data.startswith("grant_"):
        cursor.execute("INSERT OR REPLACE INTO users (user_id, access) VALUES (?, 1)", (uid,))
        conn.commit()
        bot.send_message(uid, "✅ Access granted! You can now analyze matches.")
    else:
        bot.send_message(uid, "❌ Access denied.")

# === Analyze Match button ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def analyze_check(msg):
    uid = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if row and row[0] == 1:
        bot.send_message(uid, "✅ Send the match details:")
    else:
        bot.send_message(uid, "❌ You must donate first. Click '💳 Donate & Get Access'.")

# === AI analysis ===
@bot.message_handler(func=lambda msg: True)
def analyze_match(msg):
    uid = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if not row or row[0] != 1:
        return
    bot.send_message(uid, "⚡ Analyzing match...")
    try:
        prompt = f"""You are a football match analyst.
Provide an expert prediction in this format:

Match: [Match Name]
Stage: [Stage]
Location: [Stadium]

—

Key Factors:
• Point 1
• Point 2
• Point 3
• Point 4
• Point 5

—

Prediction:
• Outcome: [Winner or Both Score]
• Score: [Example: 2:1]
• Confidence: [High / Very High]

—

Express Bet (3+ odds):
• Option 1
• Option 2
• Option 3

Now analyze:\n{msg.text}
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

bot.polling()
