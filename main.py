import telebot
import sqlite3
from flask import Flask
from threading import Thread
from groq import GroqClient
import os
from datetime import datetime, timedelta

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MIR_CARD = os.getenv("MIR_CARD")
CRYPTO_ADDRESS = os.getenv("CRYPTO_ADDRESS")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = GroqClient(api_key=GROQ_API_KEY)

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
    expires_at TEXT
)
""")
conn.commit()

# === Subscriptions ===
def has_access(user_id):
    cursor.execute("SELECT expires_at FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result:
        expires_at = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        return datetime.now() < expires_at
    return False

def grant_access(user_id, days):
    expires_at = datetime.now() + timedelta(days=days)
    cursor.execute("REPLACE INTO users (user_id, expires_at) VALUES (?, ?)", (user_id, expires_at.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

# === Commands ===
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Welcome! Use the buttons below.", reply_markup=main_menu())

@bot.message_handler(commands=['status'])
def status(message):
    cursor.execute("SELECT expires_at FROM users WHERE user_id=?", (message.chat.id,))
    result = cursor.fetchone()
    if result:
        expires = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        days = (expires - datetime.now()).days
        if days > 0:
            bot.send_message(message.chat.id, f"✅ Subscription active.\nExpires in {days} day(s).")
            return
    bot.send_message(message.chat.id, "❌ No active subscription.")

@bot.message_handler(func=lambda m: m.text == "📄 Donate & Get Access")
def donate(message):
    bot.send_message(message.chat.id, f"""
Send any amount to one of the following:

💳 MIR card: `{MIR_CARD}`
🪙 Crypto: `{CRYPTO_ADDRESS}`

Then send your payment proof to the admin for access.
""", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🔍 Analyze Match")
def analyze(message):
    if not has_access(message.chat.id):
        bot.send_message(message.chat.id, "❌ Access denied.\nPlease purchase a subscription.")
        return
    msg = bot.send_message(message.chat.id, "Send match details (e.g. Real Madrid vs Arsenal)")
    bot.register_next_step_handler(msg, get_prediction)

# === Groq AI Call ===
def get_prediction(message):
    prompt = f"""
You are a betting AI. Reply with a short prediction in this format:

Match: Лига чемпионов — {message.text}  
Ответный матч, первая игра закончилась 0:3 в пользу Арсенала.  
Матч пройдет на Сантьяго Бернабеу, Мадрид.

Прогноз:

• Основная ставка: Победа одной команды / Ничья  
• Уверенность: Низкая / Средняя / Высокая  
• Дополнительная Ставка: Тотал матча / Тотал 1-го или 2-го тайма / Тотал одной из команд
"""
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="mixtral-8x7b-32768"
    )
    bot.send_message(message.chat.id, response.choices[0].message.content.strip())

# === Buttons ===
def main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Analyze Match", "📄 Donate & Get Access")
    markup.row("📊 Subscription Status")
    return markup

bot.infinity_polling()
