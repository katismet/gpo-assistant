"""Проверка UF полей в Bitrix24 через crm.item.fields"""

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


def check_entity_fields(entity_type_id: int, entity_name: str):
    """Проверка полей для сущности."""
    print(f"\n🔍 Проверка полей для «{entity_name}» (entityTypeId={entity_type_id})...")
    
    try:
        fields = bx("crm.item.fields", {"entityTypeId": entity_type_id})
        
        # Ищем UF поля
        uf_fields = {k: v for k, v in fields.items() if k.startswith("UF_")}
        
        print(f"   Всего полей: {len(fields)}")
        print(f"   UF полей: {len(uf_fields)}")
        
        if uf_fields:
            print("   Найденные UF поля:")
            for code, field_info in sorted(uf_fields.items()):
                title = field_info.get("title") or field_info.get("formLabel") or code
                field_type = field_info.get("type") or "unknown"
                print(f"      • {code} → {title} ({field_type})")
        else:
            print("   ⚠ UF поля не найдены")
        
        return uf_fields
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return {}


def main():
    print("🔍 Проверка UF полей в Bitrix24\n")
    
    results = {}
    
    if ENTITY_RESOURCE:
        results["Ресурс"] = check_entity_fields(ENTITY_RESOURCE, "Ресурс")
    
    if ENTITY_SHIFT:
        results["Смена"] = check_entity_fields(ENTITY_SHIFT, "Смена")
    
    if ENTITY_TIMESHEET:
        results["Табель"] = check_entity_fields(ENTITY_TIMESHEET, "Табель")
    
    # Сохраняем результаты
    with open("bitrix_uf_fields.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("\n✅ Результаты сохранены в bitrix_uf_fields.json")


if __name__ == "__main__":
    main()









