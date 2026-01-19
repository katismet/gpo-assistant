#!/usr/bin/env python3
"""Тест получения поля объекта через разные методы Bitrix24 API."""

import sys
import asyncio
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID


async def test_all_methods(shift_id: int):
    """Тест всех методов получения поля объекта."""
    print("=" * 70)
    print(f"ТЕСТ ПОЛУЧЕНИЯ ПОЛЯ ОБЪЕКТА ДЛЯ СМЕНЫ {shift_id}")
    print("=" * 70)
    print()
    
    # Метод 1: crm.item.get (базовый)
    print("МЕТОД 1: crm.item.get (базовый)")
    try:
        result = await bx("crm.item.get", {
            "entityTypeId": SHIFT_ETID,
            "id": shift_id
        })
        item = result.get("item", result) if isinstance(result, dict) else result
        obj_field = item.get("ufCrm7UfCrmObject") if item else None
        print(f"   Результат: {obj_field} (тип: {type(obj_field)})")
        if isinstance(obj_field, str):
            print(f"   ⚠️  Строка вместо массива: {obj_field}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    print()
    
    # Метод 2: crm.item.get с select (массив)
    print("МЕТОД 2: crm.item.get с select (массив)")
    try:
        result = await bx("crm.item.get", {
            "entityTypeId": SHIFT_ETID,
            "id": shift_id,
            "select": ["ufCrm7UfCrmObject"]
        })
        item = result.get("item", result) if isinstance(result, dict) else result
        obj_field = item.get("ufCrm7UfCrmObject") if item else None
        print(f"   Результат: {obj_field} (тип: {type(obj_field)})")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    print()
    
    # Метод 3: crm.item.get с select (строка)
    print("МЕТОД 3: crm.item.get с select (строка)")
    try:
        result = await bx("crm.item.get", {
            "entityTypeId": SHIFT_ETID,
            "id": shift_id,
            "select": "ufCrm7UfCrmObject"
        })
        item = result.get("item", result) if isinstance(result, dict) else result
        obj_field = item.get("ufCrm7UfCrmObject") if item else None
        print(f"   Результат: {obj_field} (тип: {type(obj_field)})")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    print()
    
    # Метод 4: crm.item.list
    print("МЕТОД 4: crm.item.list")
    try:
        result = await bx("crm.item.list", {
            "entityTypeId": SHIFT_ETID,
            "filter": {"id": shift_id},
            "select": ["id", "ufCrm7UfCrmObject"]
        })
        items = result.get("items", []) if isinstance(result, dict) else result
        if items and len(items) > 0:
            item = items[0]
            obj_field = item.get("ufCrm7UfCrmObject")
            print(f"   Результат: {obj_field} (тип: {type(obj_field)})")
        else:
            print(f"   ❌ Смена не найдена")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    print()
    
    # Метод 5: Полный ответ (для анализа)
    print("МЕТОД 5: Полный ответ (первые 500 символов)")
    try:
        result = await bx("crm.item.get", {
            "entityTypeId": SHIFT_ETID,
            "id": shift_id
        })
        result_str = json.dumps(result, ensure_ascii=False, indent=2)
        print(f"   Результат (первые 500 символов):")
        print(f"   {result_str[:500]}...")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    print()
    
    # Метод 6: crm.item.fields для получения информации о поле
    print("МЕТОД 6: crm.item.fields (информация о поле)")
    try:
        fields_result = await bx("crm.item.fields", {
            "entityTypeId": SHIFT_ETID
        })
        if fields_result:
            fields = fields_result.get("fields", fields_result) if isinstance(fields_result, dict) else fields_result
            obj_field_info = fields.get("ufCrm7UfCrmObject") if isinstance(fields, dict) else None
            if obj_field_info:
                print(f"   Информация о поле:")
                print(f"   {json.dumps(obj_field_info, ensure_ascii=False, indent=2)}")
            else:
                print(f"   ⚠️  Поле не найдено в списке полей")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    print()


async def main():
    """Главная функция."""
    if len(sys.argv) < 2:
        print("Использование: python scripts/test_bitrix_object_field.py <SHIFT_ID>")
        print()
        print("Пример:")
        print("  python scripts/test_bitrix_object_field.py 297")
        sys.exit(1)
    
    try:
        shift_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный ID смены: {sys.argv[1]}")
        sys.exit(1)
    
    await test_all_methods(shift_id)


if __name__ == "__main__":
    asyncio.run(main())





