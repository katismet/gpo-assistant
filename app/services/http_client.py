# app/services/http_client.py

import asyncio
import httpx
import os
import random
from dotenv import load_dotenv

# Загружаем переменные окружения из .env ПЕРЕД использованием
load_dotenv()

# Получаем BITRIX_WEBHOOK_URL после загрузки .env
BITRIX = os.getenv("BITRIX_WEBHOOK_URL")


class BitrixError(RuntimeError):
    """Ошибка при работе с Bitrix24 API."""
    pass


def get_bitrix_url() -> str:
    """Получить BITRIX_WEBHOOK_URL с динамической загрузкой."""
    # Перезагружаем .env на случай, если он изменился
    load_dotenv()
    url = os.getenv("BITRIX_WEBHOOK_URL")
    if not url:
        raise BitrixError("BITRIX_WEBHOOK_URL not set in .env file")
    return url


async def bx(method: str, payload: dict, *, retries: int = 3) -> dict:
    """
    Надёжный клиент для Bitrix24 REST API с автоматическими ретраями.
    
    Args:
        method: Метод Bitrix24 API (например, "crm.item.add")
        payload: Параметры запроса
        retries: Количество попыток при ошибках
        
    Returns:
        Результат из data["result"]
        
    Raises:
        BitrixError: При ошибках API или после исчерпания попыток
    """
    # Получаем URL динамически при каждом вызове
    bitrix_url = get_bitrix_url()
    
    url = f"{bitrix_url}/{method}"
    
    backoff = 0.6
    async with httpx.AsyncClient(timeout=40) as client:
        for attempt in range(1, retries + 1):
            r = await client.post(url, json=payload)
            status = r.status_code
            data = {}
            try:
                data = r.json()
            except Exception:
                pass
            
            # успех
            if status == 200 and "error" not in data:
                return data.get("result", {})
            
            # временные: 429/502/503/504 или «поспешные» 400 после свежего создания
            transient = status in (429, 502, 503, 504) or (status == 400 and attempt == 1)
            if attempt < retries and transient:
                await asyncio.sleep(backoff + random.uniform(0, 0.4))
                backoff *= 1.7
                continue
            
            # финальная ошибка
            err = data.get("error_description") or data.get("error") or f"HTTP {status}"
            raise BitrixError(f"{method}: {err}")


