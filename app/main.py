"""Основной файл приложения."""

import asyncio
from contextlib import asynccontextmanager

from aiohttp import web
from loguru import logger

from app.config import get_settings
from app.db import init_db
from app.services.scheduler import scheduler_service
from app.telegram.bot import gpo_bot, dp
from app.handlers.menu import router as menu_router
from app.utils.logging import setup_logging

settings = get_settings()


@asynccontextmanager
async def lifespan():
    """Управление жизненным циклом приложения."""
    # Инициализация
    setup_logging()
    logger.info("Starting GPO Assistant")
    
    # Инициализация базы данных
    await init_db()
    logger.info("Database initialized")
    
    # Запуск планировщика
    await scheduler_service.start()
    logger.info("Scheduler started")
    
    yield
    
    # Очистка
    await scheduler_service.stop()
    logger.info("Scheduler stopped")
    
    await gpo_bot.stop()
    logger.info("Bot stopped")


async def create_app() -> web.Application:
    """Создание aiohttp приложения."""
    app = web.Application()
    
    # Управление жизненным циклом
    app.cleanup_ctx.append(lambda app: lifespan())
    
    # Роутеры уже подключены в app/telegram/bot.py
    # dp.include_router(menu_router)  # Убрано - уже подключено в bot.py
    
    # Настройка маршрутов
    if settings.debug:
        # В режиме отладки используем polling
        async def start_polling():
            """Запуск polling в фоновой задаче."""
            await dp.start_polling(gpo_bot, allowed_updates=["message", "callback_query"])
        asyncio.create_task(start_polling())
    else:
        # В продакшене используем webhook
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        SimpleRequestHandler(dispatcher=dp, bot=gpo_bot).register(app, path="/webhook")
    
    # Добавляем маршруты для PDF
    app.router.add_get("/health", health_check)
    app.router.add_get("/", root_handler)
    
    return app


async def health_check(request: web.Request) -> web.Response:
    """Проверка здоровья приложения."""
    return web.json_response({
        "status": "healthy",
        "service": "gpo-assistant",
        "version": "0.1.0",
    })


async def root_handler(request: web.Request) -> web.Response:
    """Обработчик корневого маршрута."""
    return web.json_response({
        "message": "GPO Assistant API",
        "version": "0.1.0",
        "docs": "/docs",
    })


async def main():
    """Основная функция."""
    app = await create_app()
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, settings.host, settings.port)
    await site.start()
    
    logger.info(f"Application started on {settings.host}:{settings.port}")
    
    try:
        await asyncio.Future()  # Запуск навсегда
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
