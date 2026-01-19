#!/usr/bin/env python3
"""Скрипт для проверки значения UF_PLAN_JSON в Bitrix24 для конкретной смены."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx
from app.bitrix_field_map import resolve_code, upper_to_camel


async def check_plan_json(bitrix_shift_id: int):
    """Проверяет значение UF_PLAN_JSON для смены."""
    print(f"🔍 Проверка плана для смены Bitrix ID: {bitrix_shift_id}")
    print()
    
    try:
        # Получаем смену из Bitrix24
        result = await bx("crm.item.get", {
            "entityTypeId": 1050,
            "id": bitrix_shift_id,
            "select": ["id", "*", "ufCrm%"]
        })
        
        if not result:
            print(f"❌ Смена {bitrix_shift_id} не найдена в Bitrix24")
            return
        
        item = result.get("item", result) if isinstance(result, dict) else result
        
        print(f"✅ Смена найдена:")
        print(f"   ID: {item.get('id')}")
        print(f"   Title: {item.get('title', 'N/A')}")
        print()
        
        # Определяем код поля
        f_plan_json = resolve_code("Смена", "UF_PLAN_JSON")
        f_plan_json_camel = upper_to_camel(f_plan_json) if f_plan_json else None
        
        print(f"📋 Коды полей:")
        print(f"   UF_PLAN_JSON: {f_plan_json}")
        print(f"   camelCase: {f_plan_json_camel}")
        print()
        
        # Пробуем разные варианты имени поля
        plan_raw = None
        field_used = None
        
        if f_plan_json_camel and f_plan_json_camel in item:
            plan_raw = item[f_plan_json_camel]
            field_used = f_plan_json_camel
        elif "ufCrm7UfPlanJson" in item:
            plan_raw = item["ufCrm7UfPlanJson"]
            field_used = "ufCrm7UfPlanJson"
        elif "UF_CRM_7_UF_PLAN_JSON" in item:
            plan_raw = item["UF_CRM_7_UF_PLAN_JSON"]
            field_used = "UF_CRM_7_UF_PLAN_JSON"
        else:
            # Ищем любое поле с PLAN_JSON в названии
            for key in item.keys():
                if "plan" in key.lower() and "json" in key.lower():
                    plan_raw = item[key]
                    field_used = key
                    break
        
        print(f"📄 Значение UF_PLAN_JSON:")
        if plan_raw is None:
            print(f"   ❌ Поле пустое или не найдено")
            print(f"   Проверенные поля: {f_plan_json_camel}, ufCrm7UfPlanJson, UF_CRM_7_UF_PLAN_JSON")
        else:
            print(f"   ✅ Найдено в поле: {field_used}")
            print(f"   Тип: {type(plan_raw).__name__}")
            
            # Парсим JSON если это строка
            plan_json = None
            if isinstance(plan_raw, str):
                try:
                    plan_json = json.loads(plan_raw)
                    print(f"   ✅ JSON строка успешно распарсена")
                except json.JSONDecodeError as e:
                    print(f"   ❌ Ошибка парсинга JSON: {e}")
                    print(f"   Сырое значение (первые 200 символов): {plan_raw[:200]}")
            elif isinstance(plan_raw, dict):
                plan_json = plan_raw
                print(f"   ✅ Значение уже dict")
            elif isinstance(plan_raw, list) and len(plan_raw) > 0:
                if isinstance(plan_raw[0], str):
                    try:
                        plan_json = json.loads(plan_raw[0])
                        print(f"   ✅ JSON из списка успешно распарсен")
                    except json.JSONDecodeError:
                        print(f"   ❌ Ошибка парсинга JSON из списка")
                else:
                    plan_json = plan_raw[0] if isinstance(plan_raw[0], dict) else None
            
            if plan_json:
                print()
                print(f"📊 Содержимое плана:")
                print(f"   tasks: {len(plan_json.get('tasks', []))} шт.")
                print(f"   total_plan: {plan_json.get('total_plan', 0)}")
                print(f"   date: {plan_json.get('date', 'N/A')}")
                print(f"   section: {plan_json.get('section', 'N/A')}")
                print(f"   foreman: {plan_json.get('foreman', 'N/A')}")
                print(f"   shift_type: {plan_json.get('shift_type', 'N/A')}")
                
                if "meta" in plan_json:
                    meta = plan_json["meta"]
                    print(f"   meta.object_bitrix_id: {meta.get('object_bitrix_id', 'N/A')}")
                    print(f"   meta.object_name: {meta.get('object_name', 'N/A')}")
                
                print()
                print(f"📝 Полный JSON (форматированный):")
                print(json.dumps(plan_json, ensure_ascii=False, indent=2))
            else:
                print(f"   Сырое значение: {plan_raw}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Главная функция."""
    if len(sys.argv) < 2:
        print("Использование: python scripts/debug_print_plan_json.py <BITRIX_SHIFT_ID>")
        print()
        print("Пример:")
        print("  python scripts/debug_print_plan_json.py 333")
        sys.exit(1)
    
    try:
        bitrix_shift_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный ID смены: {sys.argv[1]}")
        print("   ID должен быть числом")
        sys.exit(1)
    
    await check_plan_json(bitrix_shift_id)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())




