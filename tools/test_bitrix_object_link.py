"""Тест получения привязки объекта через crm.item.get."""
import asyncio
import json
from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID, UF_OBJECT_LINK

async def test_get_shift_object():
    """Тестируем получение объекта через crm.item.get."""
    print("=" * 60)
    print("Тест получения привязки объекта через crm.item.get")
    print("=" * 60)
    
    # Получаем список смен
    shifts_res = await bx("crm.item.list", {
        "entityTypeId": SHIFT_ETID,
        "select": ["id"],
        "order": {"id": "desc"},
        "limit": 5
    })
    
    items = shifts_res.get("items", []) if isinstance(shifts_res, dict) else (shifts_res if isinstance(shifts_res, list) else [])
    
    print(f"\nНайдено смен: {len(items)}\n")
    
    for item in items:
        sid = item.get("id")
        print(f"Смена #{sid}:")
        
        # Пробуем получить полные данные через crm.item.get
        try:
            shift_full = await bx("crm.item.get", {
                "entityTypeId": SHIFT_ETID,
                "id": sid
            })
            
            obj_link = shift_full.get(UF_OBJECT_LINK)
            print(f"  UF_OBJECT_LINK через crm.item.get: {obj_link} (тип: {type(obj_link).__name__})")
            
            if isinstance(obj_link, list):
                print(f"  ✅ Это массив: {obj_link}")
            elif isinstance(obj_link, str):
                print(f"  ⚠️ Это строка: '{obj_link}'")
            elif isinstance(obj_link, dict):
                print(f"  ⚠️ Это словарь: {json.dumps(obj_link, indent=4, ensure_ascii=False)}")
            
            # Пробуем все варианты
            for field_name in [UF_OBJECT_LINK, "ufCrm7UfCrmObject", "UF_CRM_7_UF_CRM_OBJECT"]:
                val = shift_full.get(field_name)
                if val and val != "Array":
                    print(f"  Поле {field_name}: {val} (тип: {type(val).__name__})")
            
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
        
        print()

if __name__ == "__main__":
    asyncio.run(test_get_shift_object())







