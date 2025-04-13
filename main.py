import telebot
import sqlite3
from flask import Flask
from threading import Thread
from groq import Groq
import os
from datetime import datetime, timedelta

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("7241781324:AAFOgQ8QgTiCOC1efBUoPeu7UzM7Yu2UXvo")
GROQ_API_KEY = os.getenv("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")
ADMIN_ID = int(os.getenv("1023932092"))
MIR_CARD = os.getenv("2200701901154812")
CRYPTO_ADDRESS = os.getenv("TH92J3hUqbAgpXiC5NtkxFHGe2vB9yUonH")

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
    access_until TEXT
)
""")
conn.commit()

# === /start ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Анализ матча", "💳 Купить доступ")
    bot.send_message(message.chat.id,
        "<b>🤖 Albetting — ИИ-анализ футбольных матчей</b>\n\n"
        "<b>Тарифы:</b>\n"
        "• Разовый: 5₽\n"
        "• 7 дней: 25₽\n"
        "• 30 дней: 65₽\n"
        "• Годовой: 390₽",
        parse_mode="HTML",
        reply_markup=markup
    )

# === Donate Info ===
@bot.message_handler(func=lambda msg: msg.text == "💳 Купить доступ")
def donate_info(msg):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ Я оплатил", callback_data="paid"))
    bot.send_message(msg.chat.id,
        f"Переведите оплату на одну из платформ:\n\n"
        f"💳 MIR: <code>{MIR_CARD}</code>\n"
        f"🪙 USDT (TRC20): <code>{CRYPTO_ADDRESS}</code>\n\n"
        f"После оплаты нажмите кнопку ниже:",
        parse_mode="HTML",
        reply_markup=markup
    )

# === User clicked "Paid" ===
@bot.callback_query_handler(func=lambda call: call.data == "paid")
def confirm_payment(call):
    uid = call.message.chat.id
    bot.send_message(uid, "Ожидайте подтверждение от администратора.")
    bot.send_message(ADMIN_ID,
        f"🧾 Запрос оплаты от @{call.from_user.username or 'без ника'} ({uid})",
        reply_markup=telebot.types.InlineKeyboardMarkup([
            [telebot.types.InlineKeyboardButton("Разовый", callback_data=f"access_{uid}_1")],
            [telebot.types.InlineKeyboardButton("7 дней", callback_data=f"access_{uid}_7")],
            [telebot.types.InlineKeyboardButton("30 дней", callback_data=f"access_{uid}_30")],
            [telebot.types.InlineKeyboardButton("1 год", callback_data=f"access_{uid}_365")],
            [telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data=f"deny_{uid}")]
        ])
    )

# === Admin confirms ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("access_") or call.data.startswith("deny_"))
def handle_access(call):
    if call.from_user.id != ADMIN_ID:
        return

    data = call.data.split("_")
    uid = int(data[1])

    if call.data.startswith("deny_"):
        bot.send_message(uid, "❌ Доступ отклонён.")
        bot.send_message(call.message.chat.id, "Отказ подтверждён.")
        return

    days = int(data[2])
    access_until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    cursor.execute("INSERT OR REPLACE INTO users (user_id, access_until) VALUES (?, ?)", (uid, access_until))
    conn.commit()

    bot.send_message(uid, f"✅ Доступ выдан до {access_until}")
    bot.send_message(call.message.chat.id, f"Выдал доступ до {access_until}")

# === Match Input ===
@bot.message_handler(func=lambda msg: msg.text == "🔍 Анализ матча")
def prompt_analysis(msg):
    cursor.execute("SELECT access_until FROM users WHERE user_id=?", (msg.chat.id,))
    result = cursor.fetchone()

    if not result or datetime.now() > datetime.strptime(result[0], "%Y-%m-%d"):
        bot.send_message(msg.chat.id, "⛔ Доступ отсутствует или истёк. Нажмите 💳 Купить доступ.")
        return

    bot.send_message(msg.chat.id, "Введите матч (например: Реал - Арсенал, первый матч 0:3):")

# === Match Analyzer ===
@bot.message_handler(func=lambda msg: True)
def analyze(msg):
    cursor.execute("SELECT access_until FROM users WHERE user_id=?", (msg.chat.id,))
    result = cursor.fetchone()

    if not result or datetime.now() > datetime.strptime(result[0], "%Y-%m-%d"):
        return

    bot.send_message(msg.chat.id, "⏳ Анализируем...")

    prompt = f"""
Ты — профессиональный футбольный аналитик. Ответ дай строго на русском и по следующему шаблону:

Матч: [Название]
Стадия: [1/8 финала и т.д.]
Место: [город, стадион]

—

Ключевые факторы:
• [факт 1]
• [факт 2]
• [факт 3]

—

Прогноз:
• Ставка: [например, Победа Реала]
• Счёт: [например, 2:1]
• Уверенность: [низкая/средняя/высокая]

—

Альтернативный экспресс (коэффициент 3+):
• [ставка 1]
• [ставка 2]
• [ставка 3]

Теперь проанализируй матч: {msg.text}
"""

    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response.choices[0].message.content
        for chunk in range(0, len(answer), 4000):
            bot.send_message(msg.chat.id, answer[chunk:chunk+4000])
    except Exception as e:
        bot.send_message(msg.chat.id, f"Ошибка:\n{e}")

bot.polling()
