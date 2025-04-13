import telebot
import sqlite3
from flask import Flask
from threading import Thread
from groq import Groq
import os

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MIR_CARD = os.getenv("MIR_CARD")
CRYPTO_ADDRESS = os.getenv("CRYPTO_ADDRESS")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# === Flask uptime ===
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"
Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

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
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Analyze Match", "💳 Donate & Get Access")
    bot.send_message(message.chat.id,
        "<b>🤖 AI Match Analyzer</b>\n\n"
        "Analyze football matches using AI.\n\n"
        "<b>Payment Plans:</b>\n"
        "• One-time: $5\n"
        "• Weekly: $25\n"
        "• Monthly: $65\n"
        "• Yearly: $390",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Payment Info ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Donate & Get Access")
def donate_info(msg):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ I Paid", callback_data="paid"))
    bot.send_message(msg.chat.id,
        f"Send payment to:\n\n"
        f"💳 MIR Card: <code>{MIR_CARD}</code>\n"
        f"🪙 USDT TRC20: <code>{CRYPTO_ADDRESS}</code>\n\n"
        "After payment, press the button below:",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Payment Confirmation ===
@bot.callback_query_handler(func=lambda call: call.data == "paid")
def confirm_payment(call):
    uid = call.message.chat.id
    bot.send_message(uid, "Your payment request has been sent. Wait for manual approval.")
    bot.send_message(ADMIN_ID,
        f"🧾 Payment request from user @{call.from_user.username or 'NoUsername'} ({uid})",
        reply_markup=telebot.types.InlineKeyboardMarkup([
            [telebot.types.InlineKeyboardButton("✅ Grant", callback_data=f"grant_{uid}"),
             telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]
        ])
    )

# === Admin Actions ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("grant_") or call.data.startswith("reject_"))
def handle_admin_action(call):
    uid = int(call.data.split("_")[1])
    if call.from_user.id != ADMIN_ID:
        return
    if call.data.startswith("grant_"):
        cursor.execute("INSERT OR REPLACE INTO users (user_id, access) VALUES (?, 1)", (uid,))
        conn.commit()
        bot.send_message(uid, "✅ Access granted!")
        bot.send_message(call.message.chat.id, "Access approved.")
    else:
        bot.send_message(uid, "❌ Access denied.")
        bot.send_message(call.message.chat.id, "Access rejected.")

# === Analyze Match button ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Analyze Match")
def match_entry(msg):
    cursor.execute("SELECT access FROM users WHERE user_id=?", (msg.chat.id,))
    access = cursor.fetchone()
    if access and access[0] == 1:
        bot.send_message(msg.chat.id, "Send match info (e.g. Arsenal vs Real Madrid, context, etc):")
    else:
        bot.send_message(msg.chat.id, "❌ Access denied. Use 💳 Donate & Get Access first.")

# === Handle Match Text ===
@bot.message_handler(func=lambda msg: True)
def analyze(msg):
    cursor.execute("SELECT access FROM users WHERE user_id=?", (msg.chat.id,))
    access = cursor.fetchone()
    if not access or access[0] != 1:
        return

    bot.send_message(msg.chat.id, "⚡ Анализирую матч...")

    try:
        prompt = f"""
Ты — опытный каппер. Дай краткий прогноз строго в таком формате, на русском языке:

Match: [Название турнира — команды]  
Дополнительный контекст матча: [Например, "Ответный матч, первая игра 0:3 в пользу Арсенала"]  
Место: [Стадион, Город]

Прогноз:

• Основная ставка: [Например, Победа Реала / Обе забьют / Тотал больше 2.5]  
• Уверенность: [Низкая / Средняя / Высокая / Очень высокая]  
• Дополнительная Ставка: [Пример: Арсенал забьет / Более 2.5 голов / Реал не пропустит]

Контекст матча: {msg.text}
"""

        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )

        answer = response.choices[0].message.content

        for chunk in range(0, len(answer), 4000):
            bot.send_message(msg.chat.id, answer[chunk:chunk+4000])

    except Exception as e:
        bot.send_message(msg.chat.id, f"Произошла ошибка:\n{e}")
