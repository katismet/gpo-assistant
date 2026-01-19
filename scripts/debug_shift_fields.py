#!/usr/bin/env python3
"""Диагностический скрипт для проверки полей смены в Bitrix24."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx
from app.bitrix_field_map import resolve_code, upper_to_camel


async def debug_shift_fields(bitrix_shift_id: int):
    """Проверяет поля UF_PLAN_JSON и UF_FACT_JSON для смены."""
    print(f"🔍 Диагностика полей смены Bitrix ID: {bitrix_shift_id}")
    print("=" * 60)
    
    try:
        # Получаем смену из Bitrix24 с полным select
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
        
        # Определяем коды полей
        f_plan_json = resolve_code("Смена", "UF_PLAN_JSON")
        f_plan_json_camel = upper_to_camel(f_plan_json) if f_plan_json else None
        f_fact_json = resolve_code("Смена", "UF_FACT_JSON")
        f_fact_json_camel = upper_to_camel(f_fact_json) if f_fact_json else None
        
        print(f"📋 Коды полей:")
        print(f"   UF_PLAN_JSON: {f_plan_json} -> camelCase: {f_plan_json_camel}")
        print(f"   UF_FACT_JSON: {f_fact_json} -> camelCase: {f_fact_json_camel}")
        print()
        
        # Проверяем UF_PLAN_JSON
        print("=" * 60)
        print("📄 UF_PLAN_JSON:")
        print("-" * 60)
        
        plan_raw = None
        plan_field_used = None
        
        # Пробуем разные варианты имени поля
        if f_plan_json_camel and f_plan_json_camel in item:
            plan_raw = item[f_plan_json_camel]
            plan_field_used = f_plan_json_camel
        elif "ufCrm7UfPlanJson" in item:
            plan_raw = item["ufCrm7UfPlanJson"]
            plan_field_used = "ufCrm7UfPlanJson"
        elif "UF_CRM_7_UF_PLAN_JSON" in item:
            plan_raw = item["UF_CRM_7_UF_PLAN_JSON"]
            plan_field_used = "UF_CRM_7_UF_PLAN_JSON"
        
        if plan_raw is None:
            print("   ❌ Поле пустое или не найдено")
            print(f"   Проверенные поля: {f_plan_json_camel}, ufCrm7UfPlanJson, UF_CRM_7_UF_PLAN_JSON")
            print(f"   Доступные поля с 'plan' в названии:")
            for key in sorted(item.keys()):
                if "plan" in key.lower():
                    print(f"      - {key}: {type(item[key]).__name__} = {str(item[key])[:100]}")
        else:
            print(f"   ✅ Найдено в поле: {plan_field_used}")
            print(f"   Тип сырого значения: {type(plan_raw).__name__}")
            print(f"   Сырое значение: {repr(plan_raw)}")
            
            # Парсим JSON
            plan_json = None
            if isinstance(plan_raw, str):
                try:
                    plan_json = json.loads(plan_raw)
                    print(f"   ✅ JSON строка успешно распарсена")
                except json.JSONDecodeError as e:
                    print(f"   ❌ Ошибка парсинга JSON: {e}")
            elif isinstance(plan_raw, list):
                if len(plan_raw) > 0:
                    if isinstance(plan_raw[0], str):
                        try:
                            plan_json = json.loads(plan_raw[0])
                            print(f"   ✅ JSON из списка успешно распарсен")
                        except json.JSONDecodeError:
                            print(f"   ❌ Ошибка парсинга JSON из списка")
                    elif isinstance(plan_raw[0], dict):
                        plan_json = plan_raw[0]
                        print(f"   ✅ Значение уже dict в списке")
                else:
                    print(f"   ⚠️  Список пустой")
            elif isinstance(plan_raw, dict):
                plan_json = plan_raw
                print(f"   ✅ Значение уже dict")
            
            if plan_json:
                print()
                print(f"   📊 Содержимое плана:")
                print(f"      tasks: {len(plan_json.get('tasks', []))} шт.")
                print(f"      total_plan: {plan_json.get('total_plan', 'N/A')}")
                print(f"      date: {plan_json.get('date', 'N/A')}")
                print(f"      section: {plan_json.get('section', 'N/A')}")
                print(f"      foreman: {plan_json.get('foreman', 'N/A')}")
                print(f"      shift_type: {plan_json.get('shift_type', 'N/A')}")
                
                if "meta" in plan_json:
                    meta = plan_json["meta"]
                    print(f"      ✅ meta присутствует:")
                    print(f"         object_bitrix_id: {meta.get('object_bitrix_id', 'N/A')}")
                    print(f"         object_name: {meta.get('object_name', 'N/A')}")
                else:
                    print(f"      ❌ meta отсутствует!")
                
                print()
                print(f"   📝 Полный JSON:")
                print(json.dumps(plan_json, ensure_ascii=False, indent=2))
        
        # Проверяем UF_FACT_JSON
        print()
        print("=" * 60)
        print("📄 UF_FACT_JSON:")
        print("-" * 60)
        
        fact_raw = None
        fact_field_used = None
        
        if f_fact_json_camel and f_fact_json_camel in item:
            fact_raw = item[f_fact_json_camel]
            fact_field_used = f_fact_json_camel
        elif "ufCrm7UfFactJson" in item:
            fact_raw = item["ufCrm7UfFactJson"]
            fact_field_used = "ufCrm7UfFactJson"
        elif "UF_CRM_7_UF_FACT_JSON" in item:
            fact_raw = item["UF_CRM_7_UF_FACT_JSON"]
            fact_field_used = "UF_CRM_7_UF_FACT_JSON"
        
        if fact_raw is None:
            print("   ❌ Поле пустое или не найдено")
        else:
            print(f"   ✅ Найдено в поле: {fact_field_used}")
            print(f"   Тип сырого значения: {type(fact_raw).__name__}")
            if isinstance(fact_raw, str):
                print(f"   Длина строки: {len(fact_raw)} символов")
                print(f"   Первые 200 символов: {fact_raw[:200]}...")
            else:
                print(f"   Значение: {repr(fact_raw)[:200]}")
        
        print()
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Главная функция."""
    if len(sys.argv) < 2:
        print("Использование: python scripts/debug_shift_fields.py <BITRIX_SHIFT_ID>")
        print()
        print("Пример:")
        print("  python scripts/debug_shift_fields.py 333")
        sys.exit(1)
    
    try:
        bitrix_shift_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный ID смены: {sys.argv[1]}")
        print("   ID должен быть числом")
        sys.exit(1)
    
    await debug_shift_fields(bitrix_shift_id)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())




