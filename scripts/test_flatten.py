#!/usr/bin/env python3
"""Тест функции _flatten_for_template."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.lpa_pdf import _flatten_for_template

# Тестовые данные
test_data = {
    "object_name": "Тестовый объект",
    "section": "Строительство",
    "date": "12.11.2025",
    "foreman": "Прораб",
    "tasks": [
        {"name": "земляные", "unit": "ед.", "plan": 120, "fact": 110, "executor": "Бригада", "reason": ""},
        {"name": "подушка", "unit": "ед.", "plan": 80, "fact": 75, "executor": "Бригада", "reason": ""},
        {"name": "щебень", "unit": "ед.", "plan": 20, "fact": 18, "executor": "Бригада", "reason": ""},
    ],
    "tech": [],
    "timesheet": [],
    "materials": [],
    "plan_total": 220.0,
    "fact_total": 203.0,
    "efficiency": 92.27,
    "downtime_reason": "дождь с 13-15",
    "photos": [],
}

# Преобразуем
flattened = _flatten_for_template(test_data)

# Проверяем ключи
print("=" * 60)
print("ТЕСТ ФУНКЦИИ _flatten_for_template")
print("=" * 60)
print()
print(f"✅ Базовые поля:")
print(f"   object_name: {flattened.get('object_name')}")
print(f"   section: {flattened.get('section')}")
print(f"   date: {flattened.get('date')}")
print(f"   foreman: {flattened.get('foreman')}")
print(f"   plan_total: {flattened.get('plan_total')}")
print(f"   fact_total: {flattened.get('fact_total')}")
print(f"   efficiency: {flattened.get('efficiency')}")
print(f"   downtime_reason: {flattened.get('downtime_reason')}")
print()
print(f"✅ Задачи (task1_*):")
for i in range(1, 4):
    print(f"   task{i}_name: {flattened.get(f'task{i}_name')}")
    print(f"   task{i}_unit: {flattened.get(f'task{i}_unit')}")
    print(f"   task{i}_plan: {flattened.get(f'task{i}_plan')}")
    print(f"   task{i}_fact: {flattened.get(f'task{i}_fact')}")
    print()
print(f"✅ Пустые задачи (task4_*):")
print(f"   task4_name: '{flattened.get('task4_name')}' (должно быть пусто)")
print()
print(f"✅ Всего ключей: {len(flattened)}")
print(f"✅ Ключи task1_*: {sorted([k for k in flattened.keys() if k.startswith('task1_')])}")





