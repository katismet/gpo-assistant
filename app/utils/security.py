"""Утилиты безопасности."""

import hashlib
import secrets
from typing import Optional

from loguru import logger


def generate_token(length: int = 32) -> str:
    """Генерация случайного токена."""
    return secrets.token_urlsafe(length)


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Хеширование пароля с солью."""
    if salt is None:
        salt = secrets.token_hex(16)
    
    # Используем PBKDF2 для хеширования
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,  # Количество итераций
    )
    
    return password_hash.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Проверка пароля."""
    try:
        computed_hash, _ = hash_password(password, salt)
        return secrets.compare_digest(computed_hash, password_hash)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def sanitize_filename(filename: str) -> str:
    """Очистка имени файла от опасных символов."""
    import re
    
    # Удаляем опасные символы
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Ограничиваем длину
    if len(sanitized) > 255:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        sanitized = name[:255-len(ext)-1] + ('.' + ext if ext else '')
    
    return sanitized


def validate_telegram_id(telegram_id: int) -> bool:
    """Проверка валидности Telegram ID."""
    return isinstance(telegram_id, int) and telegram_id > 0


def validate_bitrix_id(bitrix_id: int) -> bool:
    """Проверка валидности Bitrix ID."""
    return isinstance(bitrix_id, int) and bitrix_id > 0

