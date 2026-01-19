"""Проверка всех полей смены."""
import asyncio
import json
from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID

async def check_shift_fields():
    """Проверяем все поля смены."""
    print("=" * 60)
    print("Проверка всех полей смены")
    print("=" * 60)
    
    # Получаем одну смену
    shifts_res = await bx("crm.item.list", {
        "entityTypeId": SHIFT_ETID,
        "select": ["id", "*"],
        "order": {"id": "desc"},
        "limit": 1
    })
    
    items = shifts_res.get("items", []) if isinstance(shifts_res, dict) else (shifts_res if isinstance(shifts_res, list) else [])
    
    if not items:
        print("Смены не найдены")
        return
    
    item = items[0]
    sid = item.get("id")
    
    print(f"\nСмена #{sid}:\n")
    print("Все поля (первые 50):")
    for i, (key, value) in enumerate(list(item.items())[:50], 1):
        if "object" in key.lower() or "uf" in key.lower():
            print(f"  {i}. {key}: {value} (тип: {type(value).__name__})")
    
    print("\n\nВсе поля с 'uf' или 'object':")
    for key, value in item.items():
        if "object" in key.lower() or ("uf" in key.lower() and "object" in key.lower()):
            print(f"  {key}: {value} (тип: {type(value).__name__})")
    
    # Пробуем получить через crm.item.get с явным указанием полей
    print("\n\nПробуем через crm.item.get с явным указанием полей:")
    try:
        shift_full = await bx("crm.item.get", {
            "entityTypeId": SHIFT_ETID,
            "id": sid,
            "select": ["*", "ufCrm7UfCrmObject", "ufCrmObject", "object"]
        })
        
        print("Поля с 'object':")
        for key, value in shift_full.items():
            if "object" in key.lower():
                print(f"  {key}: {value} (тип: {type(value).__name__})")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(check_shift_fields())







