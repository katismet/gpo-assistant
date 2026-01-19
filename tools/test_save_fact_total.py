"""
Тест для проверки сохранения fact_total в Bitrix24.
Проверяет, правильно ли сохраняется fact_total при обновлении смены.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from app.services.bitrix import bx_post
from app.services.bitrix_ids import SHIFT_ETID
from app.bitrix_field_map import resolve_code, upper_to_camel


async def test_save_fact_total():
    """Проверить сохранение fact_total в Bitrix24."""
    print("=" * 60)
    print("ТЕСТ: Проверка сохранения fact_total в Bitrix24")
    print("=" * 60)
    
    # Получаем коды полей
    f_fact_code = resolve_code("Смена", "UF_FACT_TOTAL")
    f_fact_camel = upper_to_camel(f_fact_code)
    f_eff_final_code = resolve_code("Смена", "UF_EFF_FINAL")
    f_eff_final_camel = upper_to_camel(f_eff_final_code)
    f_status_code = resolve_code("Смена", "UF_STATUS")
    f_status_camel = upper_to_camel(f_status_code)
    
    print(f"\n1. Коды полей для сохранения:")
    print(f"   UF_FACT_TOTAL: {f_fact_code} -> {f_fact_camel}")
    print(f"   UF_EFF_FINAL: {f_eff_final_code} -> {f_eff_final_camel}")
    print(f"   UF_STATUS: {f_status_code} -> {f_status_camel}")
    
    # Находим последнюю смену для теста
    print(f"\n2. Находим последнюю смену для теста...")
    from app.services.http_client import bx
    from app.services.bitrix_ids import SHIFT_ETID
    
    try:
        shifts_res = await bx("crm.item.list", {
            "entityTypeId": SHIFT_ETID,
            "select": ["id"],
            "order": {"id": "desc"},
            "limit": 1
        })
        
        items = shifts_res.get("items", []) if isinstance(shifts_res, dict) else (shifts_res if isinstance(shifts_res, list) else [])
        
        if not items:
            print("   ❌ Смены не найдены!")
            return
        
        test_shift_id = items[0].get("id")
        print(f"   ✅ Найдена смена #{test_shift_id}")
        
        # Получаем текущие значения
        print(f"\n3. Получаем текущие значения смены #{test_shift_id}...")
        shift_before = await bx("crm.item.get", {
            "entityTypeId": SHIFT_ETID,
            "id": test_shift_id
        })
        
        fact_before = shift_before.get(f_fact_camel) or shift_before.get(f_fact_code) or 0
        print(f"   fact_total до обновления: {fact_before}")
        
        # Пробуем сохранить test значение
        test_fact_value = 123.45
        print(f"\n4. Пробуем сохранить fact_total = {test_fact_value}...")
        
        # Пробуем разные варианты сохранения
        test_cases = [
            {
                "name": "Только camelCase",
                "fields": {
                    f_fact_camel: test_fact_value,
                }
            },
            {
                "name": "camelCase + eff_final + status",
                "fields": {
                    f_fact_camel: test_fact_value,
                    f_eff_final_camel: 95.5,
                    f_status_camel: "closed",
                }
            },
            {
                "name": "Прямой код ufCrm7UfCrmFactTotal",
                "fields": {
                    "ufCrm7UfCrmFactTotal": test_fact_value,
                }
            },
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n   Вариант {i}: {test_case['name']}")
            print(f"   Поля: {list(test_case['fields'].keys())}")
            
            try:
                result = await bx_post("crm.item.update", {
                    "entityTypeId": SHIFT_ETID,
                    "id": test_shift_id,
                    "fields": test_case["fields"]
                })
                
                if result.get("result"):
                    print(f"   ✅ Обновление успешно")
                    
                    # Проверяем, сохранилось ли значение
                    shift_after = await bx("crm.item.get", {
                        "entityTypeId": SHIFT_ETID,
                        "id": test_shift_id
                    })
                    
                    fact_after_camel = shift_after.get(f_fact_camel)
                    fact_after_code = shift_after.get(f_fact_code)
                    fact_after_direct = shift_after.get("ufCrm7UfCrmFactTotal")
                    
                    print(f"   Проверка после сохранения:")
                    print(f"      {f_fact_camel} = {fact_after_camel}")
                    print(f"      {f_fact_code} = {fact_after_code}")
                    print(f"      ufCrm7UfCrmFactTotal = {fact_after_direct}")
                    
                    if fact_after_camel == test_fact_value or fact_after_code == test_fact_value or fact_after_direct == test_fact_value:
                        print(f"   ✅✅✅ ЗНАЧЕНИЕ СОХРАНИЛОСЬ! Используйте этот вариант!")
                        # Восстанавливаем исходное значение
                        await bx_post("crm.item.update", {
                            "entityTypeId": SHIFT_ETID,
                            "id": test_shift_id,
                            "fields": {
                                f_fact_camel: fact_before,
                            }
                        })
                        return
                    else:
                        print(f"   ❌ Значение НЕ сохранилось")
                else:
                    print(f"   ❌ Ошибка обновления: {result}")
                    
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
                import traceback
                traceback.print_exc()
        
        # Восстанавливаем исходное значение
        print(f"\n5. Восстанавливаем исходное значение...")
        try:
            await bx_post("crm.item.update", {
                "entityTypeId": SHIFT_ETID,
                "id": test_shift_id,
                "fields": {
                    f_fact_camel: fact_before,
                }
            })
            print(f"   ✅ Восстановлено")
        except:
            pass
        
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_save_fact_total())







