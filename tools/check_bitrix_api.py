"""Проверка доступных методов Bitrix24 API на текущем тарифе."""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

BITRIX = os.getenv("BITRIX_WEBHOOK_URL")
if not BITRIX:
    print("❌ BITRIX_WEBHOOK_URL не задан в .env")
    exit(1)

async def test_method(method: str, params: dict = None):
    """Тестирует доступность метода API."""
    url = f"{BITRIX}/{method}"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(url, json=params or {})
            if r.status_code == 200:
                data = r.json()
                if "error" in data:
                    return False, data.get("error_description", data["error"])
                return True, "OK"
            else:
                return False, f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            return False, str(e)

async def main():
    print(f"🔍 Проверка доступности методов Bitrix24 API\n")
    print(f"Webhook: {BITRIX}\n")
    
    tests = [
        ("crm.type.list", {}, "Получение списка типов"),
        ("crm.item.fields", {"entityTypeId": 1056}, "Получение полей (Ресурс)"),
        ("crm.item.list", {"entityTypeId": 1056, "start": 0, "limit": 1}, "Чтение элементов (Ресурс)"),
        ("crm.item.add", {"entityTypeId": 1056, "fields": {"TITLE": "Test"}}, "Создание элементов (Ресурс)"),
        ("crm.item.userfield.list", {"entityTypeId": 1056}, "Получение пользовательских полей"),
    ]
    
    for method, params, desc in tests:
        ok, msg = await test_method(method, params)
        status = "✅" if ok else "❌"
        print(f"{status} {desc}")
        print(f"   Метод: {method}")
        if not ok:
            print(f"   Ошибка: {msg}")
        print()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())










