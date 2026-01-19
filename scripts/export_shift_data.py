#!/usr/bin/env python3
"""
Скрипт для экспорта данных смены из Bitrix24.
Показывает все поля, начинающиеся с ufCrm7, особенно:
- ufCrm7UfPlanJson
- ufCrm7UfFactJson
- ufCrm7UfShiftPhotos

Использование:
    python scripts/export_shift_data.py <shift_id>
    
Пример:
    python scripts/export_shift_data.py 237
"""

import asyncio
import json
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID


async def export_shift_data(shift_id: int):
    """Экспортирует данные смены из Bitrix24."""
    print(f"🔍 Запрашиваю данные смены {shift_id} из Bitrix24...")
    print(f"   entityTypeId: {SHIFT_ETID}")
    print()
    
    try:
        # Запрашиваем данные смены
        result = await bx(
            "crm.item.get",
            {
                "entityTypeId": SHIFT_ETID,
                "id": shift_id,
            }
        )
        
        if not result:
            print(f"❌ Смена {shift_id} не найдена в Bitrix24")
            return
        
        # Извлекаем item
        item = result.get("item", result) if isinstance(result, dict) else result
        
        if not isinstance(item, dict):
            print(f"❌ Неожиданный формат ответа: {type(item)}")
            print(f"   Ответ: {result}")
            return
        
        print("=" * 80)
        print(f"📄 ДАННЫЕ СМЕНЫ {shift_id}")
        print("=" * 80)
        print()
        
        # Показываем основные поля
        print("📋 ОСНОВНЫЕ ПОЛЯ:")
        print(f"   ID: {item.get('id', 'N/A')}")
        print(f"   Title: {item.get('title', 'N/A')}")
        print(f"   StageId: {item.get('stageId', 'N/A')}")
        print()
        
        # Фильтруем и показываем все поля, начинающиеся с ufCrm7
        print("=" * 80)
        print("🔍 ПОЛЯ, НАЧИНАЮЩИЕСЯ С ufCrm7:")
        print("=" * 80)
        print()
        
        uf_crm7_fields = {}
        for key, value in item.items():
            if key.startswith("ufCrm7") or key.startswith("UF_CRM_7"):
                uf_crm7_fields[key] = value
        
        if not uf_crm7_fields:
            print("⚠️  Поля ufCrm7* не найдены!")
            print()
            print("Все доступные поля:")
            for key in sorted(item.keys()):
                if key.startswith("uf") or key.startswith("UF"):
                    print(f"   - {key}")
        else:
            for key in sorted(uf_crm7_fields.keys()):
                value = uf_crm7_fields[key]
                print(f"\n📌 {key}:")
                
                # Специальная обработка для JSON полей
                if "json" in key.lower() or "Json" in key:
                    print(f"   Тип: {type(value).__name__}")
                    if isinstance(value, str):
                        try:
                            parsed = json.loads(value)
                            print(f"   Формат: JSON строка")
                            print(f"   Содержимое:")
                            print(json.dumps(parsed, ensure_ascii=False, indent=6))
                        except json.JSONDecodeError:
                            print(f"   Формат: строка (не JSON)")
                            print(f"   Значение: {value[:200]}..." if len(str(value)) > 200 else f"   Значение: {value}")
                    elif isinstance(value, (dict, list)):
                        print(f"   Формат: объект/список")
                        print(f"   Содержимое:")
                        print(json.dumps(value, ensure_ascii=False, indent=6))
                    else:
                        print(f"   Значение: {value}")
                # Специальная обработка для фото
                elif "photo" in key.lower() or "Photo" in key:
                    print(f"   Тип: {type(value).__name__}")
                    if isinstance(value, list):
                        print(f"   Количество фото: {len(value)}")
                        for i, photo in enumerate(value, 1):
                            if isinstance(photo, dict):
                                print(f"   Фото {i}:")
                                print(f"      ID: {photo.get('id', 'N/A')}")
                                print(f"      DownloadUrl: {photo.get('downloadUrl', 'N/A')}")
                                print(f"      Name: {photo.get('name', 'N/A')}")
                            else:
                                print(f"   Фото {i}: {photo}")
                    else:
                        print(f"   Значение: {value}")
                else:
                    print(f"   Тип: {type(value).__name__}")
                    if isinstance(value, (dict, list)):
                        print(f"   Содержимое:")
                        print(json.dumps(value, ensure_ascii=False, indent=6))
                    else:
                        print(f"   Значение: {value}")
        
        print()
        print("=" * 80)
        print("📦 ПОЛНЫЙ JSON ОТВЕТ (для анализа):")
        print("=" * 80)
        print()
        
        # Сохраняем полный ответ в файл
        output_file = Path(f"shift_{shift_id}_export.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Полный JSON сохранён в файл: {output_file}")
        print()
        print("💡 Для анализа используйте:")
        print(f"   cat {output_file}")
        print(f"   или откройте файл в текстовом редакторе")
        print()
        
        # Показываем краткую сводку
        print("=" * 80)
        print("📊 СВОДКА:")
        print("=" * 80)
        print()
        
        plan_json = uf_crm7_fields.get("ufCrm7UfPlanJson") or uf_crm7_fields.get("UF_CRM_7_UF_PLAN_JSON")
        fact_json = uf_crm7_fields.get("ufCrm7UfFactJson") or uf_crm7_fields.get("UF_CRM_7_UF_FACT_JSON")
        photos = uf_crm7_fields.get("ufCrm7UfShiftPhotos") or uf_crm7_fields.get("UF_CRM_7_UF_SHIFT_PHOTOS")
        
        print(f"✅ UF_PLAN_JSON: {'Найдено' if plan_json else '❌ Отсутствует'}")
        if plan_json:
            if isinstance(plan_json, str):
                try:
                    parsed = json.loads(plan_json)
                    has_tasks = isinstance(parsed, dict) and "tasks" in parsed
                    print(f"   - Формат: JSON строка")
                    print(f"   - Имеет 'tasks': {has_tasks}")
                except:
                    print(f"   - Формат: строка (не валидный JSON)")
            elif isinstance(plan_json, dict):
                has_tasks = "tasks" in plan_json
                print(f"   - Формат: объект")
                print(f"   - Имеет 'tasks': {has_tasks}")
            else:
                print(f"   - Формат: {type(plan_json).__name__}")
        
        print(f"✅ UF_FACT_JSON: {'Найдено' if fact_json else '❌ Отсутствует'}")
        if fact_json:
            if isinstance(fact_json, str):
                try:
                    parsed = json.loads(fact_json)
                    has_tasks = isinstance(parsed, dict) and "tasks" in parsed
                    print(f"   - Формат: JSON строка")
                    print(f"   - Имеет 'tasks': {has_tasks}")
                except:
                    print(f"   - Формат: строка (не валидный JSON)")
            elif isinstance(fact_json, dict):
                has_tasks = "tasks" in fact_json
                print(f"   - Формат: объект")
                print(f"   - Имеет 'tasks': {has_tasks}")
            else:
                print(f"   - Формат: {type(fact_json).__name__}")
        
        print(f"✅ UF_SHIFT_PHOTOS: {'Найдено' if photos else '❌ Отсутствует'}")
        if photos:
            if isinstance(photos, list):
                print(f"   - Формат: список")
                print(f"   - Количество: {len(photos)}")
            else:
                print(f"   - Формат: {type(photos).__name__}")
        
    except Exception as e:
        print(f"❌ Ошибка при запросе данных: {e}")
        import traceback
        traceback.print_exc()
        return


async def main():
    """Главная функция."""
    if len(sys.argv) < 2:
        print("Использование: python scripts/export_shift_data.py <shift_id>")
        print()
        print("Пример:")
        print("  python scripts/export_shift_data.py 237")
        sys.exit(1)
    
    try:
        shift_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный ID смены: {sys.argv[1]}")
        print("   ID должен быть числом")
        sys.exit(1)
    
    await export_shift_data(shift_id)


if __name__ == "__main__":
    asyncio.run(main())





