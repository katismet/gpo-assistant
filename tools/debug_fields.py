"""Отладка получения полей из Bitrix24"""

import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

BITRIX = os.getenv("BITRIX_WEBHOOK_URL")
ENTITY_RESOURCE = int(os.getenv("ENTITY_RESOURCE", "0"))
ENTITY_SHIFT = int(os.getenv("ENTITY_SHIFT", "0"))
ENTITY_TIMESHEET = int(os.getenv("ENTITY_TIMESHEET", "0"))

if not BITRIX:
    print("❌ BITRIX_WEBHOOK_URL не задан")
    exit(1)


def bx(method: str, payload=None):
    """Вызов Bitrix REST API."""
    url = f"{BITRIX}/{method}"
    r = httpx.post(url, json=payload or {}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"{method}: {data.get('error_description', data['error'])}")
    return data.get("result")


def debug_entity_fields(entity_type_id: int, entity_name: str):
    """Отладка полей для сущности."""
    print(f"\n{'='*60}")
    print(f"🔍 Отладка полей для «{entity_name}» (entityTypeId={entity_type_id})")
    print(f"{'='*60}\n")
    
    try:
        fields = bx("crm.item.fields", {"entityTypeId": entity_type_id})
        
        print(f"Тип данных: {type(fields)}")
        print(f"Количество ключей: {len(fields) if isinstance(fields, dict) else 'N/A'}\n")
        
        if isinstance(fields, dict):
            # Все поля
            print("📋 Все поля:")
            for k, v in sorted(fields.items()):
                if isinstance(v, dict):
                    field_type = v.get("type") or "unknown"
                    title = v.get("title") or v.get("formLabel") or k
                else:
                    field_type = type(v).__name__
                    title = str(v)[:50] if v is not None else "None"
                print(f"   {k:30} | {str(field_type):15} | {title}")
            
            # UF поля
            uf_fields = {k: v for k, v in fields.items() if k.startswith("UF_")}
            print(f"\n🔹 UF полей найдено: {len(uf_fields)}")
            if uf_fields:
                print("\n📋 UF поля:")
                for k, v in sorted(uf_fields.items()):
                    field_type = v.get("type") if isinstance(v, dict) else type(v).__name__
                    title = v.get("title") or v.get("formLabel") if isinstance(v, dict) else str(v)[:50]
                    print(f"   {k:30} | {field_type:15} | {title}")
            else:
                print("   ⚠ UF поля не найдены")
        else:
            print(f"⚠ Неожиданный формат данных: {fields}")
        
        # Сохраняем полный ответ
        with open(f"debug_fields_{entity_name.lower()}.json", "w", encoding="utf-8") as f:
            json.dump(fields, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Полный ответ сохранен в debug_fields_{entity_name.lower()}.json")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("🔍 Отладка получения полей из Bitrix24\n")
    
    if ENTITY_RESOURCE:
        debug_entity_fields(ENTITY_RESOURCE, "Ресурс")
    
    if ENTITY_SHIFT:
        debug_entity_fields(ENTITY_SHIFT, "Смена")
    
    if ENTITY_TIMESHEET:
        debug_entity_fields(ENTITY_TIMESHEET, "Табель")


if __name__ == "__main__":
    main()

