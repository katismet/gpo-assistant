"""
Тест для прямого обновления fact_total в Bitrix24.
Проверяет, сохраняется ли значение при разных способах обновления.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from app.services.bitrix import bx_post
from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID


async def test_update_fact_direct():
    """Прямое обновление fact_total в Bitrix24."""
    print("=" * 60)
    print("ТЕСТ: Прямое обновление fact_total в Bitrix24")
    print("=" * 60)
    
    # Находим последнюю смену
    print(f"\n1. Находим последнюю смену...")
    shifts_res = await bx("crm.item.list", {
        "entityTypeId": SHIFT_ETID,
        "select": ["id"],
        "order": {"id": "desc"},
        "limit": 1
    })
    
    items = shifts_res.get("items", []) if isinstance(shifts_res, dict) else (shifts_res if isinstance(shifts_res, list) else [])
    test_shift_id = items[0].get("id")
    print(f"   ✅ Найдена смена #{test_shift_id}")
    
    # Получаем текущие значения
    print(f"\n2. Получаем текущие значения...")
    shift_before = await bx("crm.item.get", {
        "entityTypeId": SHIFT_ETID,
        "id": test_shift_id
    })
    
    item_before = shift_before.get("item", shift_before)
    fact_before = item_before.get("ufCrm7UfCrmFactTotal", 0)
    eff_before = item_before.get("ufCrm7UfCrmEffFinal")
    
    print(f"   fact_total до: {fact_before}")
    print(f"   eff_final до: {eff_before}")
    
    # Пробуем обновить с разными значениями
    test_value = 999.99
    print(f"\n3. Пробуем сохранить fact_total = {test_value}...")
    
    try:
        result = await bx_post("crm.item.update", {
            "entityTypeId": SHIFT_ETID,
            "id": test_shift_id,
            "fields": {
                "ufCrm7UfCrmFactTotal": test_value,
                "ufCrm7UfCrmEffFinal": 95.5,
                "ufCrm7UfCrmStatus": "closed",
            }
        })
        
        print(f"   Результат обновления: {result}")
        
        # Проверяем сразу после обновления
        print(f"\n4. Проверяем сразу после обновления...")
        shift_after = await bx("crm.item.get", {
            "entityTypeId": SHIFT_ETID,
            "id": test_shift_id
        })
        
        item_after = shift_after.get("item", shift_after)
        fact_after = item_after.get("ufCrm7UfCrmFactTotal")
        eff_after = item_after.get("ufCrm7UfCrmEffFinal")
        status_after = item_after.get("ufCrm7UfCrmStatus")
        
        print(f"   fact_total после: {fact_after} (ожидалось: {test_value})")
        print(f"   eff_final после: {eff_after} (ожидалось: 95.5)")
        print(f"   status после: {status_after} (ожидалось: 'closed')")
        
        if fact_after == test_value:
            print(f"   ✅✅✅ fact_total СОХРАНИЛОСЬ!")
        else:
            print(f"   ❌ fact_total НЕ сохранилось")
            print(f"   Все поля смены после обновления:")
            for key, value in sorted(item_after.items()):
                if "fact" in key.lower() or "eff" in key.lower() or "status" in key.lower():
                    print(f"      {key} = {value}")
        
        # Восстанавливаем исходные значения
        print(f"\n5. Восстанавливаем исходные значения...")
        await bx_post("crm.item.update", {
            "entityTypeId": SHIFT_ETID,
            "id": test_shift_id,
            "fields": {
                "ufCrm7UfCrmFactTotal": fact_before,
                "ufCrm7UfCrmEffFinal": eff_before,
            }
        })
        print(f"   ✅ Восстановлено")
        
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_update_fact_direct())







