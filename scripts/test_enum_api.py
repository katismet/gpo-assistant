"""Тест API методов для получения enum значений."""
import asyncio
from app.services.http_client import bx
from app.services.bitrix_ids import RESOURCE_ETID, SHIFT_ETID

async def main():
    print("=== Тест получения enum значений ===\n")
    
    # Тест 1: crm.item.userfield.get для Ресурса
    print("1. Тест crm.item.userfield.get для UF_RESOURCE_TYPE (Ресурс):")
    try:
        resp1 = await bx('crm.item.userfield.get', {
            'entityTypeId': RESOURCE_ETID,
            'fieldName': 'ufCrm9UfResourceType',
        })
        print(f"   Результат: {resp1}")
        if 'result' in resp1 or 'LIST' in resp1:
            print("   ✓ Метод работает")
        else:
            print("   ✗ Метод не вернул ожидаемые данные")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
    
    print()
    
    # Тест 2: crm.item.userfield.get для Смены (UF_SHIFT_TYPE)
    print("2. Тест crm.item.userfield.get для UF_SHIFT_TYPE (Смена):")
    try:
        resp2 = await bx('crm.item.userfield.get', {
            'entityTypeId': SHIFT_ETID,
            'fieldName': 'ufCrm7UfCrmShiftType',
        })
        print(f"   Результат: {resp2}")
        if 'result' in resp2 or 'LIST' in resp2:
            print("   ✓ Метод работает")
        else:
            print("   ✗ Метод не вернул ожидаемые данные")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
    
    print()
    
    # Тест 3: Альтернативный метод - получить через существующую запись
    print("3. Тест получения enum через существующую запись ресурса:")
    try:
        res_list = await bx('crm.item.list', {
            'entityTypeId': RESOURCE_ETID,
            'filter': {'ufCrm9UfShiftId': 491},
            'select': ['id', 'ufCrm9UfResourceType'],
            'limit': 5
        })
        print(f"   Найдено ресурсов: {len(res_list.get('items', []))}")
        for item in res_list.get('items', [])[:3]:
            print(f"   Ресурс {item.get('id')}: UF_RESOURCE_TYPE = {item.get('ufCrm9UfResourceType')} (тип: {type(item.get('ufCrm9UfResourceType'))})")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())



