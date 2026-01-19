"""Проверка соединения с Bitrix24: crm.item.add и crm.item.update"""

import os
import asyncio
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BITRIX = os.getenv("BITRIX_WEBHOOK_URL")
ENTITY_RESOURCE = int(os.getenv("ENTITY_RESOURCE", "0"))
ENTITY_SHIFT = int(os.getenv("ENTITY_SHIFT", "0"))

if not BITRIX or not ENTITY_RESOURCE or not ENTITY_SHIFT:
    print("❌ Не заданы BITRIX_WEBHOOK_URL, ENTITY_RESOURCE или ENTITY_SHIFT")
    exit(1)


async def bx(method: str, payload=None):
    """Вызов Bitrix REST API."""
    url = f"{BITRIX}/{method}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload or {})
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"{method}: {data.get('error_description', data['error'])}")
        return data.get("result")


async def test_add():
    """Тест создания элемента."""
    print("🧪 Тест crm.item.add (Ресурс)...")
    try:
        result = await bx("crm.item.add", {
            "entityTypeId": ENTITY_RESOURCE,
            "fields": {
                "TITLE": f"Тест создания {datetime.now().strftime('%H:%M:%S')}",
            }
        })
        item_id = result.get("item", {}).get("id") if isinstance(result, dict) else result
        print(f"✅ crm.item.add успешно: item.id = {item_id}")
        return item_id
    except Exception as e:
        print(f"❌ crm.item.add ошибка: {e}")
        return None


async def test_update(item_id: int):
    """Тест обновления элемента."""
    if not item_id:
        print("⚠ Пропуск crm.item.update (нет item_id)")
        return False
    
    print(f"🧪 Тест crm.item.update (item.id = {item_id})...")
    try:
        result = await bx("crm.item.update", {
            "entityTypeId": ENTITY_RESOURCE,
            "id": item_id,
            "fields": {
                "TITLE": f"Обновлено {datetime.now().strftime('%H:%M:%S')}",
            }
        })
        print(f"✅ crm.item.update успешно")
        return True
    except Exception as e:
        print(f"❌ crm.item.update ошибка: {e}")
        return False


async def test_get(item_id: int):
    """Тест получения элемента."""
    if not item_id:
        return None
    
    print(f"🧪 Тест crm.item.get (item.id = {item_id})...")
    try:
        result = await bx("crm.item.get", {
            "entityTypeId": ENTITY_RESOURCE,
            "id": item_id,
        })
        title = result.get("item", {}).get("title") if isinstance(result, dict) else result.get("title")
        print(f"✅ crm.item.get успешно: TITLE = {title}")
        return result
    except Exception as e:
        print(f"❌ crm.item.get ошибка: {e}")
        return None


async def main():
    print(f"🔍 Проверка соединения с Bitrix24\n")
    print(f"Webhook: {BITRIX}")
    print(f"ENTITY_RESOURCE: {ENTITY_RESOURCE}")
    print(f"ENTITY_SHIFT: {ENTITY_SHIFT}\n")
    
    # Тест создания
    item_id = await test_add()
    print()
    
    # Тест обновления
    update_ok = await test_update(item_id)
    print()
    
    # Тест получения
    item_data = await test_get(item_id)
    print()
    
    # Итог
    if item_id and update_ok:
        print("✅ REST API fully functional")
        print(f"   Создан тестовый элемент: item.id = {item_id}")
    else:
        print("❌ REST API имеет ограничения")
        if not item_id:
            print("   crm.item.add не работает")
        if not update_ok:
            print("   crm.item.update не работает")


if __name__ == "__main__":
    asyncio.run(main())









