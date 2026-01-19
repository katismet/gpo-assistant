"""Демонстрационный скрипт для заказчика - полный прогон ГПО flow.

Скрипт выполняет полный цикл:
1. Создание/получение смены
2. Сохранение плана (2-3 задачи)
3. Добавление нескольких строк табеля и ресурсов
4. Генерация ЛПА

Выводит в консоль ключевые значения и путь к сгенерированному ЛПА.
"""

import asyncio
import logging
from datetime import date
from pathlib import Path

from app.services.shift_client import bitrix_get_shift_for_object_and_date
from app.services.resource_client import bitrix_add_resource
from app.services.lpa_generator import generate_lpa_for_shift
from app.services.objects import fetch_all_objects
from app.telegram.flow_plan import save_plan_to_bitrix
from app.services.http_client import bx as bx_client
from app.bitrix_field_map import resolve_code, upper_to_camel
from app.services.bitrix_ids import TIMESHEET_ETID, SHIFT_ETID
from app.services.bitrix_files import upload_docx_to_bitrix_field

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("demo.customer")


async def demo_run():
    """Выполняет демонстрационный прогон ГПО flow."""
    
    print("=" * 80)
    print("=== ДЕМОНСТРАЦИОННЫЙ ПРОГОН ГПО ===")
    print("=" * 80)
    print()
    
    # 1. Используем фиксированный объект 13 и дату 17.11.2025 для работы со сменой 491
    print("[1] Загрузка объектов из Bitrix24...")
    objects = await fetch_all_objects()
    if not objects:
        print("[ERROR] Ошибка: объекты не загружены")
        return
    
    # Ищем объект с ID 13, если не найден - используем первый
    object_id = 13
    object_title = None
    for obj_id, obj_title, *_ in objects:
        if obj_id == 13:
            object_id = obj_id
            object_title = obj_title
            break
    
    if not object_title:
        # Если объект 13 не найден, используем первый
        object_id, object_title, *_ = objects[0]
        print(f"   [WARN] Объект 13 не найден, используем первый: {object_id}")
    
    # Фиксированная дата 17.11.2025 для работы со сменой 491
    work_date = date(2025, 11, 17)
    
    print(f"   [OK] Выбран объект: {object_id} - {object_title}")
    print(f"   [OK] Дата: {work_date} (фиксированная для смены 491)")
    print()
    
    # 2. Создаём/получаем смену
    print("[2] Создание/получение смены...")
    shift_id, shift_meta = await bitrix_get_shift_for_object_and_date(
        object_bitrix_id=object_id,
        target_date=work_date,
        create_if_not_exists=True
    )
    
    if not shift_id:
        print("❌ Ошибка: не удалось создать или получить смену")
        return
    
    print(f"   [OK] Смена получена: shift_bitrix_id={shift_id}")
    print()
    
    # 3. Сохраняем план
    print("[3] Сохранение плана...")
    plan_tasks = [
        {"name": "Земляные работы", "plan": 150, "unit": "м³"},
        {"name": "Подушка", "plan": 100, "unit": "м³"},
        {"name": "Укладка асфальта", "plan": 50, "unit": "м²"},
    ]
    
    meta = {
        "date": work_date.strftime("%d.%m.%Y"),
        "shift_type": "day",
        "section": "Строительство",
        "foreman": "Прораб",
        "object_bitrix_id": object_id,
        "object_name": object_title,
    }
    
    try:
        await save_plan_to_bitrix(
            shift_id=shift_id,
            plan_tasks=plan_tasks,
            meta=meta,
            bx=bx_client
        )
        plan_total = sum(t["plan"] for t in plan_tasks)
        print(f"   [OK] План сохранён: {len(plan_tasks)} задач, total_plan={plan_total}")
    except Exception as e:
        print(f"   [ERROR] Ошибка сохранения плана: {e}")
        return
    print()
    
    # 4. Добавляем табель
    print("[4] Добавление табеля...")
    f_shift_id = resolve_code("Табель", "UF_SHIFT_ID")
    f_worker = resolve_code("Табель", "UF_WORKER")
    f_hours = resolve_code("Табель", "UF_HOURS")
    f_rate = resolve_code("Табель", "UF_RATE")
    
    timesheet_entries = [
        {"worker": "Бригада А", "hours": 8.0, "rate": 1000.0},
        {"worker": "Бригада Б", "hours": 6.0, "rate": 1200.0},
        {"worker": "Бригада В", "hours": 4.0, "rate": 1100.0},
    ]
    
    timesheet_ids = []
    for entry in timesheet_entries:
        try:
            fields = {
                "TITLE": f"{entry['worker']} / {entry['hours']} ч",
                upper_to_camel(f_shift_id): shift_id,
                upper_to_camel(f_worker): entry["worker"],
                upper_to_camel(f_hours): entry["hours"],
                upper_to_camel(f_rate): entry["rate"],
            }
            
            result = await bx_client("crm.item.add", {
                "entityTypeId": TIMESHEET_ETID,
                "fields": fields
            })
            
            ts_id = result.get("item", {}).get("id") if isinstance(result, dict) else None
            if ts_id:
                timesheet_ids.append(ts_id)
                print(f"   [OK] Табель добавлен: {entry['worker']}, {entry['hours']} ч (id={ts_id})")
        except Exception as e:
            print(f"   [WARN] Ошибка добавления табеля {entry['worker']}: {e}")
    
    fact_total = sum(e["hours"] for e in timesheet_entries)
    print(f"   [OK] Всего добавлено записей табеля: {len(timesheet_ids)}, сумма часов: {fact_total}")
    print()
    
    # 5. Добавляем ресурсы
    print("[5] Добавление ресурсов...")
    resource_entries = [
        {"type": "MAT", "mat_type": "Песок", "mat_qty": 20, "mat_unit": "т", "mat_price": 500},
        {"type": "MAT", "mat_type": "Щебень", "mat_qty": 15, "mat_unit": "т", "mat_price": 600},
        {"type": "EQUIP", "equip_type": "Экскаватор", "equip_hours": 8, "equip_rate": 2000},
    ]
    
    resource_ids = []
    for entry in resource_entries:
        try:
            resource_data = {
                "shift_id": shift_id,
                "resource_type": entry["type"],
            }
            if entry["type"] == "MAT":
                resource_data.update({
                    "mat_type": entry["mat_type"],
                    "mat_qty": entry["mat_qty"],
                    "mat_unit": entry["mat_unit"],
                    "mat_price": entry["mat_price"],
                })
            else:
                resource_data.update({
                    "equip_type": entry["equip_type"],
                    "equip_hours": entry["equip_hours"],
                    "equip_rate": entry["equip_rate"],
                })
            
            result = await bitrix_add_resource(resource_data)
            res_id = result.get("result", {}).get("item", {}).get("id") if isinstance(result, dict) else None
            if res_id:
                resource_ids.append(res_id)
                res_name = entry.get("mat_type") or entry.get("equip_type")
                print(f"   [OK] Ресурс добавлен: {res_name} (id={res_id})")
        except Exception as e:
            print(f"   [WARN] Ошибка добавления ресурса: {e}")
    
    print(f"   [OK] Всего добавлено ресурсов: {len(resource_ids)}")
    print()
    
    # 6. Генерируем ЛПА
    print("[6] Генерация ЛПА...")
    try:
        result = await generate_lpa_for_shift(
            shift_bitrix_id=shift_id,
            fallback_plan=None,
            fallback_fact=None,
            meta=None,
        )
        pdf_path = result.pdf_path
        lpa_context = result.context
        
        print(f"   [OK] ЛПА сгенерирован: {pdf_path}")
        print(f"   [OK] Размер файла: {pdf_path.stat().st_size / 1024:.2f} KB")

        uploaded = await upload_docx_to_bitrix_field(
            file_path=str(pdf_path),
            entity_type_id=SHIFT_ETID,
            item_id=shift_id,
            field_logical_name="UF_PDF_FILE",
            entity_ru_name="Смена",
        )
        print(f"   [OK] Файл загружен в Bitrix: {uploaded}")
    except Exception as e:
        print(f"   [ERROR] Ошибка генерации ЛПА: {e}")
        import traceback
        traceback.print_exc()
        return
    print()
    
    # 7. Выводим итоговую сводку
    print("=" * 80)
    print("=== ИТОГОВАЯ СВОДКА ===")
    print("=" * 80)
    print(f"Объект:")
    print(f"  - object_bitrix_id: {object_id}")
    print(f"  - object_name: {object_title}")
    print()
    print(f"Смена:")
    print(f"  - shift_bitrix_id: {shift_id}")
    print(f"  - date: {work_date}")
    print()
    print(f"План:")
    print(f"  - plan_total: {plan_total}")
    print(f"  - tasks_count: {len(plan_tasks)}")
    print()
    print(f"Факт:")
    print(f"  - fact_total: {fact_total} (сумма часов из табеля)")
    print(f"  - timesheet_count: {len(timesheet_ids)}")
    print()
    print(f"Ресурсы:")
    print(f"  - resource_count: {len(resource_ids)}")
    print()
    print(f"ЛПА:")
    print(f"  - pdf_path: {pdf_path}")
    if lpa_context:
        print(f"  - plan_total в ЛПА: {lpa_context.get('plan_total', 0)}")
        print(f"  - fact_total в ЛПА: {lpa_context.get('fact_total', 0)}")
    print()
    print("=" * 80)
    print("=== ДЕМОНСТРАЦИОННЫЙ ПРОГОН ЗАВЕРШЁН УСПЕШНО ===")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(demo_run())


