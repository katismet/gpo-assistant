#!/usr/bin/env python3
"""
Скрипт для добавления пользовательских полей в Bitrix24 через API.
Добавляет поля UF_PLAN_JSON и UF_FACT_JSON в смарт-процесс "Смена".
"""

import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http_client import bx, get_bitrix_url
from app.services.bitrix_ids import SHIFT_ETID


async def add_text_field(entity_type_id: int, field_name: str, label: str, is_multiple: bool = False) -> bool:
    """
    Добавить текстовое поле в смарт-процесс Bitrix24.
    
    Args:
        entity_type_id: ID типа сущности (например, 1050 для "Смена")
        field_name: Имя поля (например, "UF_PLAN_JSON")
        label: Название поля (например, "План работ (JSON)")
        is_multiple: Множественное ли поле
    
    Returns:
        True если успешно, False если ошибка
    """
    try:
        # Для смарт-процессов используем entityId в формате "CRM" + entityTypeId
        # Например, для entityTypeId=1050 это будет "CRM1050"
        entity_id = f"CRM{entity_type_id}"
        
        # Для многострочного текста используем USER_TYPE_ID = "text"
        payload = {
            "fields": {
                "FIELD_NAME": field_name,
                "USER_TYPE_ID": "text",  # Многострочный текст
                "XML_ID": field_name.lower(),
                "SORT": 500,
                "MULTIPLE": "N",
                "MANDATORY": "N",
                "SHOW_FILTER": "N",
                "SHOW_IN_LIST": "Y",
                "EDIT_IN_LIST": "Y",
                "IS_SEARCHABLE": "N",
                "SETTINGS": {
                    "DEFAULT_VALUE": "",
                    "SIZE": 0,
                    "ROWS": 5,  # 5 строк для многострочного текста
                    "REGEXP": ""
                },
                "LIST": [
                    {
                        "VALUE": label,
                        "DEF": "N"
                    }
                ],
                "LABEL": {
                    "ru": label,
                    "en": field_name
                }
            }
        }
        
        print(f"📝 Создаю поле '{label}' ({field_name}) для {entity_id}...")
        
        # Пробуем разные методы API
        methods_to_try = [
            ("crm.userfield.add", {"entityId": entity_id, **payload}),
            ("crm.item.userfield.add", {"entityTypeId": entity_type_id, **payload}),
        ]
        
        for method, method_payload in methods_to_try:
            try:
                print(f"   Пробую метод {method}...")
                result = await bx(method, method_payload)
                if result:
                    print(f"✅ Поле '{label}' успешно создано через {method}!")
                    return True
            except Exception as method_error:
                error_msg = str(method_error)
                # Если поле уже существует, это нормально
                if "already exists" in error_msg.lower() or "уже существует" in error_msg.lower() or "duplicate" in error_msg.lower():
                    print(f"ℹ️ Поле '{label}' уже существует")
                    return True
                print(f"   ⚠️ {method} не сработал: {error_msg[:100]}")
                continue
        
        print(f"⚠️ Не удалось создать поле '{label}' ни одним из методов")
        return False
            
    except Exception as e:
        error_msg = str(e)
        # Если поле уже существует, это нормально
        if "already exists" in error_msg.lower() or "уже существует" in error_msg.lower():
            print(f"ℹ️ Поле '{label}' уже существует, пропускаю")
            return True
        print(f"❌ Ошибка при создании поля '{label}': {e}")
        return False


async def check_field_exists(entity_type_id: int, field_label: str) -> bool:
    """Проверить, существует ли поле с таким названием."""
    try:
        fields = await bx("crm.item.fields", {"entityTypeId": entity_type_id})
        if not fields:
            return False
        
        # Ищем поле по label через userfield.list
        userfields = await bx("crm.item.userfield.list", {"entityTypeId": entity_type_id})
        if userfields:
            for uf in userfields.get("userFields", []):
                if uf.get("EDIT_FORM_LABEL") == field_label or uf.get("LIST_COLUMN_LABEL") == field_label:
                    return True
        return False
    except Exception as e:
        print(f"⚠️ Ошибка при проверке существования поля: {e}")
        return False


async def main():
    """Главная функция."""
    print("=" * 60)
    print("Добавление полей в Bitrix24 для ЛПА")
    print("=" * 60)
    print()
    
    try:
        bitrix_url = get_bitrix_url()
        print(f"🔗 Подключение к Bitrix24: {bitrix_url[:50]}...")
        print()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("Проверьте, что BITRIX_WEBHOOK_URL установлен в .env файле")
        sys.exit(1)
    
    # Поля для добавления
    fields_to_add = [
        {
            "field_name": "UF_PLAN_JSON",
            "label": "План работ (JSON)",
            "description": "Детальные данные плана работ в формате JSON"
        },
        {
            "field_name": "UF_FACT_JSON",
            "label": "Факт работ (JSON)",
            "description": "Детальные данные фактических работ в формате JSON"
        }
    ]
    
    success_count = 0
    
    for field_info in fields_to_add:
        field_name = field_info["field_name"]
        label = field_info["label"]
        
        # Проверяем, существует ли поле
        exists = await check_field_exists(SHIFT_ETID, label)
        if exists:
            print(f"ℹ️ Поле '{label}' уже существует, пропускаю")
            success_count += 1
            continue
        
        # Пробуем создать через crm.type.fields.add
        success = await add_text_field(SHIFT_ETID, field_name, label, is_multiple=False)
        if success:
            success_count += 1
        else:
            # Если не получилось через crm.type.fields.add, пробуем альтернативный метод
            print(f"⚠️ Первый метод не сработал, пробую альтернативный...")
            # Bitrix24 может требовать другой формат для некоторых типов полей
            # В этом случае нужно использовать веб-интерфейс Bitrix24
    
    print()
    print("=" * 60)
    if success_count == len(fields_to_add):
        print(f"✅ Успешно обработано {success_count} из {len(fields_to_add)} полей")
        print()
        print("📋 Следующий шаг: Запустите синхронизацию:")
        print("   python scripts/sync_bitrix_env.py")
    else:
        print(f"⚠️ Обработано {success_count} из {len(fields_to_add)} полей")
        print()
        print("💡 Если поля не создались автоматически, создайте их вручную:")
        print("   1. Войдите в Bitrix24")
        print("   2. Перейдите в CRM → Смарт-процессы → Смена")
        print("   3. Нажмите 'Настроить поля'")
        print("   4. Добавьте поля:")
        for field_info in fields_to_add:
            print(f"      - {field_info['label']} (многострочный текст)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

