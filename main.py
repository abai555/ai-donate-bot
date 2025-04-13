import telebot
import sqlite3
from flask import Flask
from threading import Thread
from groq import Groq

# === CONFIG ===
import os
TELEGRAM_TOKEN = os.getenv("7241781324:AAFOgQ8QgTiCOC1efBUoPeu7UzM7Yu2UXvo")
GROQ_API_KEY = os.getenv("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")
ADMIN_ID = int(os.getenv("1023932092"))
MIR_CARD = os.getenv("2200701901154812")
CRYPTO_ADDRESS = os.getenv("TH92J3hUqbAgpXiC5NtkxFHGe2vB9yUonH")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"
def run():
    app.run(host="0.0.0.0", port=8080)
Thread(target=run).start()

conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, access INTEGER DEFAULT 0)")
conn.commit()

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Analyze Match", "💳 Donate & Get Access")
    bot.send_message(
        message.chat.id,
        "<b>🤖 AI Match Analyzer</b>

"
        "Get football predictions using AI.

"
        "<b>Pricing:</b>
"
        "• One-time – $5
• Weekly – $25
• Monthly – $65
• Yearly – $390",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def donate(msg):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(
        msg.chat.id,
        f"<b>Payment Info:</b>

"
        f"💳 MIR Card: <code>{MIR_CARD}</code>
"
        f"🪙 USDT TRC20: <code>{CRYPTO_ADDRESS}</code>

"
        "Click '✅ I Paid' after payment.",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "paid")
def handle_paid(call):
    uid = call.message.chat.id
    bot.send_message(uid, "🕓 Payment sent. Waiting for confirmation.")
    bot.send_message(
        ADMIN_ID,
        f"🧾 Payment request:
User: @{call.from_user.username or 'NoUsername'}
ID: {uid}",
        reply_markup=telebot.types.InlineKeyboardMarkup([
            [telebot.types.InlineKeyboardButton("✅ Grant", callback_data=f"grant_{uid}"),
             telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]
        ])
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("grant_") or call.data.startswith("reject_"))
def confirm_access(call):
    if call.from_user.id != ADMIN_ID:
        return
    uid = int(call.data.split("_")[1])
    if call.data.startswith("grant_"):
        cursor.execute("INSERT OR REPLACE INTO users (user_id, access) VALUES (?, 1)", (uid,))
        conn.commit()
        bot.send_message(uid, "✅ Access granted.")
    else:
        bot.send_message(uid, "❌ Access denied.")
    bot.send_message(call.message.chat.id, "Access processed.")

@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def request_analysis(msg):
    uid = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id=?", (uid,))
    result = cursor.fetchone()
    if result and result[0] == 1:
        bot.send_message(uid, "✅ Send match info:")
    else:
        bot.send_message(uid, "❌ Access required. Use '💳 Donate & Get Access'.")

@bot.message_handler(func=lambda msg: True)
def analyze(msg):
    uid = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id=?", (uid,))
    result = cursor.fetchone()
    if not result or result[0] != 1:
        return
    bot.send_message(uid, "⚡ Analyzing match...")

    prompt = f'''
You are a football betting expert. Predict this match using a realistic betting style.
Only suggest safe bets like:
- Over/Under goals
- Handicap
- Both Teams to Score
- Draw No Bet
- Double Chance

Avoid unrealistic or crazy scorelines.

Respond in this format:

Match: [Team A vs Team B]
Tournament: [Competition Name]
Date: [Expected Date]

—

Prediction:
• Bet: [Example: Over 2.5 goals]
• Odds: ~[1.70–2.20]
• Confidence: [Low / Medium / High]

—

Reasoning:
• 1 short fact
• 2nd short fact
• 3rd short fact

Match: {msg.text}
'''

    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content
        for chunk in range(0, len(result), 4000):
            bot.send_message(uid, result[chunk:chunk+4000])
    except Exception as e:
        bot.send_message(uid, f"❌ Error:
{e}")

bot.polling()
