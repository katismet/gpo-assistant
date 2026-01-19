"""Скрипт для запуска бота с диагностикой."""
import asyncio
import sys
import logging
from app.telegram.bot import gpo_bot, dp
from app.scheduler import setup_scheduler

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8', mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
)

log = logging.getLogger("gpo.bot")

async def _bot_send(chat_id: int, text: str):
    """Функция для отправки сообщений через бота."""
    await gpo_bot.send_message(chat_id, text)

async def main():
    log.info("=" * 60)
    log.info("ЗАПУСК БОТА С ДИАГНОСТИКОЙ")
    log.info("=" * 60)
    
    try:
        # Проверка бота
        log.info("Проверка подключения к Telegram...")
        bot_info = await gpo_bot.get_me()
        log.info(f"✅ Бот подключен: @{bot_info.username} (ID: {bot_info.id})")
        print(f"✅ Бот подключен: @{bot_info.username} (ID: {bot_info.id})")
        
        # Проверка роутеров
        log.info(f"✅ Роутеров подключено: {len(dp.sub_routers)}")
        print(f"✅ Роутеров подключено: {len(dp.sub_routers)}")
        
        # Проверка обработчика /start
        start_handlers = []
        for router in dp.sub_routers:
            if hasattr(router, 'message'):
                for handler in router.message.handlers:
                    if 'start' in str(handler.callback).lower() or 'CommandStart' in str(handler.filters):
                        start_handlers.append(handler)
        
        log.info(f"✅ Найдено обработчиков /start: {len(start_handlers)}")
        print(f"✅ Найдено обработчиков /start: {len(start_handlers)}")
        
        # Настройка планировщика
        log.info("Настройка планировщика...")
        scheduler = setup_scheduler(_bot_send)
        log.info("✅ Планировщик настроен")
        
        # Запуск polling
        log.info("=" * 60)
        log.info("НАЧАЛО POLLING - БОТ РАБОТАЕТ")
        log.info("=" * 60)
        print("=" * 60)
        print("БОТ ЗАПУЩЕН И ОЖИДАЕТ КОМАНДЫ")
        print("Отправьте /start в Telegram боту")
        print("=" * 60)
        
        await dp.start_polling(
            gpo_bot, 
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True  # Игнорируем старые обновления
        )
        
    except KeyboardInterrupt:
        log.info("Получен сигнал остановки (Ctrl+C)")
        print("\nОстановка бота...")
    except Exception as e:
        log.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        log.info("Остановка планировщика...")
        try:
            scheduler.shutdown()
        except:
            pass
        log.info("Бот остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)







