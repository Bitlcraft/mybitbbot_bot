import asyncio
import logging
import os
from datetime import datetime, timedelta, UTC  # Добавь UTC для фикса warning
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

# Логи
logging.basicConfig(level=logging.INFO)

# Токен из env
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logging.error("BOT_TOKEN не задан!")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Фильтр свежести (5 мин) — ФИКС: message.date уже datetime, не timestamp
def is_recent_message(message_date):
    now = datetime.now(UTC)  # Фикс deprecation
    # message_time = datetime.fromtimestamp(message_date)  # УБРАЛ: уже datetime!
    return (now - message_date) < timedelta(seconds=300)

@dp.message(Command('status'))
async def status(message: types.Message):
    if not is_recent_message(message.date):
        logging.info(f"Игнор старой /status от {message.from_user.id}")
        return
    await message.reply("🤖 Бот онлайн! Версия: 1.2 (фикс даты + антиконфликт)")

@dp.message(Command('ping'))
async def ping_admins(message: types.Message):
    if not is_recent_message(message.date):
        logging.info(f"Игнор старой /ping от {message.from_user.id}")
        return
    
    chat = message.chat
    if chat.type not in ['group', 'supergroup']:
        await message.reply("Работает только в группах!")
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
    
    # Получаем админов
    try:
        admins = await bot.get_chat_administrators(chat.id)
        if not admins:
            await message.reply("Админов не найдено.")
            return
        
        # Батчи по 10, пауза 3 сек
        batch_size = 10
        for i in range(0, len(admins), batch_size):
            batch_admins = admins[i:i + batch_size]
            mentions = []
            for admin in batch_admins:
                user = admin.user
                if user.username:
                    mention = f'<a href="tg://user?id={user.id}">@{(user.username)}</a>'
                else:
                    mention = f'<a href="tg://user?id={user.id}">{user.first_name or "Admin"}</a>'
                mentions.append(mention)
            
            text = "Пинг админов! " + " ".join(mentions)
            try:
                await bot.send_message(
                    chat.id,
                    text,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
                await asyncio.sleep(3)  # Антифлуд
            except TelegramBadRequest as e:
                if "Too Many Requests" in str(e):
                    await message.reply("Флуд-лимит! Подожди минуту.")
                    return
                continue
            except TelegramForbiddenError:
                continue
            except Exception as e:
                await message.reply(f"Ошибка отправки: {e}")
                break
        
        await message.reply(f"Пинг админов завершён! Упомянуто {len(admins)}.")
    
    except Exception as e:
        await message.reply(f"Ошибка при получении админов: {e}")

# Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
