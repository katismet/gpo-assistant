"""Настройка логирования."""

import sys
from pathlib import Path

from loguru import logger

from app.config import get_settings

settings = get_settings()


def setup_logging() -> None:
    """Настройка логирования."""
    # Удаляем стандартный обработчик
    logger.remove()

    # Консольный вывод
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        colorize=True,
    )

    # Файловый вывод
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "app.log",
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="1 day",
        retention="30 days",
        compression="zip",
    )

    # Отдельный файл для ошибок
    logger.add(
        log_dir / "errors.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="1 week",
        retention="90 days",
        compression="zip",
    )

    logger.info("Logging configured successfully")
