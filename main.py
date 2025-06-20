import asyncio
import datetime
import logging
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CallbackQueryHandler,
)
import os

logging.basicConfig(
    filename="bot.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# Список групп
groups = [
    {
        "name": "Бачата, нач. группа",
        "days": ["Monday", "Friday"],
        "time": {"Monday": "10:00", "Friday": "09:00"},
        "chat_id": os.getenv("CHAT_ID_BACHATA"),
    },
    {
        "name": "Бачата прод. группа",
        "days": ["Monday", "Friday"],
        "time": {"Monday": "11:00", "Friday": "10:00"},
        "chat_id": os.getenv("CHAT_ID_BACHATA_ADV"),
    },
]

pending = {}
last_check_date = None

def decision_keyboard(group_name):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да", callback_data=f"yes|{group_name}")],
        [InlineKeyboardButton("❌ Нет, отмена", callback_data=f"no|{group_name}")],
        [InlineKeyboardButton("⏭ Нет, но я сама напишу в группу", callback_data=f"skip|{group_name}")],
    ])

async def ask_admin(app, group, class_time):
    print(f"[ask_admin] Спрашиваем про: {group['name']}, чат: {group['chat_id']}")
    print(f"[ask_admin] ADMIN_ID: {ADMIN_ID}")
    msg = await app.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"Завтра будет '{group['name']}' в {class_time}?",
        reply_markup=decision_keyboard(group['name'])
    )
    pending[msg.message_id] = group

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, group_name = query.data.split("|")
    group = next((g for g in groups if g["name"] == group_name), None)

    now_utc = datetime.datetime.utcnow()
    now = now_utc + datetime.timedelta(hours=7)
    next_day = now + datetime.timedelta(days=1)
    weekday = next_day.strftime("%A")
    class_time = group["time"][weekday]

    if action == "yes":
        await context.bot.send_poll(
            chat_id=group["chat_id"],
            question=f"Завтра бачата в {class_time}. Кто придёт?",
            options=["✅ Приду", "❌ Не приду"],
            is_anonymous=False,
        )
        await query.edit_message_text("Опрос отправлен ✅")

    elif action == "no":
        await context.bot.send_message(
            chat_id=group["chat_id"],
            text="Ребята, завтра занятия не будет!"
        )
        await query.edit_message_text("Отмена отправлена ❌")

    elif action == "skip":
        await query.edit_message_text("Хорошо, сообщение не отправлено 🚫")

async def scheduler(app):
    global last_check_date
    print("[scheduler] запустился")
    while True:
        try:
            now_utc = datetime.datetime.utcnow()
            now = now_utc + datetime.timedelta(hours=7)
            next_day = now + datetime.timedelta(days=1)
            weekday = next_day.strftime("%A")
            print(f"[scheduler] now = {now}, next_day = {next_day}, weekday = {weekday}")

            if now.hour == 18 and 50 <= now.minute <= 53:
                if last_check_date != now.date():
                    for group in groups:
                        if weekday in group["days"]:
                            class_time = group["time"][weekday]
                            await ask_admin(app, group, class_time)
                    last_check_date = now.date()
                    await asyncio.sleep(180)
                else:
                    print("[scheduler] Уже спрашивали сегодня")

            await asyncio.sleep(20)
        except Exception as e:
            logging.exception("Ошибка в scheduler")
            await asyncio.sleep(10)

async def handle_ping(request):
    return web.Response(text="I'm alive!")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    print(f"[webserver] Starting on port {port}")
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(handle_callback))

    loop = asyncio.get_event_loop()
    loop.create_task(scheduler(app))
    loop.create_task(start_webserver())

    app.run_polling()

if __name__ == "__main__":
    main()
