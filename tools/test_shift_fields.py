"""
Тест для проверки всех полей смены в Bitrix24.
Показывает все поля смены, чтобы найти правильное имя для fact_total.
"""

import asyncio
import sys
import json
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID


async def test_shift_fields():
    """Проверить все поля смены в Bitrix24."""
    print("=" * 60)
    print("ТЕСТ: Проверка всех полей смены в Bitrix24")
    print("=" * 60)
    
    # Находим последнюю смену
    print(f"\n1. Находим последнюю смену...")
    try:
        shifts_res = await bx("crm.item.list", {
            "entityTypeId": SHIFT_ETID,
            "select": ["id", "*"],
            "order": {"id": "desc"},
            "limit": 1
        })
        
        items = shifts_res.get("items", []) if isinstance(shifts_res, dict) else (shifts_res if isinstance(shifts_res, list) else [])
        
        if not items:
            print("   ❌ Смены не найдены!")
            return
        
        test_shift_id = items[0].get("id")
        print(f"   ✅ Найдена смена #{test_shift_id}")
        
        # Получаем полные данные через crm.item.get
        print(f"\n2. Получаем все поля смены #{test_shift_id}...")
        shift_full = await bx("crm.item.get", {
            "entityTypeId": SHIFT_ETID,
            "id": test_shift_id
        })
        
        print(f"   ✅ Получено полей: {len(shift_full)}")
        
        # Ищем все поля, связанные с fact, plan, eff
        print(f"\n3. Поля, содержащие 'fact', 'plan', 'eff', 'total':")
        relevant_fields = {}
        for key, value in shift_full.items():
            key_lower = key.lower()
            if any(word in key_lower for word in ['fact', 'plan', 'eff', 'total', 'volume', 'объем']):
                relevant_fields[key] = value
        
        if relevant_fields:
            for key, value in sorted(relevant_fields.items()):
                print(f"   {key} = {value} (type: {type(value).__name__})")
        else:
            print("   ❌ Не найдено релевантных полей")
        
        # Показываем все поля (первые 50)
        print(f"\n4. Все поля смены (первые 50):")
        for i, (key, value) in enumerate(list(shift_full.items())[:50], 1):
            value_str = str(value)
            if len(value_str) > 50:
                value_str = value_str[:50] + "..."
            print(f"   {i}. {key} = {value_str} (type: {type(value).__name__})")
        
        if len(shift_full) > 50:
            print(f"   ... и еще {len(shift_full) - 50} полей")
        
        # Сохраняем в файл для детального анализа
        output_file = Path("tools") / "shift_fields_dump.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(shift_full, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n5. Полный дамп сохранен в: {output_file}")
        
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_shift_fields())







