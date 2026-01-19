"""Скрипт для тестирования поиска закрытых смен для ЛПА."""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date, timedelta
from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID, UF_OBJECT_LINK, UF_STATUS
from app.bitrix_field_map import resolve_code, upper_to_camel
from app.services.w6_alerts import _get_field_value
from app.services.objects import fetch_all_objects
from loguru import logger

logger.add("test_lpa_shifts.log", rotation="10 MB", level="DEBUG")


async def test_find_closed_shifts():
    """Тестирование поиска закрытых смен."""
    print("=" * 60)
    print("Тестирование поиска закрытых смен для ЛПА")
    print("=" * 60)
    
    # Получаем список объектов
    print("\n1. Получаем список объектов...")
    objs = await fetch_all_objects()
    print(f"   Найдено объектов: {len(objs)}")
    
    if not objs:
        print("   ❌ Объекты не найдены!")
        return
    
    # Получаем коды полей
    print("\n2. Получаем коды полей...")
    f_date = resolve_code("Смена", "UF_DATE")
    f_date_camel = upper_to_camel(f_date)
    f_plan_code = resolve_code("Смена", "UF_PLAN_TOTAL")
    f_fact_code = resolve_code("Смена", "UF_FACT_TOTAL")
    f_eff_code = resolve_code("Смена", "UF_EFF_FINAL")
    f_status_code = resolve_code("Смена", "UF_STATUS")
    f_status_camel = upper_to_camel(f_status_code)
    f_fact_camel = upper_to_camel(f_fact_code)
    f_plan_camel = upper_to_camel(f_plan_code)
    f_eff_camel = upper_to_camel(f_eff_code)
    
    print(f"   UF_DATE: {f_date} -> {f_date_camel}")
    print(f"   UF_FACT_TOTAL: {f_fact_code} -> {f_fact_camel}")
    print(f"   UF_STATUS: {f_status_code} -> {f_status_camel}")
    
    # Тестируем поиск для каждого объекта
    print("\n3. Ищем закрытые смены для каждого объекта...")
    today = date.today()
    found_shifts = []
    
    for obj in objs[:5]:  # Тестируем первые 5 объектов
        obj_id = obj.get("id")
        obj_name = obj.get("name", f"Объект #{obj_id}")
        print(f"\n   Объект: {obj_name} (ID: {obj_id})")
        
        # Ищем смены за последние 30 дней
        for days_ago in range(30):
            check_date = today - timedelta(days=days_ago)
            day_from = check_date.isoformat() + "T00:00:00"
            day_to = check_date.isoformat() + "T23:59:59"
            
            try:
                shifts_res = await bx("crm.item.list", {
                    "entityTypeId": SHIFT_ETID,
                    "filter": {
                        f">={f_date_camel}": day_from,
                        f"<={f_date_camel}": day_to,
                    },
                    "select": ["id", f_date_camel, UF_OBJECT_LINK, f_status_camel, f_plan_camel, f_fact_camel, f_eff_camel, "*"],
                    "order": {"id": "desc"},
                    "limit": 100
                })
                
                items = shifts_res.get("items", []) if isinstance(shifts_res, dict) else (shifts_res if isinstance(shifts_res, list) else [])
                
                if not items:
                    continue
                
                # Ищем смену с нужным объектом
                for item in items:
                    obj_link = item.get(UF_OBJECT_LINK)
                    if not obj_link:
                        continue
                    
                    # Извлекаем ID объекта
                    if isinstance(obj_link, list) and len(obj_link) > 0:
                        obj_str = obj_link[0]
                    elif isinstance(obj_link, str):
                        obj_str = obj_link
                    else:
                        continue
                    
                    # Парсим ID объекта
                    try:
                        if isinstance(obj_str, str) and obj_str.startswith("D_"):
                            obj_id_from_bitrix = int(obj_str[2:])
                        else:
                            obj_id_from_bitrix = int(obj_str)
                    except (ValueError, TypeError):
                        continue
                    
                    if obj_id_from_bitrix != obj_id:
                        continue
                    
                    bitrix_shift_id = item.get("id")
                    if not bitrix_shift_id:
                        continue
                    
                    # Читаем значения полей
                    plan_total = float(item.get(f_plan_camel) or item.get(f_plan_code) or item.get("ufCrm7UfCrmPlanTotal") or 0)
                    fact_total = float(item.get(f_fact_camel) or item.get(f_fact_code) or item.get("ufCrm7UfCrmFactTotal") or 0)
                    eff_final = float(item.get(f_eff_camel) or item.get(f_eff_code) or item.get("ufCrm7UfCrmEffFinal") or 0)
                    
                    # Проверяем статус
                    item_status = ""
                    try:
                        item_status = _get_field_value(item, f_status_camel) or _get_field_value(item, f_status_code) or ""
                        if isinstance(item_status, str):
                            item_status = item_status.lower().strip()
                    except:
                        item_status = ""
                    
                    # Проверяем, является ли смена закрытой
                    is_closed = (item_status in ("closed", "закрыта", "закрыто")) or (not item_status and fact_total > 0)
                    
                    if fact_total > 0 and is_closed:
                        print(f"      ✅ Найдена закрытая смена: ID={bitrix_shift_id}, дата={check_date}, факт={fact_total}, статус='{item_status}'")
                        found_shifts.append({
                            "object_id": obj_id,
                            "object_name": obj_name,
                            "shift_id": bitrix_shift_id,
                            "date": check_date,
                            "fact_total": fact_total,
                            "plan_total": plan_total,
                            "efficiency": eff_final,
                            "status": item_status
                        })
                        break
                
                if found_shifts and found_shifts[-1]["object_id"] == obj_id:
                    break  # Нашли смену для этого объекта, переходим к следующему
                    
            except Exception as e:
                logger.error(f"Error fetching shifts for {check_date}: {e}")
                continue
    
    # Выводим результаты
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    if found_shifts:
        print(f"\n✅ Найдено закрытых смен: {len(found_shifts)}")
        for shift in found_shifts:
            print(f"\n   Объект: {shift['object_name']} (ID: {shift['object_id']})")
            print(f"   Смена ID: {shift['shift_id']}")
            print(f"   Дата: {shift['date']}")
            print(f"   План: {shift['plan_total']}")
            print(f"   Факт: {shift['fact_total']}")
            print(f"   Эффективность: {shift['efficiency']}%")
            print(f"   Статус: {shift['status'] or 'не указан'}")
    else:
        print("\n❌ Закрытых смен не найдено!")
        print("\n   Возможные причины:")
        print("   1. Смены не закрыты в Bitrix24 (статус не 'closed')")
        print("   2. У смен нет фактических данных (UF_FACT_TOTAL = 0)")
        print("   3. Смены не привязаны к объектам")
        print("   4. Смены созданы более 30 дней назад")
    
    print("\n" + "=" * 60)


async def test_sync_bitrix():
    """Тестирование синхронизации с Bitrix24."""
    print("\n" + "=" * 60)
    print("Тестирование синхронизации с Bitrix24")
    print("=" * 60)
    
    try:
        # Проверяем подключение
        print("\n1. Проверяем подключение к Bitrix24...")
        result = await bx("crm.type.list", {})
        if result:
            print(f"   ✅ Подключение успешно! Найдено типов: {len(result)}")
        else:
            print("   ❌ Не удалось получить список типов")
            return
        
        # Проверяем смены
        print("\n2. Проверяем смены...")
        shifts_res = await bx("crm.item.list", {
            "entityTypeId": SHIFT_ETID,
            "select": ["id", "*"],
            "order": {"id": "desc"},
            "limit": 10
        })
        
        items = shifts_res.get("items", []) if isinstance(shifts_res, dict) else (shifts_res if isinstance(shifts_res, list) else [])
        print(f"   Найдено смен: {len(items)}")
        
        if items:
            print("\n   Последние смены:")
            for item in items[:5]:
                shift_id = item.get("id")
                print(f"      - Смена ID: {shift_id}")
        
        print("\n✅ Синхронизация работает корректно")
        
    except Exception as e:
        print(f"\n❌ Ошибка синхронизации: {e}")
        logger.error(f"Sync error: {e}", exc_info=True)


async def main():
    """Главная функция."""
    try:
        await test_find_closed_shifts()
        await test_sync_bitrix()
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        logger.error(f"Critical error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())







