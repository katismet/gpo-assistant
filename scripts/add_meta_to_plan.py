#!/usr/bin/env python3
"""Добавление meta в plan_json для существующей смены."""

import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx


async def add_meta_to_plan(shift_id: int, object_bitrix_id: int, object_name: str):
    """Добавить meta в plan_json для смены."""
    print(f"📋 Добавление meta в plan_json для смены {shift_id}...")
    print(f"   object_bitrix_id: {object_bitrix_id}")
    print(f"   object_name: {object_name}")
    print()
    
    try:
        # Получаем текущий plan_json
        result = await bx("crm.item.get", {
            "entityTypeId": 1050,
            "id": shift_id,
            "select": ["id", "*", "ufCrm%"]
        })
        
        if not result:
            print("❌ Смена не найдена")
            return
        
        item = result.get("item", result)
        plan_raw = item.get("ufCrm7UfPlanJson")
        
        if not plan_raw:
            print("❌ UF_PLAN_JSON пусто")
            return
        
        # Парсим JSON
        if isinstance(plan_raw, list):
            if plan_raw:
                plan_raw = plan_raw[0]
            else:
                print("❌ UF_PLAN_JSON - пустой список")
                return
        
        if isinstance(plan_raw, str):
            try:
                plan_json = json.loads(plan_raw)
            except json.JSONDecodeError as e:
                print(f"❌ Ошибка парсинга JSON: {e}")
                return
        else:
            plan_json = plan_raw
        
        # Проверяем, есть ли уже meta
        if plan_json.get("meta"):
            print(f"⚠️  Meta уже существует в plan_json")
            print(f"   Текущая meta: {plan_json.get('meta')}")
            response = input("   Перезаписать? (y/n): ")
            if response.lower() != 'y':
                print("   Отменено")
                return
        
        # Добавляем meta
        plan_json["meta"] = {
            "object_bitrix_id": int(object_bitrix_id),
            "object_name": str(object_name).strip()
        }
        
        # Обновляем в Bitrix24
        update_result = await bx("crm.item.update", {
            "entityTypeId": 1050,
            "id": shift_id,
            "fields": {
                "ufCrm7UfPlanJson": json.dumps(plan_json, ensure_ascii=False)
            }
        })
        
        if update_result:
            print(f"✅ Meta добавлена в plan_json")
            print(f"   Обновленный plan_json: {json.dumps(plan_json, ensure_ascii=False, indent=2)}")
        else:
            print(f"❌ Ошибка обновления")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Использование: python scripts/add_meta_to_plan.py <SHIFT_ID> <OBJECT_BITRIX_ID> <OBJECT_NAME>")
        print()
        print("Пример:")
        print("  python scripts/add_meta_to_plan.py 297 51 'Объект №20 - Строительство автопарка'")
        sys.exit(1)
    
    try:
        shift_id = int(sys.argv[1])
        object_bitrix_id = int(sys.argv[2])
        object_name = sys.argv[3]
    except (ValueError, IndexError) as e:
        print(f"❌ Неверные параметры: {e}")
        sys.exit(1)
    
    asyncio.run(add_meta_to_plan(shift_id, object_bitrix_id, object_name))





