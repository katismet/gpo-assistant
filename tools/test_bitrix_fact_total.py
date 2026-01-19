"""
Тест для проверки fact_total в Bitrix24.
Проверяет:
1. Есть ли смены с fact_total > 0
2. Правильно ли читается fact_total
3. Какие поля используются
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID
from app.bitrix_field_map import resolve_code, upper_to_camel


async def test_fact_total():
    """Проверить fact_total в Bitrix24."""
    print("=" * 60)
    print("ТЕСТ: Проверка fact_total в Bitrix24")
    print("=" * 60)
    
    # Получаем коды полей
    f_fact_code = resolve_code("Смена", "UF_FACT_TOTAL")
    f_fact_camel = upper_to_camel(f_fact_code)
    f_date_code = resolve_code("Смена", "UF_DATE")
    f_date_camel = upper_to_camel(f_date_code)
    f_status_code = resolve_code("Смена", "UF_STATUS")
    f_status_camel = upper_to_camel(f_status_code)
    
    print(f"\n1. Коды полей:")
    print(f"   UF_FACT_TOTAL: {f_fact_code}")
    print(f"   camelCase: {f_fact_camel}")
    print(f"   UF_DATE: {f_date_code} -> {f_date_camel}")
    print(f"   UF_STATUS: {f_status_code} -> {f_status_camel}")
    
    # Получаем последние 50 смен
    print(f"\n2. Получаем последние 50 смен из Bitrix24...")
    try:
        shifts_res = await bx("crm.item.list", {
            "entityTypeId": SHIFT_ETID,
            "select": [
                "id",
                f_date_camel,
                f_fact_camel,
                f_fact_code,
                f_status_camel,
                f_status_code,
                "ufCrm7UfCrmFactTotal",  # Прямой код
                "UF_CRM_7_UF_CRM_FACT_TOTAL",  # UPPER_CASE
                "*"
            ],
            "order": {"id": "desc"},
            "limit": 50
        })
        
        items = shifts_res.get("items", []) if isinstance(shifts_res, dict) else (shifts_res if isinstance(shifts_res, list) else [])
        print(f"   ✅ Найдено смен: {len(items)}")
        
        if not items:
            print("   ❌ Смены не найдены!")
            return
        
        # Анализируем смены
        print(f"\n3. Анализ смен:")
        shifts_with_fact = []
        shifts_without_fact = []
        
        for item in items:
            shift_id = item.get("id")
            
            # Пробуем разные варианты чтения fact_total
            fact_values = {}
            fact_values[f_fact_camel] = item.get(f_fact_camel)
            fact_values[f_fact_code] = item.get(f_fact_code)
            fact_values["ufCrm7UfCrmFactTotal"] = item.get("ufCrm7UfCrmFactTotal")
            fact_values["UF_CRM_7_UF_CRM_FACT_TOTAL"] = item.get("UF_CRM_7_UF_CRM_FACT_TOTAL")
            
            # Находим первое не-None значение
            fact_total = None
            fact_source = None
            for key, value in fact_values.items():
                if value is not None and value != "":
                    try:
                        fact_total = float(value)
                        fact_source = key
                        break
                    except (ValueError, TypeError):
                        continue
            
            if fact_total is None:
                fact_total = 0.0
                fact_source = "default (0)"
            
            # Получаем дату
            shift_date = item.get(f_date_camel) or item.get(f_date_code) or "не указана"
            
            # Получаем статус
            status = item.get(f_status_camel) or item.get(f_status_code) or ""
            
            if fact_total > 0:
                shifts_with_fact.append({
                    "id": shift_id,
                    "date": shift_date,
                    "fact_total": fact_total,
                    "source": fact_source,
                    "status": status
                })
            else:
                shifts_without_fact.append({
                    "id": shift_id,
                    "date": shift_date,
                    "fact_total": fact_total,
                    "source": fact_source,
                    "status": status
                })
        
        print(f"\n   📊 Статистика:")
        print(f"   - Смен с fact_total > 0: {len(shifts_with_fact)}")
        print(f"   - Смен с fact_total = 0: {len(shifts_without_fact)}")
        
        if shifts_with_fact:
            print(f"\n   ✅ Смены с фактическими данными (первые 10):")
            for shift in shifts_with_fact[:10]:
                print(f"      Смена #{shift['id']}: fact_total={shift['fact_total']}, "
                      f"дата={shift['date']}, статус='{shift['status']}', "
                      f"источник={shift['source']}")
        else:
            print(f"\n   ❌ НЕТ СМЕН С fact_total > 0!")
            print(f"\n   Первые 5 смен с fact_total=0:")
            for shift in shifts_without_fact[:5]:
                print(f"      Смена #{shift['id']}: fact_total={shift['fact_total']}, "
                      f"дата={shift['date']}, статус='{shift['status']}', "
                      f"источник={shift['source']}")
                # Показываем все значения полей для первой смены
                if shift['id'] == shifts_without_fact[0]['id']:
                    print(f"      Все значения fact_total для смены #{shift['id']}:")
                    for key, value in fact_values.items():
                        print(f"         {key} = {value} (type: {type(value).__name__})")
        
        # Проверяем одну смену детально через crm.item.get
        if items:
            test_shift_id = items[0].get("id")
            print(f"\n4. Детальная проверка смены #{test_shift_id} через crm.item.get:")
            try:
                shift_full = await bx("crm.item.get", {
                    "entityTypeId": SHIFT_ETID,
                    "id": test_shift_id
                })
                
                print(f"   Все поля, содержащие 'fact' или 'Fact':")
                for key, value in shift_full.items():
                    if "fact" in key.lower():
                        print(f"      {key} = {value} (type: {type(value).__name__})")
                
                # Проверяем конкретные поля
                print(f"\n   Проверка конкретных полей:")
                print(f"      {f_fact_camel} = {shift_full.get(f_fact_camel)}")
                print(f"      {f_fact_code} = {shift_full.get(f_fact_code)}")
                print(f"      ufCrm7UfCrmFactTotal = {shift_full.get('ufCrm7UfCrmFactTotal')}")
                print(f"      UF_CRM_7_UF_CRM_FACT_TOTAL = {shift_full.get('UF_CRM_7_UF_CRM_FACT_TOTAL')}")
                
            except Exception as e:
                print(f"   ❌ Ошибка при получении смены: {e}")
        
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_fact_total())

