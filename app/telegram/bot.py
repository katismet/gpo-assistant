from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
import logging, os

from .flow_plan import router as plan_router
from .flow_report import router as report_router
from .flow_lpa import router as lpa_router
from .flow_resources import router as resources_router
from .flow_timesheet import router as timesheet_router
from .flow_w6 import router as w6_router
from .router_root import router as root_router
from app.handlers.authz import router as authz_router
from app.handlers.debug import router as debug_router
from app.handlers.w6_handlers import router as w6_handlers_router
from app.handlers.debug_shift import router as debug_shift_router
from app.handlers.menu import router as menu_router
from app.handlers.insights_handler import router as insights_router
from app.config import get_settings

# Настройка логирования в файл и консоль
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Удаляем все существующие обработчики перед настройкой
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Создаем обработчики с правильной кодировкой
file_handler = logging.FileHandler('bot.log', encoding='utf-8', mode='a')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(log_format))

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter(log_format))

logging.basicConfig(
    level=logging.DEBUG,
    format=log_format,
    handlers=[file_handler, console_handler]
)
settings = get_settings()
gpo_bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Роутеры меню (первыми для перехвата /start)
dp.include_router(menu_router)  # Новое меню с клавиатурой (ролевое меню) - ПЕРВЫМ для /start

# Базовые обработчики
dp.include_router(authz_router)  # Авторизация и базовые команды (help, menu, bind_user, who)
dp.include_router(insights_router)  # AI-инсайты для владельца (/insights)

# Операционные роутеры (ВАЖНО: до root_router, чтобы перехватывать act:tab, act:resources и т.д.)
dp.include_router(plan_router)
dp.include_router(report_router)
dp.include_router(lpa_router)
dp.include_router(resources_router)
dp.include_router(timesheet_router)  # ДО root_router, чтобы перехватывать act:tab
dp.include_router(w6_router)

# Команды W6
dp.include_router(w6_handlers_router)  # Команды W6 (daily_report, status, subscribe_alerts)

# Базовые обработчики (последними, чтобы не перехватывать специфичные команды)
dp.include_router(root_router)  # Базовые обработчики (diag, last, resource)

# Отладочные роутеры (только в режиме DEBUG)
if settings.debug:
    dp.include_router(debug_router)
    dp.include_router(debug_shift_router)
    logging.getLogger("gpo.bot").info("Debug routers enabled (DEBUG mode)")
else:
    logging.getLogger("gpo.bot").info("Debug routers disabled (production mode)")

if __name__ == "__main__":
    import asyncio
    from app.scheduler import setup_scheduler
    
    # Функция отправки для планировщика
    async def _bot_send(chat_id: int, text: str):
        """Функция для отправки сообщений через бота."""
        await gpo_bot.send_message(chat_id, text)
    
    async def main():
        log = logging.getLogger("gpo.bot")
        log.info("=" * 50)
        log.info("Запуск бота...")
        log.info(f"Bot ID: {gpo_bot.id}")
        log.info(f"Routers count: {len(dp.sub_routers)}")
        
        # Проверка конфигурации
        import os
        from dotenv import load_dotenv
        load_dotenv()
        bitrix_webhook = os.getenv("BITRIX_WEBHOOK_URL")
        if bitrix_webhook:
            log.info(f"BITRIX_WEBHOOK_URL: {bitrix_webhook[:50]}...")
        else:
            log.warning("BITRIX_WEBHOOK_URL не установлен в .env")
        
        # Настраиваем планировщик (запускается автоматически при setup_scheduler)
        scheduler = setup_scheduler(_bot_send)
        log.info("Планировщик настроен")
        
        try:
            # Проверяем подключение к Telegram перед запуском polling
            try:
                bot_info = await gpo_bot.get_me()
                log.info(f"✅ Подключение к Telegram успешно: @{bot_info.username} (ID: {bot_info.id})")
            except Exception as e:
                log.error(f"❌ Ошибка подключения к Telegram API: {e}", exc_info=True)
                raise
            
            log.info("Начало polling...")
            log.info("Ожидание обновлений от Telegram...")
            # Запускаем бота
            await dp.start_polling(gpo_bot, allowed_updates=["message", "callback_query"])
        except KeyboardInterrupt:
            log.info("Получен сигнал остановки (Ctrl+C)")
        except Exception as e:
            log.error(f"❌ Критическая ошибка при запуске бота: {e}", exc_info=True)
            raise
        finally:
            # Останавливаем планировщик при выходе
            log.info("Остановка планировщика...")
            scheduler.shutdown()
    
    # Альтернативный вариант с runner (aiogram 3.x):
    # from aiogram import Bot, Dispatcher
    # from aiogram.client.default import DefaultBotProperties
    # from aiogram.enums import ParseMode
    # from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    # from aiohttp import web
    # 
    # async def on_startup(bot: Bot):
    #     scheduler = setup_scheduler(_bot_send)
    #     # scheduler будет работать в фоне
    # 
    # runner = dp.start_polling(gpo_bot, on_startup=on_startup)
    # asyncio.run(runner)
    
    asyncio.run(main())
