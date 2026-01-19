import os
import asyncio
import httpx
import json
from dotenv import load_dotenv
from datetime import date

load_dotenv()
BASE = os.getenv("BITRIX_BASE")
TOK = os.getenv("BITRIX_TOKEN")

async def monitor_bitrix_records():
    """Мониторинг записей в Bitrix24 для проверки интеграции с ботом"""
    async with httpx.AsyncClient(timeout=20) as x:
        print("=== МОНИТОРИНГ BITRIX24 ЗАПИСЕЙ ===")
        print(f"Base URL: {BASE}")
        print(f"Token: {TOK}")
        print()
        
        # Получаем текущие записи
        print("Текущие записи в Bitrix24:")
        
        # Объекты
        try:
            r = await x.get(f"{BASE}/rest/{TOK}/crm.item.list.json",
                           params={"entityTypeId": 1046, "select[]": ["id", "title", "createdTime"], "start": 0, "limit": 10})
            if r.status_code == 200:
                data = r.json()
                objects = data.get("result", {}).get("items", [])
                print(f"\n📋 Объекты ({len(objects)}):")
                for obj in objects:
                    print(f"  ID: {obj['id']}, Название: {obj['title']}, Создан: {obj['createdTime']}")
            else:
                print(f"Ошибка получения объектов: {r.status_code}")
        except Exception as e:
            print(f"Ошибка: {e}")
        
        # Смены
        try:
            r = await x.get(f"{BASE}/rest/{TOK}/crm.item.list.json",
                           params={"entityTypeId": 1050, "select[]": ["id", "title", "createdTime"], "start": 0, "limit": 10})
            if r.status_code == 200:
                data = r.json()
                shifts = data.get("result", {}).get("items", [])
                print(f"\n🔄 Смены ({len(shifts)}):")
                for shift in shifts:
                    print(f"  ID: {shift['id']}, Название: {shift['title']}, Создан: {shift['createdTime']}")
            else:
                print(f"Ошибка получения смен: {r.status_code}")
        except Exception as e:
            print(f"Ошибка: {e}")
        
        print("\n" + "="*60)
        print("🤖 Бот запущен! Теперь можете:")
        print("1. Отправить команду /start в Telegram боту")
        print("2. Создать план через бота")
        print("3. Завершить смену через бота")
        print("4. Проверить новые записи в Bitrix24")
        print("="*60)

if __name__ == "__main__":
    asyncio.run(monitor_bitrix_records())
