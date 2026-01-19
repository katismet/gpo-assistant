#!/usr/bin/env python3
"""Тест извлечения объекта и генерации ЛПА."""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID, OBJECT_ETID
from app.services.lpa_data import collect_lpa_data
from app.services.lpa_pdf import render_lpa_docx, docx_to_pdf


async def test_object_extraction(shift_id: int):
    """Тест извлечения объекта из смены."""
    print("=" * 70)
    print("ТЕСТ 1: Извлечение объекта из смены")
    print("=" * 70)
    print()
    
    # Тест 1: crm.item.get
    print("📋 Тест 1.1: crm.item.get")
    try:
        result1 = await bx("crm.item.get", {
            "entityTypeId": SHIFT_ETID,
            "id": shift_id
        })
        item1 = result1.get("item", result1) if isinstance(result1, dict) else result1
        obj_field1 = item1.get("ufCrm7UfCrmObject") if item1 else None
        print(f"   Результат: {obj_field1} (тип: {type(obj_field1)})")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        obj_field1 = None
    
    print()
    
    # Тест 2: crm.item.get с select
    print("📋 Тест 1.2: crm.item.get с select")
    try:
        result2 = await bx("crm.item.get", {
            "entityTypeId": SHIFT_ETID,
            "id": shift_id,
            "select": ["ufCrm7UfCrmObject"]
        })
        item2 = result2.get("item", result2) if isinstance(result2, dict) else result2
        obj_field2 = item2.get("ufCrm7UfCrmObject") if item2 else None
        print(f"   Результат: {obj_field2} (тип: {type(obj_field2)})")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        obj_field2 = None
    
    print()
    
    # Тест 3: crm.item.list
    print("📋 Тест 1.3: crm.item.list")
    try:
        result3 = await bx("crm.item.list", {
            "entityTypeId": SHIFT_ETID,
            "filter": {"id": shift_id},
            "select": ["id", "ufCrm7UfCrmObject"]
        })
        items3 = result3.get("items", []) if isinstance(result3, dict) else result3
        if items3 and len(items3) > 0:
            item3 = items3[0]
            obj_field3 = item3.get("ufCrm7UfCrmObject")
            print(f"   Результат: {obj_field3} (тип: {type(obj_field3)})")
        else:
            print(f"   ❌ Смена не найдена")
            obj_field3 = None
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        obj_field3 = None
    
    print()
    
    # Извлекаем ID объекта из всех результатов
    obj_id = None
    for i, obj_field in enumerate([obj_field1, obj_field2, obj_field3], 1):
        if not obj_field or obj_field == "Array":
            continue
        
        print(f"📋 Тест 1.{i+3}: Извлечение ID из результата {i}")
        try:
            if isinstance(obj_field, list) and obj_field:
                obj_str = obj_field[0]
                print(f"   Элемент списка: {obj_str} (тип: {type(obj_str)})")
            elif isinstance(obj_field, str):
                obj_str = obj_field
                print(f"   Строка: {obj_str}")
            else:
                obj_str = obj_field
                print(f"   Другое: {obj_str} (тип: {type(obj_str)})")
            
            if isinstance(obj_str, str):
                if obj_str.startswith("D_"):
                    obj_id = int(obj_str[2:])
                    print(f"   ✅ Извлечен ID: {obj_id}")
                    break
                else:
                    try:
                        obj_id = int(obj_str)
                        print(f"   ✅ Извлечен ID (число): {obj_id}")
                        break
                    except ValueError:
                        pass
            elif isinstance(obj_str, (int, float)):
                obj_id = int(obj_str)
                print(f"   ✅ Извлечен ID (число): {obj_id}")
                break
        except Exception as e:
            print(f"   ❌ Ошибка извлечения: {e}")
        print()
    
    # Получаем название объекта
    if obj_id:
        print(f"📋 Тест 1.7: Получение названия объекта {obj_id}")
        try:
            obj_data = await bx("crm.item.get", {
                "entityTypeId": OBJECT_ETID,
                "id": obj_id
            })
            if obj_data:
                obj_item = obj_data.get("item", obj_data)
                obj_title = obj_item.get("title") or obj_item.get("TITLE") or f"Объект #{obj_id}"
                print(f"   ✅ Название объекта: {obj_title}")
                return obj_title
            else:
                print(f"   ❌ Объект {obj_id} не найден")
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
    else:
        print("   ❌ Не удалось извлечь ID объекта")
    
    return None


async def test_lpa_generation(shift_id: int):
    """Тест генерации ЛПА."""
    print()
    print("=" * 70)
    print("ТЕСТ 2: Генерация ЛПА")
    print("=" * 70)
    print()
    
    print("📊 Собираю данные из Bitrix24...")
    context, photos = await collect_lpa_data(
        shift_bitrix_id=shift_id,
        fallback_plan=None,
        fallback_fact=None,
        meta=None,
    )
    
    object_name = context.get("object_name", "Не указан")
    plan_total = context.get("plan_total", 0)
    fact_total = context.get("fact_total", 0)
    tasks_count = len(context.get("tasks", []))
    
    print(f"✅ Данные собраны:")
    print(f"   - Объект: {object_name}")
    print(f"   - Задач: {tasks_count}")
    print(f"   - План: {plan_total}")
    print(f"   - Факт: {fact_total}")
    print(f"   - Фото: {len(photos)}")
    print()
    
    # Проверяем шаблон
    template_path = Path("app/templates/pdf/lpa_template.docx")
    if not template_path.exists():
        print(f"❌ Шаблон не найден: {template_path}")
        return False
    
    # Создаем выходную директорию
    output_dir = Path("output/pdf")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("📝 Генерирую DOCX...")
    try:
        docx_path = render_lpa_docx(
            template_path=template_path,
            data=context,
            out_dir=output_dir,
            filename_prefix="LPA_TEST",
            photos=photos,
            max_photos_in_doc=5,
        )
        
        if docx_path.exists():
            print(f"✅ DOCX создан: {docx_path}")
            
            # Проверяем название файла
            file_name = docx_path.name
            if "Не указан" in file_name:
                print(f"⚠️  В названии файла все еще 'Не указан': {file_name}")
                return False
            elif object_name != "Не указан" and object_name in file_name:
                print(f"✅ Название объекта в файле: {object_name}")
                return True
            else:
                print(f"⚠️  Название файла: {file_name}")
                return object_name != "Не указан"
        else:
            print(f"❌ Файл DOCX не был создан")
            return False
    except Exception as e:
        print(f"❌ Ошибка генерации: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Главная функция."""
    if len(sys.argv) < 2:
        print("Использование: python scripts/test_lpa_object.py <SHIFT_ID>")
        print()
        print("Пример:")
        print("  python scripts/test_lpa_object.py 297")
        sys.exit(1)
    
    try:
        shift_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный ID смены: {sys.argv[1]}")
        sys.exit(1)
    
    print()
    print("🧪 ТЕСТ ИЗВЛЕЧЕНИЯ ОБЪЕКТА И ГЕНЕРАЦИИ ЛПА")
    print()
    
    # Тест 1: Извлечение объекта
    object_name = await test_object_extraction(shift_id)
    
    # Тест 2: Генерация ЛПА
    lpa_success = await test_lpa_generation(shift_id)
    
    print()
    print("=" * 70)
    print("ИТОГИ ТЕСТА")
    print("=" * 70)
    print()
    
    if object_name and object_name != "Не указан":
        print(f"✅ Объект извлечен: {object_name}")
    else:
        print(f"❌ Объект не извлечен (получено: {object_name})")
    
    if lpa_success:
        print(f"✅ ЛПА сгенерирован успешно")
    else:
        print(f"❌ ЛПА не сгенерирован или объект не в названии файла")
    
    print()


if __name__ == "__main__":
    asyncio.run(main())





