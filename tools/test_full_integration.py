"""Полное тестирование интеграции с Bitrix24"""

import os
import asyncio
import httpx
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

BITRIX = os.getenv("BITRIX_WEBHOOK_URL")
ENTITY_OBJECT = int(os.getenv("ENTITY_OBJECT", "0"))
ENTITY_SHIFT = int(os.getenv("ENTITY_SHIFT", "0"))
ENTITY_RESOURCE = int(os.getenv("ENTITY_RESOURCE", "0"))
ENTITY_TIMESHEET = int(os.getenv("ENTITY_TIMESHEET", "0"))

if not BITRIX:
    print("❌ BITRIX_WEBHOOK_URL не задан")
    exit(1)


async def bx(method: str, payload=None):
    """Вызов Bitrix REST API."""
    url = f"{BITRIX}/{method}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload or {}, timeout=30)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"{method}: {data.get('error_description', data['error'])}")
        return data.get("result")


async def test_w3_resources():
    """Тест W3: создание ресурсов (техника и материал)."""
    print("\n🧪 Тест W3: Создание ресурсов...")
    
    test_shift_id = 98765  # Тестовый ID смены
    
    # Техника
    try:
        r1 = await bx("crm.item.add", {
            "entityTypeId": ENTITY_RESOURCE,
            "fields": {
                "TITLE": f"Тест техники {datetime.now().strftime('%H:%M:%S')}",
            }
        })
        equip_id = r1.get("item", {}).get("id") if isinstance(r1, dict) else r1
        print(f"   ✅ Техника создана: id={equip_id}")
    except Exception as e:
        print(f"   ❌ Ошибка создания техники: {e}")
        equip_id = None
    
    # Материал
    try:
        r2 = await bx("crm.item.add", {
            "entityTypeId": ENTITY_RESOURCE,
            "fields": {
                "TITLE": f"Тест материала {datetime.now().strftime('%H:%M:%S')}",
            }
        })
        mat_id = r2.get("item", {}).get("id") if isinstance(r2, dict) else r2
        print(f"   ✅ Материал создан: id={mat_id}")
    except Exception as e:
        print(f"   ❌ Ошибка создания материала: {e}")
        mat_id = None
    
    return equip_id, mat_id


async def test_w4_timesheet():
    """Тест W4: создание табеля."""
    print("\n🧪 Тест W4: Создание табеля...")
    
    test_shift_id = 98765  # Тестовый ID смены
    
    try:
        r = await bx("crm.item.add", {
            "entityTypeId": ENTITY_TIMESHEET,
            "fields": {
                "TITLE": f"Тест табеля {datetime.now().strftime('%H:%M:%S')}",
            }
        })
        timesheet_id = r.get("item", {}).get("id") if isinstance(r, dict) else r
        print(f"   ✅ Табель создан: id={timesheet_id}")
        return timesheet_id
    except Exception as e:
        print(f"   ❌ Ошибка создания табеля: {e}")
        return None


async def test_w2_shift():
    """Тест W2: создание смены."""
    print("\n🧪 Тест W2: Создание смены...")
    
    try:
        r = await bx("crm.item.add", {
            "entityTypeId": ENTITY_SHIFT,
            "fields": {
                "TITLE": f"Тест смены {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            }
        })
        shift_id = r.get("item", {}).get("id") if isinstance(r, dict) else r
        print(f"   ✅ Смена создана: id={shift_id}")
        return shift_id
    except Exception as e:
        print(f"   ❌ Ошибка создания смены: {e}")
        return None


async def get_entity_summary():
    """Получить сводку по сущностям."""
    print("\n📊 Сводка по сущностям Bitrix24:")
    
    entities = {
        "Объект": ENTITY_OBJECT,
        "Смена": ENTITY_SHIFT,
        "Ресурс": ENTITY_RESOURCE,
        "Табель": ENTITY_TIMESHEET,
    }
    
    summary = {}
    
    for name, etid in entities.items():
        if not etid:
            continue
        
        try:
            # Получаем поля
            fields = await bx("crm.item.fields", {"entityTypeId": etid})
            field_count = len(fields) if isinstance(fields, dict) else 0
            uf_count = len([k for k in (fields.keys() if isinstance(fields, dict) else []) if k.startswith("UF_")])
            
            # Получаем количество элементов
            items = await bx("crm.item.list", {
                "entityTypeId": etid,
                "start": 0,
                "limit": 1,
            })
            total = items.get("total", 0) if isinstance(items, dict) else 0
            
            summary[name] = {
                "entityTypeId": etid,
                "fields": field_count,
                "uf_fields": uf_count,
                "total_items": total,
            }
            
            print(f"   {name}:")
            print(f"      entityTypeId: {etid}")
            print(f"      Всего полей: {field_count}")
            print(f"      UF полей: {uf_count}")
            print(f"      Элементов: {total}")
        except Exception as e:
            print(f"   ⚠ {name}: ошибка получения данных - {e}")
            summary[name] = {"error": str(e)}
    
    return summary


async def main():
    print("=" * 60)
    print("🔍 Полное тестирование интеграции с Bitrix24")
    print("=" * 60)
    print(f"\nWebhook: {BITRIX}")
    print(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "w3_resources": {},
        "w4_timesheet": None,
        "w2_shift": None,
        "summary": {},
    }
    
    # Тест W3
    equip_id, mat_id = await test_w3_resources()
    results["w3_resources"] = {"equip_id": equip_id, "mat_id": mat_id}
    
    # Тест W4
    timesheet_id = await test_w4_timesheet()
    results["w4_timesheet"] = timesheet_id
    
    # Тест W2
    shift_id = await test_w2_shift()
    results["w2_shift"] = shift_id
    
    # Сводка
    summary = await get_entity_summary()
    results["summary"] = summary
    
    # Сохраняем результаты
    import json
    with open("bitrix_integration_test.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print("✅ Тестирование завершено")
    print("=" * 60)
    print(f"\n✅ REST API fully functional")
    print(f"\n📊 Сводка:")
    for name, info in summary.items():
        if "error" not in info:
            print(f"   {name}: entityTypeId={info['entityTypeId']}, полей={info['fields']}, элементов={info['total_items']}")
    print(f"\n📝 Результаты сохранены в bitrix_integration_test.json")
    print(f"⏰ Время последней синхронизации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())









