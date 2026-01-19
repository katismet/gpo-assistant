"""Проверка формата привязки объекта в сменах."""
import asyncio
import json
from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID, UF_OBJECT_LINK
from app.bitrix_field_map import resolve_code, upper_to_camel

async def check_shift_object_links():
    """Проверяем формат привязки объекта в сменах."""
    print("=" * 60)
    print("Проверка формата привязки объекта в сменах")
    print("=" * 60)
    
    f_date = resolve_code("Смена", "UF_DATE")
    f_date_camel = upper_to_camel(f_date)
    
    # Получаем последние 20 смен
    shifts_res = await bx("crm.item.list", {
        "entityTypeId": SHIFT_ETID,
        "select": ["id", f_date_camel, UF_OBJECT_LINK, "*"],
        "order": {"id": "desc"},
        "limit": 20
    })
    
    items = shifts_res.get("items", []) if isinstance(shifts_res, dict) else (shifts_res if isinstance(shifts_res, list) else [])
    
    print(f"\nНайдено смен: {len(items)}\n")
    
    for i, item in enumerate(items[:10], 1):  # Показываем первые 10
        sid = item.get("id")
        obj_link = item.get(UF_OBJECT_LINK)
        
        print(f"{i}. Смена #{sid}:")
        print(f"   UF_OBJECT_LINK (тип: {type(obj_link).__name__}): {obj_link}")
        
        if obj_link:
            if isinstance(obj_link, list):
                print(f"   Это список: {obj_link}")
                if obj_link:
                    print(f"   Первый элемент: {obj_link[0]} (тип: {type(obj_link[0]).__name__})")
            elif isinstance(obj_link, str):
                print(f"   Это строка: {obj_link}")
            elif isinstance(obj_link, dict):
                print(f"   Это словарь: {json.dumps(obj_link, indent=2, ensure_ascii=False)}")
            else:
                print(f"   Неизвестный тип: {obj_link}")
        else:
            print(f"   ⚠️ Привязка к объекту отсутствует!")
        
        # Пробуем извлечь ID объекта
        if obj_link:
            try:
                if isinstance(obj_link, list) and len(obj_link) > 0:
                    obj_str = obj_link[0]
                elif isinstance(obj_link, str):
                    obj_str = obj_link
                else:
                    obj_str = None
                
                if obj_str:
                    if isinstance(obj_str, str) and obj_str.startswith("D_"):
                        obj_id = int(obj_str[2:])
                        print(f"   ✅ Извлечен ID объекта: {obj_id} (из '{obj_str}')")
                    else:
                        try:
                            obj_id = int(obj_str)
                            print(f"   ✅ Извлечен ID объекта: {obj_id} (из '{obj_str}')")
                        except:
                            print(f"   ❌ Не удалось извлечь ID из '{obj_str}'")
                else:
                    print(f"   ❌ Не удалось получить строку из привязки")
            except Exception as e:
                print(f"   ❌ Ошибка извлечения ID: {e}")
        
        print()
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(check_shift_object_links())







