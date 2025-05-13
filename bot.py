import logging
from datetime import datetime, timedelta
import pytz
import asyncio
import json
import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler, ContextTypes, filters
)

TOKEN = "7558281182:AAHqX6h6oVpMgyIgs5ayZ0mxTv7Zw7BnSI8"

# === ФУНКЦИИ СОХРАНЕНИЯ/ЗАГРУЗКИ ===

def load_data():
    if os.path.exists("payments.json"):
        with open("payments.json", "r", encoding="utf-8") as f:
            loaded_payments = json.load(f)
            # Преобразуем timestamp обратно в datetime
            loaded_payments = [(uid, name, datetime.fromisoformat(ts), cid) for uid, name, ts, cid in loaded_payments]
    else:
        loaded_payments = []

    if os.path.exists("participants.json"):
        with open("participants.json", "r", encoding="utf-8") as f:
            raw_participants = json.load(f)
            loaded_participants = {int(k): tuple(v) for k, v in raw_participants.items()}
    else:
        loaded_participants = {}

    return loaded_payments, loaded_participants

def save_data():
    # Сохраняем payments с преобразованием datetime → строка
    with open("payments.json", "w", encoding="utf-8") as f:
        json.dump(
            [(uid, name, ts.isoformat(), cid) for uid, name, ts, cid in payments],
            f, ensure_ascii=False, indent=2
        )

    with open("participants.json", "w", encoding="utf-8") as f:
        json.dump(participants, f, ensure_ascii=False, indent=2)

# === ИНИЦИАЛИЗАЦИЯ ===

payments, participants = load_data()

logging.basicConfig(level=logging.INFO)

def now_moscow():
    return datetime.now(pytz.timezone("Europe/Moscow"))

def get_recent_payments(chat_id):
    cutoff = now_moscow() - timedelta(days=4)
    return [(uid, name) for (uid, name, ts, cid) in payments if ts > cutoff and cid == chat_id]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    # Сохраняем участника
    participants[user.id] = (
        user.full_name,
        f"@{user.username}" if user.username else user.full_name,
        chat_id
    )

    if "#оплата" in text.lower():
        name = text.replace("#оплата", "").strip()
        payments.append((user.id, name, now_moscow(), chat_id))
        logging.info(f"Записана оплата от {name} в чате {chat_id}")

    save_data()  # сохраняем и участников, и оплаты после каждого сообщения

async def friday_report(application):
    await asyncio.sleep(5)
    while True:
        now = now_moscow()
        if now.weekday() == 1 and now.hour == 21 and now.minute == 2:
            logging.info("Настало время пятничного отчёта...")
            chat_ids = {c for (_, _, _, c) in payments}
            for chat_id in chat_ids:
                paid = get_recent_payments(chat_id)
                paid_ids = {uid for uid, _ in paid}
                paid_names = [name for _, name in paid]

                unpaid_tags = []
                for uid, (fullname, tag, cid) in participants.items():
                    if cid == chat_id and uid not in paid_ids:
                        unpaid_tags.append(tag)

                text = f"🤖 Привет, это бот-модератор. Я почитал ваши сообщения и рад приветствовать участников супервизии в понедельник — {len(paid_names)} человек:\n"
                if paid_names:
                    text += "\n" + "\n".join(f"• {name}" for name in paid_names)
                else:
                    text += "\n• никто не оплатил 😨"

                text += "\n\nНапоминаю "
                if unpaid_tags:
                    text += ", ".join(unpaid_tags)
                    text += ", что мне придётся вас удалить из чата, если вы не скинете подтверждение оплаты с #оплата до конца завтрашнего дня :/"
                else:
                    text += "всем, что вы молодцы, все оплатили! 🎉"

                try:
                    await application.bot.send_message(chat_id=chat_id, text=text)
                except Exception as e:
                    logging.warning(f"Ошибка отправки в чат {chat_id}: {e}")
            await asyncio.sleep(65)
        else:
            await asyncio.sleep(20)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

async def main():
    asyncio.create_task(friday_report(app))
    print("Бот запущен и ждёт пятницы...")
    await app.run_polling()

import nest_asyncio
nest_asyncio.apply()
asyncio.run(main())
