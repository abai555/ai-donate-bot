import telebot
import sqlite3
from flask import Flask
from threading import Thread
from groq import Groq
import os
from datetime import datetime, timedelta

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
    expiry TIMESTAMP
)
""")
conn.commit()

def has_active_subscription(user_id):
    cursor.execute("SELECT expiry FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        return datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S") > datetime.now()
    return False

def add_subscription(user_id, days):
    expiry_date = datetime.now() + timedelta(days=days)
    cursor.execute("REPLACE INTO users (user_id, expiry) VALUES (?, ?)",
                   (user_id, expiry_date.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def get_subscription_status(user_id):
    cursor.execute("SELECT expiry FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        expiry = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        remaining = (expiry - datetime.now()).days
        return f"â Subscription active.\nExpires in {remaining} day(s)."
    return "â No active subscription."

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("ð Analyze Match", "ð³ Donate & Get Access", "ð Subscription Status")
    bot.send_message(message.chat.id,
                     "Welcome! Choose an option below:",
                     reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "ð Subscription Status")
def check_status(message):
    status = get_subscription_status(message.from_user.id)
    bot.send_message(message.chat.id, status)

@bot.message_handler(func=lambda m: m.text == "ð³ Donate & Get Access")
def donate(message):
    bot.send_message(message.chat.id, f"""To activate access, make a manual payment:
ð³ MIR: `{MIR_CARD}`
ð° Crypto: `{CRYPTO_ADDRESS}`

After payment, send a message: `Paid {message.from_user.id} 7` (or 30, 365).""", parse_mode="Markdown")

@bot.message_handler(regexp=r'^Paid (\d+) (\d+)$')
def confirm_payment(message):
    if message.from_user.id == ADMIN_ID:
        try:
            parts = message.text.split()
            user_id = int(parts[1])
            days = int(parts[2])
            add_subscription(user_id, days)
            bot.send_message(user_id, "â Access activated!")
            bot.send_message(message.chat.id, "User activated.")
        except:
            bot.send_message(message.chat.id, "Error processing the command.")

@bot.message_handler(func=lambda m: m.text == "ð Analyze Match")
def analyze_prompt(message):
    if not has_active_subscription(message.from_user.id):
        bot.send_message(message.chat.id, "â Access denied.")
        return
    msg = bot.send_message(message.chat.id, "Send the match info:")
    bot.register_next_step_handler(msg, analyze_match)

def analyze_match(message):
    user_input = message.text.strip()
    prompt = f"""
Ð¢Ñ ÑÐ¿Ð¾ÑÑÐ¸Ð²Ð½ÑÐ¹ Ð°Ð½Ð°Ð»Ð¸ÑÐ¸Ðº. ÐÑÐ¾Ð°Ð½Ð°Ð»Ð¸Ð·Ð¸ÑÑÐ¹ Ð¼Ð°ÑÑ Ð½Ð° Ð¾ÑÐ½Ð¾Ð²Ðµ Ð¾Ð¿Ð¸ÑÐ°Ð½Ð¸Ñ Ð¸ Ð²ÑÐ´Ð°Ð¹ ÐºÑÐ°ÑÐºÐ¸Ð¹ Ð¿ÑÐ¾Ð³Ð½Ð¾Ð· Ð² ÑÐ¾ÑÐ¼Ð°ÑÐµ:

â
Match: [Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ ÑÑÑÐ½Ð¸ÑÐ° Ð¸ Ð¼Ð°ÑÑ]
â
ÐÑÐ¾Ð³Ð½Ð¾Ð·:
â¢ ÐÑÑÐ¾Ð´: [Ð1/Ð2/Ð½Ð¸ÑÑÑ]
â¢ Ð¢Ð¾ÑÐ°Ð» Ð¼Ð°ÑÑÐ°: [Ð±Ð¾Ð»ÑÑÐµ/Ð¼ÐµÐ½ÑÑÐµ X.5]
â¢ Ð¢Ð¾ÑÐ°Ð» Ð¿ÐµÑÐ²Ð¾Ð³Ð¾/Ð²ÑÐ¾ÑÐ¾Ð³Ð¾ ÑÐ°Ð¹Ð¼Ð°: [Ð±Ð¾Ð»ÑÑÐµ/Ð¼ÐµÐ½ÑÑÐµ X.5]
â¢ Ð¢Ð¾ÑÐ°Ð» Ð¾Ð´Ð½Ð¾Ð¹ Ð¸Ð· ÐºÐ¾Ð¼Ð°Ð½Ð´: [Ð±Ð¾Ð»ÑÑÐµ/Ð¼ÐµÐ½ÑÑÐµ X.5]
â¢ ÐÐµÑÐ´Ð¸ÐºÑ: [ÑÐµÐ·ÑÐ»ÑÑÐ°Ñ]

ÐÐ¾Ñ Ð¾Ð¿Ð¸ÑÐ°Ð½Ð¸Ðµ Ð¼Ð°ÑÑÐ°: {user_input}
    """
    try:
        response = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=1.0
        )
        answer = response.choices[0].message.content
        bot.send_message(message.chat.id, answer)
    except Exception as e:
        bot.send_message(message.chat.id, "Error occurred during analysis.")
        print(e)

bot.polling()
