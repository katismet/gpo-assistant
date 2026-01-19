"""Быстрая проверка работы бота."""

import asyncio
from aiogram import Bot
from aiogram.types import BotCommand

async def check_bot():
    token = "BOT_TOKEN_REMOVED"
    bot = Bot(token=token)
    
    try:
        me = await bot.get_me()
        print(f"✅ Бот активен: @{me.username} ({me.first_name})")
        
        # Получаем список команд
        commands = await bot.get_my_commands()
        print(f"\n📋 Доступные команды:")
        for cmd in commands:
            print(f"  /{cmd.command} - {cmd.description}")
        
        print("\n✅ Бот готов к работе!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(check_bot())

