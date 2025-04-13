import telebot
import sqlite3
from groq import Groq
import os

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("7241781324:AAFOgQ8QgTiCOC1efBUoPeu7UzM7Yu2UXvo")
GROQ_API_KEY = os.getenv("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")
ADMIN_ID = int(os.getenv("1023932092"))
MIR_CARD = os.getenv("2200701901154812")
CRYPTO_ADDRESS = os.getenv("TH92J3hUqbAgpXiC5NtkxFHGe2vB9yUonH")

# === INIT ===
bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# === DATABASE ===
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
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔍 Analyze Match", "💳 Donate & Get Access")
    bot.send_message(message.chat.id,
        "<b>🤖 AI Match Analyzer</b>\n\n"
        "Predict football matches using powerful AI.\n"
        "Access is granted after one-time or subscription donation.\n\n"
        "<b>Pricing:</b>\n"
        "• One-time: $5\n"
        "• Weekly: $25\n"
        "• Monthly: $65\n"
        "• Yearly: $390",
        parse_mode="HTML", reply_markup=kb
    )

# === Donate Info ===
@bot.message_handler(func=lambda m: m.text == "💳 Donate & Get Access")
def donate_info(msg):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(msg.chat.id,
        f"<b>Send your donation to:</b>\n\n"
        f"💳 MIR Card:\n<code>{MIR_CARD}</code>\n\n"
        f"🪙 USDT (TRC20):\n<code>{CRYPTO_ADDRESS}</code>\n\n"
        "After sending, click '✅ I Paid'. Access is approved manually.",
        parse_mode="HTML", reply_markup=kb
    )

# === Handle Payment Request ===
@bot.callback_query_handler(func=lambda call: call.data == "paid")
def handle_paid(call):
    uid = call.message.chat.id
    bot.send_message(uid, "🕓 Payment sent. Waiting for admin approval.")
    bot.send_message(ADMIN_ID,
        f"🧾 Payment request from @{call.from_user.username or 'no username'} (ID: {uid})",
        reply_markup=telebot.types.InlineKeyboardMarkup([
            [telebot.types.InlineKeyboardButton("✅ Grant", callback_data=f"grant_{uid}"),
             telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]
        ])
    )

# === Admin Grant/Reject ===
@bot.callback_query_handler(func=lambda c: c.data.startswith("grant_") or c.data.startswith("reject_"))
def handle_admin_decision(call):
    if call.from_user.id != ADMIN_ID:
        return
    uid = int(call.data.split("_")[1])
    if call.data.startswith("grant_"):
        cursor.execute("INSERT OR REPLACE INTO users (user_id, access) VALUES (?, 1)", (uid,))
        conn.commit()
        bot.send_message(uid, "✅ Access granted. You can now analyze matches.")
    else:
        bot.send_message(uid, "❌ Access denied. Please check your payment.")
    bot.send_message(call.message.chat.id, "✔️ Processed.")

# === Check Access for Analysis ===
@bot.message_handler(func=lambda m: m.text == "🔍 Analyze Match")
def check_access(msg):
    uid = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if row and row[0] == 1:
        bot.send_message(uid, "✅ Send the match details (teams, tournament, etc).")
    else:
        bot.send_message(uid, "❌ Access denied. Please donate first.")

# === Analyze Match (Groq AI) ===
@bot.message_handler(func=lambda m: True)
def analyze(msg):
    uid = msg.chat.id
    cursor.execute("SELECT access FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if not row or row[0] != 1:
        return
    bot.send_message(uid, "⚡ Analyzing match...")

    prompt = f"""
You are a football betting expert. Predict the following match using safe, high-probability betting tips.

Only suggest realistic outcomes:
- Over/Under goals
- Both Teams to Score
- Handicap
- Draw No Bet
- Double Chance

Don't invent crazy scorelines.

Reply in this format:

Match: [Teams]  
Tournament: [Name]  
Date: [Approximate Date]

—

Prediction:
• Bet: [Bet type]
• Odds: ~1.70–2.20
• Confidence: Low / Medium / High

—

Reasoning:
• Short fact 1
• Short fact 2
• Short fact 3

Match: {msg.text}
"""

    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content
        for chunk in range(0, len(result), 4000):
            bot.send_message(uid, result[chunk:chunk+4000])
    except Exception as e:
        bot.send_message(uid, f"❌ Error:\n{e}")

bot.polling()
