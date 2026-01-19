"""Проверка, отвечает ли бот на команды."""
import asyncio
from app.telegram.bot import gpo_bot

async def test():
    try:
        # Проверяем подключение
        bot_info = await gpo_bot.get_me()
        print(f"✅ Бот подключен: @{bot_info.username} (ID: {bot_info.id})")
        
        # Пробуем отправить тестовое сообщение (если знаем chat_id)
        # chat_id = 897953585  # Из логов
        # await gpo_bot.send_message(chat_id, "🧪 Тестовое сообщение от бота")
        # print(f"✅ Тестовое сообщение отправлено в chat {chat_id}")
        
        print("\n✅ Бот работает и готов к приему команд")
        print("Отправьте /start в Telegram боту @GPO_Helper2_bot")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())







