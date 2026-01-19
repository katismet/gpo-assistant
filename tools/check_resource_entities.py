"""Проверка доступных типов CRM в Bitrix24."""

import asyncio
from app.services.bitrix import bx_get

async def check_entities():
    try:
        result = await bx_get('crm.type.list')
        print('Доступные типы CRM:')
        for item in result.get('result', []):
            entity_id = item.get('entityTypeId')
            title = item.get('title')
            print(f'ID: {entity_id}, Название: {title}')
            
        # Ищем подходящие для ресурсов
        print('\nПоиск подходящих для ресурсов:')
        for item in result.get('result', []):
            title = item.get('title', '').lower()
            if any(word in title for word in ['ресурс', 'resource', 'техника', 'материал']):
                print(f'НАЙДЕН: ID: {item.get("entityTypeId")}, Название: {item.get("title")}')
                
    except Exception as e:
        print(f'Ошибка: {e}')

if __name__ == "__main__":
    asyncio.run(check_entities())

