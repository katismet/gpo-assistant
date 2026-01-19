"""Тест создания ресурса с правильным enum."""
import asyncio
from app.services.resource_client import bitrix_add_resource
from app.services.http_client import bx
from app.services.bitrix_ids import RESOURCE_ETID
from app.bitrix_field_map import resolve_code, upper_to_camel

async def main():
    # Создаем тестовый ресурс
    resource_data = {
        "shift_id": 491,
        "resource_type": "MAT",
        "mat_type": "Тестовый материал",
        "mat_qty": 1,
        "mat_unit": "шт",
        "mat_price": 100,
    }
    
    print("Создаем ресурс с resource_type='MAT'...")
    result = await bitrix_add_resource(resource_data)
    
    if isinstance(result, dict) and "result" in result:
        res_id = result["result"].get("item", {}).get("id")
        if res_id:
            print(f"Ресурс создан: ID={res_id}")
            
            # Проверяем, что записалось
            check = await bx('crm.item.get', {
                'entityTypeId': RESOURCE_ETID,
                'id': res_id,
                'select': ['id', 'ufCrm9UfResourceType', 'ufCrm9UfMatType']
            })
            
            item = check.get('item', check)
            print(f"UF_RESOURCE_TYPE после создания: {item.get('ufCrm9UfResourceType')}")
            print(f"Тип: {type(item.get('ufCrm9UfResourceType'))}")
            print(f"Материал: {item.get('ufCrm9UfMatType')}")
        else:
            print(f"Ошибка: ресурс не создан. Результат: {result}")
    else:
        print(f"Ошибка: неожиданный формат результата: {result}")

if __name__ == "__main__":
    asyncio.run(main())



