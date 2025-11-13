import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError

# Включи логи для отладки
logging.basicConfig(level=logging.INFO)

# Твой токен
BOT_TOKEN = 'YOUR_BOT_TOKEN'

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command('status'))  # Новая команда: /status для проверки
async def status(message: types.Message):
    await message.reply("🤖 Бот онлайн и готов к работе! Версия: 1.0 (с пингом и статусом)")

@dp.message(Command('ping'))
async def ping_all(message: types.Message):
    chat = message.chat
    if chat.type not in ['group', 'supergroup']:
        await message.reply("Эта команда работает только в группах!")
        return
    
    # Проверяем, что бот — админ
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat.id, me.id)
        if member.status not in ['administrator', 'creator']:
            await message.reply("Я должен быть админом для пинга!")
            return
    except Exception:
        await message.reply("Ошибка: не могу проверить права.")
        return
    
    # Собираем список участников (с пагинацией, лимит 200 за раз)
    members = []
    offset = 0
    limit = 200  # Telegram лимит на get_chat_members
    
    while True:
        try:
            batch = await bot.get_chat_members(chat.id, offset=offset, limit=limit)
            if not batch:
                break
            members.extend([m for m in batch if not m.user.is_bot])  # Исключаем ботов
            offset += limit
        except Exception as e:
            await message.reply(f"Ошибка при получении участников: {e}")
            return
    
    if not members:
        await message.reply("В группе нет участников (или только боты).")
        return
    
    # Формируем сообщение с упоминаниями (чтобы не флудить, отправляем по 30 за раз)
    batch_size = 30
    for i in range(0, len(members), batch_size):
        batch_members = members[i:i + batch_size]
        mentions = []
        for member in batch_members:
            user = member.user
            # Упоминание через HTML: <a href="tg://user?id=ID">Name</a>
            if user.username:
                mention = f'<a href="tg://user?id={user.id}">@{(user.username)}</a>'
            else:
                mention = f'<a href="tg://user?id={user.id}">{user.first_name or "User"}</a>'
            mentions.append(mention)
        
        text = "Пинг! " + " ".join(mentions)
        try:
            await bot.send_message(
                chat.id,
                text,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            await asyncio.sleep(1)  # Пауза, чтобы не флудить (Telegram лимит ~20 сек/мин)
        except TelegramForbiddenError:
            # Если кто-то заблокировал бота, пропускаем
            continue
        except Exception as e:
            await message.reply(f"Ошибка при отправке: {e}")
            break
    
    await message.reply(f"Пинг завершён! Упомянуто {len(members)} участников.")

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
