"""Быстрая проверка подключения к боту."""
import asyncio
from aiogram import Bot
import os
from dotenv import load_dotenv

load_dotenv()

async def test():
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ BOT_TOKEN не найден в .env")
        return
    
    bot = Bot(token=token)
    try:
        me = await bot.get_me()
        print(f"✅ Бот подключен: @{me.username} (id={me.id})")
        print(f"   Имя: {me.first_name}")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test())

