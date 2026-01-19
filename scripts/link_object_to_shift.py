#!/usr/bin/env python3
"""Привязка объекта к смене в Bitrix24."""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx
from app.services.bitrix_ids import OBJECT_ETID, SHIFT_ETID


async def list_objects():
    """Получить список всех объектов."""
    print("📋 Получаю список объектов из Bitrix24...")
    print()
    
    try:
        result = await bx("crm.item.list", {
            "entityTypeId": OBJECT_ETID,
            "select": ["id", "title"],
            "order": {"id": "DESC"},
            "limit": 50
        })
        
        items = result.get("items", []) if isinstance(result, dict) else result
        
        if not items:
            print("❌ Объекты не найдены")
            return []
        
        print(f"✅ Найдено объектов: {len(items)}")
        print()
        print("Список объектов:")
        print("-" * 60)
        for i, obj in enumerate(items, 1):
            obj_id = obj.get("id")
            obj_title = obj.get("title") or obj.get("TITLE") or f"Объект #{obj_id}"
            print(f"{i:2d}. ID: {obj_id:4d} | {obj_title}")
        print("-" * 60)
        
        return items
        
    except Exception as e:
        print(f"❌ Ошибка при получении объектов: {e}")
        return []


async def link_object_to_shift(shift_id: int, object_id: int):
    """Привязать объект к смене."""
    print(f"🔗 Привязываю объект {object_id} к смене {shift_id}...")
    print()
    
    try:
        # Формат для привязки: ["D_1046"] где 1046 - это ID объекта
        object_link = [f"D_{object_id}"]
        
        result = await bx("crm.item.update", {
            "entityTypeId": SHIFT_ETID,
            "id": shift_id,
            "fields": {
                "ufCrm7UfCrmObject": object_link
            }
        })
        
        if result:
            print("✅ Объект успешно привязан к смене!")
            print()
            
            # Проверяем результат
            check = await bx("crm.item.get", {
                "entityTypeId": SHIFT_ETID,
                "id": shift_id
            })
            
            item = check.get("item", check) if isinstance(check, dict) else check
            obj_field = item.get("ufCrm7UfCrmObject") if item else None
            
            print("📋 Проверка результата:")
            if obj_field:
                if isinstance(obj_field, list) and obj_field:
                    obj_str = obj_field[0]
                    if isinstance(obj_str, str) and obj_str.startswith("D_"):
                        linked_obj_id = int(obj_str[2:])
                        print(f"   ✓ Объект привязан: ID {linked_obj_id}")
                        
                        # Получаем название объекта
                        obj_data = await bx("crm.item.get", {
                            "entityTypeId": OBJECT_ETID,
                            "id": linked_obj_id
                        })
                        if obj_data:
                            obj_item = obj_data.get("item", obj_data)
                            obj_title = obj_item.get("title") or obj_item.get("TITLE") or f"Объект #{linked_obj_id}"
                            print(f"   ✓ Название: {obj_title}")
                    else:
                        print(f"   ⚠️  Неожиданный формат: {obj_str}")
                else:
                    print(f"   ⚠️  Неожиданный формат поля: {type(obj_field)}")
            else:
                print(f"   ❌ Объект не привязан (поле пустое)")
        else:
            print("❌ Не удалось привязать объект")
            
    except Exception as e:
        print(f"❌ Ошибка при привязке объекта: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Главная функция."""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python scripts/link_object_to_shift.py list")
        print("  python scripts/link_object_to_shift.py <SHIFT_ID> <OBJECT_ID>")
        print()
        print("Примеры:")
        print("  python scripts/link_object_to_shift.py list")
        print("  python scripts/link_object_to_shift.py 297 1046")
        sys.exit(1)
    
    if sys.argv[1] == "list":
        await list_objects()
    else:
        if len(sys.argv) < 3:
            print("❌ Не указан ID объекта")
            print("   Используйте: python scripts/link_object_to_shift.py <SHIFT_ID> <OBJECT_ID>")
            sys.exit(1)
        
        try:
            shift_id = int(sys.argv[1])
            object_id = int(sys.argv[2])
        except ValueError:
            print(f"❌ Неверные ID: смена={sys.argv[1]}, объект={sys.argv[2]}")
            print("   ID должны быть числами")
            sys.exit(1)
        
        await link_object_to_shift(shift_id, object_id)


if __name__ == "__main__":
    asyncio.run(main())





