#!/usr/bin/env python3
"""Проверка полей смены в Bitrix24, особенно поля для фото."""

import sys
import asyncio
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx


async def check_shift_fields():
    """Проверяет поля смены и ищет поле для фото."""
    print("🔍 Проверяю поля смены (entityTypeId=1050)...")
    print()
    
    try:
        result = await bx("crm.item.fields", {"entityTypeId": 1050})
        
        if not result:
            print("❌ Не удалось получить поля")
            return
        
        # Ищем все поля, начинающиеся с ufCrm7
        photo_fields = []
        all_uf_fields = []
        
        fields = result.get("fields", result) if isinstance(result, dict) else result
        
        if not isinstance(fields, dict):
            print(f"⚠️  Неожиданный формат ответа: {type(fields)}")
            print(f"   Ответ: {result}")
            return
        
        print(f"📋 Найдено полей: {len(fields)}")
        print()
        
        for field_name, field_data in fields.items():
            if not isinstance(field_data, dict):
                continue
            
            # Ищем поля ufCrm7
            if field_name.startswith("ufCrm7") or field_name.startswith("UF_CRM_7"):
                field_type = field_data.get("type", "unknown")
                field_title = field_data.get("title", field_name)
                is_multiple = field_data.get("multiple", False)
                
                all_uf_fields.append({
                    "name": field_name,
                    "type": field_type,
                    "title": field_title,
                    "multiple": is_multiple,
                })
                
                # Ищем поле для фото
                if "photo" in field_name.lower() or "фото" in field_title.lower() or "file" in field_type.lower():
                    photo_fields.append({
                        "name": field_name,
                        "type": field_type,
                        "title": field_title,
                        "multiple": is_multiple,
                    })
        
        print("📸 Поля, связанные с фото:")
        if photo_fields:
            for pf in photo_fields:
                print(f"   ✓ {pf['name']}")
                print(f"     Тип: {pf['type']}, Множественное: {pf['multiple']}")
                print(f"     Название: {pf['title']}")
                print()
        else:
            print("   ❌ Поле для фото не найдено")
            print()
        
        print("📋 Все поля ufCrm7:")
        for uf in all_uf_fields:
            print(f"   • {uf['name']} ({uf['type']}, multiple={uf['multiple']}) - {uf['title']}")
        
        print()
        print("💡 Рекомендации:")
        if not photo_fields:
            print("   1. Создайте поле в Bitrix24:")
            print("      Смарт-процессы → Смена → Поля → Добавить")
            print("      Тип: Файл, Множественное: Да, Название: Фото смены")
            print()
        
        # Сохраняем результат в файл для анализа
        output_file = Path("shift_fields_output.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(fields, f, ensure_ascii=False, indent=2)
        print(f"💾 Полный список полей сохранен в: {output_file}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_shift_fields())





