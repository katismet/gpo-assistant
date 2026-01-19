#!/usr/bin/env python3
"""Проверка наличия meta в plan_json для смены."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx
import asyncio


async def check_plan_meta(shift_id: int):
    """Проверить наличие meta в plan_json."""
    print(f"📋 Проверка meta в plan_json для смены {shift_id}...")
    print()
    
    try:
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
        
        print(f"✅ Plan JSON найден:")
        print(f"   Ключи: {list(plan_json.keys())}")
        print()
        
        # Проверяем meta
        meta = plan_json.get("meta")
        if meta:
            print(f"✅ Meta найдена:")
            print(f"   object_bitrix_id: {meta.get('object_bitrix_id')}")
            print(f"   object_name: {meta.get('object_name')}")
        else:
            print(f"❌ Meta отсутствует в plan_json")
            print(f"   Это означает, что смена была создана до добавления meta")
            print(f"   Для проверки нужно создать новую смену через бота")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python scripts/check_plan_meta.py <SHIFT_ID>")
        print()
        print("Пример:")
        print("  python scripts/check_plan_meta.py 297")
        sys.exit(1)
    
    try:
        shift_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный ID смены: {sys.argv[1]}")
        sys.exit(1)
    
    asyncio.run(check_plan_meta(shift_id))

