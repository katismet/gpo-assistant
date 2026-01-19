import os
import asyncio
import httpx
import json
from dotenv import load_dotenv

load_dotenv()
BASE = os.getenv("BITRIX_BASE")
TOK = os.getenv("BITRIX_TOKEN")

async def main():
    async with httpx.AsyncClient(timeout=20) as x:
        print("=== Проверка доступных сущностей ===")
        print(f"Base URL: {BASE}")
        print(f"Token: {TOK}")
        print()
        
        # Проверяем стандартные сущности CRM
        standard_entities = [
            (1, "Сделка"),
            (2, "Контакт"), 
            (3, "Компания"),
            (4, "Лид"),
            (5, "Смарт-процесс"),
            (6, "Счет"),
            (7, "Смены"),
            (8, "Задача"),
            (9, "Событие"),
            (10, "Предложение")
        ]
        
        available_entities = []
        
        for entity_id, entity_name in standard_entities:
            try:
                r = await x.get(f"{BASE}/rest/{TOK}/crm.item.list.json",
                                params={"entityTypeId": entity_id, "select[]": ["id"], "start": 0, "limit": 1})
                
                if r.status_code == 200:
                    data = r.json()
                    if "result" in data:
                        available_entities.append((entity_id, entity_name, "✓ Доступен"))
                    else:
                        available_entities.append((entity_id, entity_name, f"✗ Ошибка: {data.get('error', 'Unknown')}"))
                else:
                    available_entities.append((entity_id, entity_name, f"✗ HTTP {r.status_code}"))
                    
            except Exception as e:
                available_entities.append((entity_id, entity_name, f"✗ Исключение: {str(e)}"))
        
        print("Результаты проверки:")
        print("-" * 60)
        for entity_id, entity_name, status in available_entities:
            print(f"ID {entity_id:2d}: {entity_name:20s} - {status}")
        
        print()
        print("=== Дополнительная информация ===")
        
        # Пробуем получить информацию о смарт-процессах
        try:
            r = await x.get(f"{BASE}/rest/{TOK}/crm.type.list.json")
            if r.status_code == 200:
                data = r.json()
                if "result" in data:
                    print("Доступные типы CRM:")
                    for item in data["result"]:
                        print(f"  ID: {item.get('id')}, Название: {item.get('title')}")
                else:
                    print(f"Ошибка при получении типов CRM: {data}")
        except Exception as e:
            print(f"Не удалось получить типы CRM: {e}")

if __name__ == "__main__":
    asyncio.run(main())