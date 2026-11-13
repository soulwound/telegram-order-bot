
import os
import sqlite3
import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.error import TelegramError

from config import BOT_TOKEN, ADMIN_ID


# -------------------------
# НАСТРОЙКИ
# -------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

DB_PATH = "database/requests.db"

NAME, CONTACT, DESCRIPTION, CONFIRM = range(4)

SERVICES = {
    "telegram": "Разработка Telegram-бота",
    "python": "Автоматизация Python",
    "other": "Другая задача"
}


# -------------------------
# БАЗА ДАННЫХ
# -------------------------

def init_db():
    os.makedirs("database", exist_ok=True)

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                service TEXT NOT NULL,
                name TEXT NOT NULL,
                contact TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'Новая',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def save_request(user_id, username, service, name, contact, description):
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.execute("""
            INSERT INTO requests (
                user_id, username, service,
                name, contact, description
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            username,
            service,
            name,
            contact,
            description
        ))

        return cursor.lastrowid


# -------------------------
# ГЛАВНОЕ МЕНЮ
# -------------------------

def main_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "Разработка Telegram-бота",
                callback_data="telegram"
            )
        ],
        [
            InlineKeyboardButton(
                "Автоматизация Python",
                callback_data="python"
            )
        ],
        [
            InlineKeyboardButton(
                "Другая задача",
                callback_data="other"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Здравствуйте!\n\n"
        "Я бот для приёма заявок.\n"
        "Выберите интересующую услугу:",
        reply_markup=main_menu()
    )


# -------------------------
# ФОРМА ЗАЯВКИ
# -------------------------

async def choose_service(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    service = SERVICES.get(query.data)

    if not service:
        await query.message.reply_text("Неизвестная услуга.")
        return ConversationHandler.END

    context.user_data["service"] = service

    await query.message.reply_text(
        f"Вы выбрали: {service}\n\n"
        "Как вас зовут?"
    )

    return NAME


async def get_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    name = update.message.text.strip()

    if len(name) < 2 or len(name) > 60:
        await update.message.reply_text(
            "Введите имя длиной от 2 до 60 символов."
        )
        return NAME

    context.user_data["name"] = name

    await update.message.reply_text(
        "Укажите контакт для связи.\n\n"
        "Например: @username, номер телефона или email."
    )

    return CONTACT


async def get_contact(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    contact = update.message.text.strip()

    if len(contact) < 3 or len(contact) > 100:
        await update.message.reply_text(
            "Контакт должен содержать от 3 до 100 символов."
        )
        return CONTACT

    context.user_data["contact"] = contact

    await update.message.reply_text(
        "Опишите вашу задачу подробнее."
    )

    return DESCRIPTION


async def get_description(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    description = update.message.text.strip()

    if len(description) < 10 or len(description) > 1000:
        await update.message.reply_text(
            "Описание должно содержать от 10 до 1000 символов."
        )
        return DESCRIPTION

    context.user_data["description"] = description

    keyboard = [
        [
            InlineKeyboardButton(
                "Отправить заявку",
                callback_data="submit"
            )
        ],
        [
            InlineKeyboardButton(
                "Отмена",
                callback_data="cancel"
            )
        ]
    ]

    text = (
        "Проверьте вашу заявку:\n\n"
        f"Услуга: {context.user_data['service']}\n"
        f"Имя: {context.user_data['name']}\n"
        f"Контакт: {context.user_data['contact']}\n"
        f"Описание: {description}\n\n"
        "Всё верно?"
    )

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return CONFIRM


# -------------------------
# СОХРАНЕНИЕ ЗАЯВКИ
# -------------------------

async def submit_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    request_id = save_request(
        user_id=user.id,
        username=user.username or "",
        service=context.user_data["service"],
        name=context.user_data["name"],
        contact=context.user_data["contact"],
        description=context.user_data["description"]
    )

    await query.edit_message_text(
        f"Заявка №{request_id} успешно отправлена!\n\n"
        "Спасибо. С вами свяжутся по указанному контакту."
    )

    if ADMIN_ID:
        admin_message = (
            f"Новая заявка №{request_id}\n\n"
            f"Услуга: {context.user_data['service']}\n"
            f"Имя: {context.user_data['name']}\n"
            f"Контакт: {context.user_data['contact']}\n"
            f"Описание: {context.user_data['description']}\n\n"
            f"Telegram ID: {user.id}"
        )

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message
            )
        except TelegramError:
            logging.exception("Не удалось отправить уведомление админу")

    context.user_data.clear()

    return ConversationHandler.END


# -------------------------
# ОТМЕНА
# -------------------------

async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    context.user_data.clear()

    await update.effective_message.reply_text(
        "Заполнение заявки отменено.\n\n"
        "Чтобы начать заново, отправьте /start."
    )

    return ConversationHandler.END


async def cancel_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    await query.edit_message_text(
        "Заполнение заявки отменено.\n\n"
        "Чтобы начать заново, отправьте /start."
    )

    return ConversationHandler.END


# -------------------------
# АДМИНИСТРАТИВНАЯ ПАНЕЛЬ
# -------------------------

def get_requests():
    with sqlite3.connect(DB_PATH) as connection:
        return connection.execute("""
            SELECT id, service, name, status, created_at
            FROM requests
            ORDER BY id DESC
            LIMIT 10
        """).fetchall()


def get_request(request_id):
    with sqlite3.connect(DB_PATH) as connection:
        return connection.execute("""
            SELECT id, user_id, username, service,
                   name, contact, description, status, created_at
            FROM requests
            WHERE id = ?
        """, (request_id,)).fetchone()


def update_request_status(request_id, status):
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            UPDATE requests
            SET status = ?
            WHERE id = ?
        """, (status, request_id))


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Доступ запрещён.")
        return

    requests = get_requests()

    if not requests:
        await update.message.reply_text("Заявок пока нет.")
        return

    keyboard = []

    for request in requests:
        request_id, service, name, status, created_at = request

        keyboard.append([
            InlineKeyboardButton(
                f"#{request_id} | {name} | {status}",
                callback_data=f"view_{request_id}"
            )
        ])

    await update.message.reply_text(
        "Панель администратора\n\n"
        "Последние 10 заявок:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("Доступ запрещён.")
        return

    data = query.data

    if data.startswith("view_"):
        request_id = int(data.split("_")[1])
        request = get_request(request_id)

        if not request:
            await query.edit_message_text("Заявка не найдена.")
            return

        (
            rid, user_id, username, service,
            name, contact, description, status, created_at
        ) = request

        keyboard = [
            [
                InlineKeyboardButton(
                    "Новая",
                    callback_data=f"status_{rid}_new"
                ),
                InlineKeyboardButton(
                    "В работе",
                    callback_data=f"status_{rid}_work"
                )
            ],
            [
                InlineKeyboardButton(
                    "Завершена",
                    callback_data=f"status_{rid}_done"
                )
            ],
            [
                InlineKeyboardButton(
                    "Назад",
                    callback_data="admin_list"
                )
            ]
        ]

        text = (
            f"Заявка №{rid}\n\n"
            f"Услуга: {service}\n"
            f"Имя: {name}\n"
            f"Контакт: {contact}\n"
            f"Описание: {description}\n\n"
            f"Статус: {status}\n"
            f"Дата: {created_at}\n"
            f"Telegram ID: {user_id}\n"
            f"Username: @{username if username else 'не указан'}"
        )

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("status_"):
        _, request_id, status_code = data.split("_")

        statuses = {
            "new": "Новая",
            "work": "В работе",
            "done": "Завершена"
        }

        status = statuses.get(status_code)

        if status:
            update_request_status(int(request_id), status)

            await query.edit_message_text(
                "Статус обновлён.\n\n" + ...
            )

            request = get_request(int(request_id))

            if request:
                await query.edit_message_text(
                    f"Заявка №{request[0]}\n\n"
                    f"Имя: {request[4]}\n"
                    f"Услуга: {request[3]}\n"
                    f"Контакт: {request[5]}\n"
                    f"Описание: {request[6]}\n\n"
                    f"Статус: {request[7]}",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                "Новая",
                                callback_data=f"status_{request_id}_new"
                            ),
                            InlineKeyboardButton(
                                "В работе",
                                callback_data=f"status_{request_id}_work"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "Завершена",
                                callback_data=f"status_{request_id}_done"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "Назад",
                                callback_data="admin_list"
                            )
                        ]
                    ])
                )

    elif data == "admin_list":
        requests = get_requests()

        if not requests:
            await query.edit_message_text("Заявок пока нет.")
            return

        keyboard = []

        for request in requests:
            rid, service, name, status, created_at = request

            keyboard.append([
                InlineKeyboardButton(
                    f"#{rid} | {name} | {status}",
                    callback_data=f"view_{rid}"
                )
            ])

        await query.edit_message_text(
            "Панель администратора\n\n"
            "Последние 10 заявок:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# -------------------------
# ЗАПУСК
# -------------------------

def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                choose_service,
                pattern="^(telegram|python|other)$"
            )
        ],
        states={
            NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_name
                )
            ],
            CONTACT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_contact
                )
            ],
            DESCRIPTION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_description
                )
            ],
            CONFIRM: [
                CallbackQueryHandler(
                    submit_request,
                    pattern="^submit$"
                )
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(
                cancel_button,
                pattern="^cancel$"
            )
        ],
        allow_reentry=True
    )

    app.add_handler(conversation)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(
        CallbackQueryHandler(
            admin_callback,
            pattern="^(view_|status_|admin_list)"
        )
    )

    print("Бот запущен!")

    app.run_polling()


if __name__ == "__main__":
    main()
