import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta, UTC
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.client.default import DefaultBotProperties

# Логи
logging.basicConfig(level=logging.INFO)

# Токен из env
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logging.error("BOT_TOKEN не задан!")
    exit(1)

# БД файл
DB_PATH = 'users.db'

# Инициализация БД
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            chat_id INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()  # Запуск при старте

def add_user(user_id, username, first_name, chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, chat_id)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, chat_id))
    conn.commit()
    conn.close()

def get_users(chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name FROM users WHERE chat_id = ?', (chat_id,))
    users = cursor.fetchall()
    conn.close()
    return users

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# Фильтр свежести
def is_recent_message(message_date):
    now = datetime.now(UTC)
    return (now - message_date) < timedelta(seconds=300)

# Глобальный error handler
@dp.errors()
async def errors_handler(update, exception):
    if isinstance(exception, TelegramForbiddenError):
        logging.warning(f"Заблокирован юзером {update.from_user.id if update.from_user else 'unknown'}")
        return
    logging.error(f"Неожиданная ошибка: {exception}")

# Хэндлер для сбора юзеров (на любое сообщение в группе)
@dp.message(lambda message: message.chat.type in ['group', 'supergroup'])
async def collect_users(message: types.Message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name or user.full_name, message.chat.id)

@dp.message(Command('status'))
async def status(message: types.Message):
    if not is_recent_message(message.date):
        logging.info(f"Игнор старой /status от {message.from_user.id}")
        return
    try:
        await message.reply("🤖 Бот онлайн! Версия: 1.4 (пинг всех из БД)")
    except TelegramForbiddenError:
        logging.warning(f"Не могу ответить {message.from_user.id} — заблокирован")

@dp.message(Command('ping'))
async def ping_all_from_db(message: types.Message):
    if not is_recent_message(message.date):
        logging.info(f"Игнор старой /ping от {message.from_user.id}")
        return
    
    chat = message.chat
    if chat.type not in ['group', 'supergroup']:
        try:
            await message.reply("Работает только в группах!")
        except TelegramForbiddenError:
            logging.warning(f"Не могу ответить в {chat.id}")
        return
    
    # Проверяем права бота
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat.id, me.id)
        if member.status not in ['administrator', 'creator']:
            await message.reply("Я должен быть админом!")
            return
    except Exception:
        await message.reply("Ошибка проверки прав.")
        return
    
    # Получаем юзеров из БД
    try:
        users = get_users(chat.id)
        if not users:
            await message.reply("Нет данных о пользователях. Пусть напишут что-нибудь!")
            return
        
        # Батчи по 10, пауза 3 сек
        batch_size = 10
        pinged_count = 0
        for i in range(0, len(users), batch_size):
            batch_users = users[i:i + batch_size]
            mentions = []
            for user_id, username, first_name in batch_users:
                if username:
                    mention = f'<a href="tg://user?id={user_id}">@{(username)}</a>'
                else:
                    mention = f'<a href="tg://user?id={user_id}">{first_name or "User"}</a>'
                mentions.append(mention)
            
            text = "Пинг всех! " + " ".join(mentions)
            try:
                await bot.send_message(
                    chat.id,
                    text,
                    disable_web_page_preview=True
                )
                pinged_count += len(batch_users)
                await asyncio.sleep(3)  # Антифлуд
            except TelegramBadRequest as e:
                if "Too Many Requests" in str(e):
                    await message.reply("Флуд-лимит! Подожди минуту.")
                    return
                logging.warning(f"Ошибка батча: {e}")
                continue
            except TelegramForbiddenError:
                logging.warning(f"Заблокирован в {chat.id}")
                continue
            except Exception as e:
                await message.reply(f"Ошибка отправки: {e}")
                break
        
        await message.reply(f"Пинг завершён! Упомянуто {pinged_count} пользователей из БД.")
    
    except Exception as e:
        await message.reply(f"Ошибка чтения БД: {e}")

# Запуск
async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("Webhook очищен")
    except:
        pass
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
