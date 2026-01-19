"""Проверка готовности ЛПА - есть ли закрытые смены для тестирования."""

import asyncio
import sys
from pathlib import Path
from datetime import date

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.shift_repo import get_last_closed_shift
from app.services.objects import fetch_all_objects
from app.db import session_scope
from app.models import Shift, ShiftStatus
from loguru import logger

logger.add("check_lpa_ready.log", rotation="10 MB", level="DEBUG")


async def check_lpa_ready():
    """Проверка готовности ЛПА - есть ли закрытые смены."""
    print("=" * 60)
    print("Проверка готовности ЛПА")
    print("=" * 60)
    
    # 1. Проверяем объекты
    print("\n1. Проверяем объекты...")
    try:
        objs = await fetch_all_objects()
        print(f"   ✅ Найдено объектов: {len(objs)}")
        if objs:
            print("   Объекты:")
            for obj in objs[:10]:  # Показываем первые 10
                print(f"      - {obj.get('name', 'Без названия')} (ID: {obj.get('id')})")
            if len(objs) > 10:
                print(f"      ... и еще {len(objs) - 10} объектов")
    except Exception as e:
        print(f"   ❌ Ошибка получения объектов: {e}")
        return
    
    if not objs:
        print("   ⚠️  Объекты не найдены! Нужно создать объекты в Bitrix24.")
        return
    
    # 2. Проверяем закрытые смены в локальной БД
    print("\n2. Проверяем закрытые смены в локальной БД...")
    closed_shifts_local = []
    try:
        with session_scope() as s:
            shifts = s.query(Shift).filter(Shift.status == ShiftStatus.CLOSED)\
                     .order_by(Shift.id.desc()).limit(20).all()
            closed_shifts_local = shifts
            print(f"   ✅ Найдено закрытых смен: {len(shifts)}")
            
            if shifts:
                print("   Закрытые смены:")
                for sh in shifts[:10]:
                    obj_name = sh.object.name if sh.object else f"Объект #{sh.object_id}"
                    fact_total = sum(sh.fact_json.values()) if sh.fact_json else 0
                    print(f"      - Смена #{sh.id}: {obj_name} (объект {sh.object_id}), дата: {sh.date.strftime('%d.%m.%Y')}, факт: {fact_total}")
    except Exception as e:
        print(f"   ❌ Ошибка проверки локальной БД: {e}")
        logger.error(f"Error checking local DB: {e}", exc_info=True)
    
    # 3. Проверяем для каждого объекта
    print("\n3. Проверяем закрытые смены для каждого объекта...")
    objects_with_shifts = []
    
    for obj in objs[:20]:  # Проверяем первые 20 объектов
        obj_id = obj.get("id")
        obj_name = obj.get("name", f"Объект #{obj_id}")
        
        result = get_last_closed_shift(obj_id)
        if result:
            shift_id, shift_data = result
            fact_total = sum(shift_data.get("fact", {}).values()) if shift_data.get("fact") else 0
            objects_with_shifts.append({
                "obj_id": obj_id,
                "obj_name": obj_name,
                "shift_id": shift_id,
                "fact_total": fact_total,
                "date": shift_data.get("date", "Не указана")
            })
    
    if objects_with_shifts:
        print(f"   ✅ Найдено объектов с закрытыми сменами: {len(objects_with_shifts)}")
        print("\n   Объекты, для которых можно сгенерировать ЛПА:")
        for item in objects_with_shifts[:10]:
            print(f"      ✅ {item['obj_name']} (ID: {item['obj_id']})")
            print(f"         Смена #{item['shift_id']}, дата: {item['date']}, факт: {item['fact_total']}")
    else:
        print("   ❌ Закрытых смен не найдено ни для одного объекта")
    
    # 4. Итоговый вывод
    print("\n" + "=" * 60)
    print("ИТОГОВЫЙ РЕЗУЛЬТАТ")
    print("=" * 60)
    
    if objects_with_shifts:
        print(f"\n✅ ЛПА готов к тестированию!")
        print(f"   Найдено объектов с закрытыми сменами: {len(objects_with_shifts)}")
        print(f"\n   Можете сразу протестировать ЛПА для объектов:")
        for item in objects_with_shifts[:5]:
            print(f"      - {item['obj_name']} (ID: {item['obj_id']})")
        if len(objects_with_shifts) > 5:
            print(f"      ... и еще {len(objects_with_shifts) - 5} объектов")
    else:
        print("\n❌ ЛПА пока нельзя протестировать")
        print("   Причины:")
        if not closed_shifts_local:
            print("      - Нет закрытых смен в локальной БД")
        print("      - Нужно создать план, затем отчет, и закрыть смену")
        print("\n   Что делать:")
        print("      1. Создайте план для объекта")
        print("      2. Создайте отчет с фактическими данными")
        print("      3. Смена закроется автоматически")
        print("      4. После этого можно будет сгенерировать ЛПА")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(check_lpa_ready())
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        logger.error(f"Critical error: {e}", exc_info=True)
        sys.exit(1)







