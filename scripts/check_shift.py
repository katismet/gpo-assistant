#!/usr/bin/env python3
"""Проверка данных смены в Bitrix24."""

import json
import sys
import asyncio
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx


async def check_shift(shift_id: int):
    """Проверяет данные смены в Bitrix24."""
    try:
        r = await bx("crm.item.get", {"entityTypeId": 1050, "id": shift_id})
        item = (r or {}).get("item", r) if isinstance(r, dict) else r
        
        if not item:
            print(f"❌ Смена {shift_id} не найдена в Bitrix24")
            return
        
        print(f"📄 Смена {shift_id}:")
        print(f"   Title: {item.get('title', 'N/A')}")
        print()
        
        def parse(raw):
            """Парсит JSON поле из Bitrix24."""
            if raw is None:
                return {}
            if isinstance(raw, list):
                raw = (raw[0] if raw else "")
            if isinstance(raw, str) and raw.strip():
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {}
            return raw if isinstance(raw, dict) else {}
        
        plan_raw = item.get("ufCrm7UfPlanJson")
        fact_raw = item.get("ufCrm7UfFactJson")
        photos_uf = item.get("ufCrm7UfShiftPhotos")
        
        print("🔍 Сырые данные из Bitrix24:")
        print(f"   plan_raw = {plan_raw}")
        if isinstance(plan_raw, list) and len(plan_raw) > 0:
            print(f"      → Тип: список с {len(plan_raw)} элементом(ами)")
            if isinstance(plan_raw[0], str):
                print(f"      → Формат: список с JSON-строкой ✓")
                try:
                    parsed = json.loads(plan_raw[0])
                    print(f"      → Содержит: tasks={len(parsed.get('tasks', []))}, total_plan={parsed.get('total_plan', 0)}")
                except:
                    print(f"      → ⚠️  Не валидный JSON")
            else:
                print(f"      → Тип элемента: {type(plan_raw[0])}")
        elif plan_raw == []:
            print(f"      → Пустой список (план не сохранен) ❌")
        else:
            print(f"      → Тип: {type(plan_raw)}")
        
        print(f"   fact_raw = {fact_raw}")
        if isinstance(fact_raw, list) and len(fact_raw) > 0:
            print(f"      → Тип: список с {len(fact_raw)} элементом(ами)")
            if isinstance(fact_raw[0], str):
                print(f"      → Формат: список с JSON-строкой ✓")
                try:
                    parsed = json.loads(fact_raw[0])
                    print(f"      → Содержит: tasks={len(parsed.get('tasks', []))}, total_fact={parsed.get('total_fact', 0)}")
                except:
                    print(f"      → ⚠️  Не валидный JSON")
            else:
                print(f"      → Тип элемента: {type(fact_raw[0])}")
        elif fact_raw == []:
            print(f"      → Пустой список (факт не сохранен) ❌")
        else:
            print(f"      → Тип: {type(fact_raw)}")
        
        print(f"   photosUF = {photos_uf}")
        if photos_uf:
            if isinstance(photos_uf, list):
                print(f"      → Тип: массив файлов с {len(photos_uf)} элементом(ами) ✓")
                if len(photos_uf) > 0:
                    first_photo = photos_uf[0]
                    if isinstance(first_photo, dict):
                        print(f"      → Формат: объекты с id/downloadUrl")
                        print(f"      → Пример: id={first_photo.get('id', 'N/A')}, name={first_photo.get('name', 'N/A')}")
                    else:
                        print(f"      → Тип элемента: {type(first_photo)}")
            else:
                print(f"      → Тип: {type(photos_uf)}")
        else:
            print(f"      → None (фото не загружены в Bitrix24)")
            # Проверяем, есть ли фото в fact_json
            fact = parse(fact_raw)
            if fact.get("photos"):
                print(f"      → ⚠️  Фото есть только в fact_json.photos (Telegram file_id): {len(fact.get('photos', []))}")
        print()
        
        plan = parse(plan_raw)
        fact = parse(fact_raw)
        
        print("📊 Распарсенные данные:")
        print(f"   plan.tasks = {len(plan.get('tasks', []))}, plan.total = {plan.get('total_plan', 0)}")
        print(f"   fact.tasks = {len(fact.get('tasks', []))}, fact.total = {fact.get('total_fact', 0)}")
        print(f"   downtime = {fact.get('downtime_reason', 'Нет')}")
        print()
        
        # Проверка формата
        print("✅ Проверка формата:")
        if isinstance(plan_raw, list) and len(plan_raw) > 0 and isinstance(plan_raw[0], str):
            print("   ✓ plan_raw - список с JSON строкой")
        elif plan_raw == []:
            print("   ❌ plan_raw - пустой список (план не сохранен)")
        else:
            print(f"   ⚠️  plan_raw - неожиданный формат: {type(plan_raw)}")
        
        if isinstance(fact_raw, list) and len(fact_raw) > 0 and isinstance(fact_raw[0], str):
            print("   ✓ fact_raw - список с JSON строкой")
        elif fact_raw == []:
            print("   ❌ fact_raw - пустой список (факт не сохранен)")
        else:
            print(f"   ⚠️  fact_raw - неожиданный формат: {type(fact_raw)}")
        
        # Проверка данных
        print()
        print("📋 Проверка данных:")
        if plan.get("tasks"):
            print(f"   ✓ План: {len(plan.get('tasks', []))} задач, total_plan={plan.get('total_plan', 0)}")
        else:
            print("   ❌ План: нет задач")
        
        if fact.get("tasks"):
            print(f"   ✓ Факт: {len(fact.get('tasks', []))} задач, total_fact={fact.get('total_fact', 0)}")
        else:
            print("   ❌ Факт: нет задач")
        
        if photos_uf:
            print(f"   ✓ Фото в UF_SHIFT_PHOTOS: {len(photos_uf) if isinstance(photos_uf, list) else 1}")
        elif fact.get("photos"):
            print(f"   ⚠️  Фото только в fact_json.photos (Telegram file_id): {len(fact.get('photos', []))}")
        else:
            print("   ❌ Фото отсутствуют")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Главная функция."""
    if len(sys.argv) < 2:
        print("Использование: python scripts/check_shift.py <shift_id>")
        print()
        print("Пример:")
        print("  python scripts/check_shift.py 261")
        sys.exit(1)
    
    try:
        shift_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный ID смены: {sys.argv[1]}")
        print("   ID должен быть числом")
        sys.exit(1)
    
    await check_shift(shift_id)


if __name__ == "__main__":
    asyncio.run(main())

