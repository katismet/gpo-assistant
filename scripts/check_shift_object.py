#!/usr/bin/env python3
"""Проверка поля объекта в смене."""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID, OBJECT_ETID


async def check_shift_object(shift_id: int):
    """Проверить поле объекта в смене."""
    print(f"📋 Проверяю поле объекта в смене {shift_id}...")
    print()
    
    try:
        result = await bx("crm.item.get", {
            "entityTypeId": SHIFT_ETID,
            "id": shift_id
        })
        
        item = result.get("item", result) if isinstance(result, dict) else result
        
        if not item:
            print("❌ Смена не найдена")
            return
        
        obj_field = item.get("ufCrm7UfCrmObject")
        print(f"📊 Поле ufCrm7UfCrmObject:")
        print(f"   Тип: {type(obj_field)}")
        print(f"   Значение: {obj_field}")
        print()
        
        if obj_field:
            # Пробуем извлечь ID объекта
            obj_id = None
            if isinstance(obj_field, list) and obj_field:
                obj_str = obj_field[0]
                print(f"   Элемент списка: {obj_str} (тип: {type(obj_str)})")
                if isinstance(obj_str, str) and obj_str.startswith("D_"):
                    obj_id = int(obj_str[2:])
                elif isinstance(obj_str, (int, float)):
                    obj_id = int(obj_str)
            elif isinstance(obj_field, str):
                print(f"   Строка: {obj_field}")
                if obj_field.startswith("D_"):
                    obj_id = int(obj_field[2:])
                else:
                    try:
                        obj_id = int(obj_field)
                    except ValueError:
                        pass
            elif isinstance(obj_field, (int, float)):
                obj_id = int(obj_field)
            
            if obj_id:
                print(f"   ✅ Извлечен ID объекта: {obj_id}")
                print()
                
                # Получаем название объекта
                obj_data = await bx("crm.item.get", {
                    "entityTypeId": OBJECT_ETID,
                    "id": obj_id
                })
                
                if obj_data:
                    obj_item = obj_data.get("item", obj_data)
                    obj_title = obj_item.get("title") or obj_item.get("TITLE") or f"Объект #{obj_id}"
                    print(f"   📌 Название объекта: {obj_title}")
                else:
                    print(f"   ❌ Объект {obj_id} не найден в Bitrix24")
            else:
                print(f"   ❌ Не удалось извлечь ID объекта из {obj_field}")
        else:
            print("   ❌ Поле объекта пустое")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Главная функция."""
    if len(sys.argv) < 2:
        print("Использование: python scripts/check_shift_object.py <SHIFT_ID>")
        print()
        print("Пример:")
        print("  python scripts/check_shift_object.py 297")
        sys.exit(1)
    
    try:
        shift_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный ID смены: {sys.argv[1]}")
        sys.exit(1)
    
    await check_shift_object(shift_id)


if __name__ == "__main__":
    asyncio.run(main())





