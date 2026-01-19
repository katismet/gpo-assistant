#!/usr/bin/env python3
"""Разовая запись плана в уже созданную смену (бэкофилл)."""

import json
import sys
import asyncio
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx


def _num(x):
    """Преобразует значение в число."""
    try:
        return float(str(x).replace(',', '.'))
    except:
        return 0.0


async def backfill_plan(shift_id: int):
    """Записывает план в существующую смену."""
    plan_tasks = [
        {"name": "земляные", "unit": "ед.", "plan": 120, "executor": "Бригада"},
        {"name": "подушка", "unit": "ед.", "plan": 80, "executor": "Бригада"},
        {"name": "щебень", "unit": "ед.", "plan": 20, "executor": "Бригада"},
    ]
    
    total_plan = sum(_num(t["plan"]) for t in plan_tasks)
    
    plan_json = {
        "tasks": plan_tasks,
        "total_plan": total_plan,
    }
    
    payload = {
        "entityTypeId": 1050,
        "id": shift_id,
        "fields": {
            "ufCrm7UfPlanJson": json.dumps(plan_json, ensure_ascii=False),
            "ufCrm7UfCrmPlanTotal": float(total_plan),
        }
    }
    
    print(f"📝 Записываю план в смену {shift_id}...")
    print(f"   Задач: {len(plan_tasks)}")
    print(f"   Total plan: {total_plan}")
    print()
    
    r = await bx("crm.item.update", payload)
    print(f"✅ Обновление: {r}")
    print()
    
    # Проверяем результат
    g = await bx("crm.item.get", {"entityTypeId": 1050, "id": shift_id})
    item = (g or {}).get("item", g) if isinstance(g, dict) else g
    
    plan_raw = item.get("ufCrm7UfPlanJson") if item else None
    print(f"📋 Проверка результата:")
    print(f"   plan_raw = {plan_raw}")
    
    if isinstance(plan_raw, list) and len(plan_raw) > 0:
        print(f"   ✓ План сохранен как список с JSON-строкой")
        try:
            parsed = json.loads(plan_raw[0])
            print(f"   ✓ Содержит: tasks={len(parsed.get('tasks', []))}, total_plan={parsed.get('total_plan', 0)}")
        except:
            print(f"   ⚠️  Не удалось распарсить JSON")
    elif plan_raw == []:
        print(f"   ❌ План не сохранился (пустой список)")
    else:
        print(f"   ⚠️  Неожиданный формат: {type(plan_raw)}")


async def main():
    """Главная функция."""
    if len(sys.argv) < 2:
        print("Использование: python scripts/backfill_plan.py <SHIFT_ID>")
        print()
        print("Пример:")
        print("  python scripts/backfill_plan.py 285")
        sys.exit(1)
    
    try:
        shift_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный ID смены: {sys.argv[1]}")
        print("   ID должен быть числом")
        sys.exit(1)
    
    await backfill_plan(shift_id)


if __name__ == "__main__":
    asyncio.run(main())





