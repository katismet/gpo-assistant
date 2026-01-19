"""Диагностический скрипт для проверки поиска закрытых смен для ЛПА."""
import asyncio
import sys
from datetime import date, timedelta
from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID, UF_OBJECT_LINK
from app.bitrix_field_map import resolve_code, upper_to_camel
from app.services.w6_alerts import _get_field_value

async def debug_lpa_search(obj_id: int):
    """Диагностика поиска закрытых смен для объекта."""
    print("=" * 60)
    print(f"Диагностика поиска закрытых смен для объекта {obj_id}")
    print("=" * 60)
    
    # Получаем коды полей
    f_date = resolve_code("Смена", "UF_DATE")
    f_date_camel = upper_to_camel(f_date)
    f_plan_code = resolve_code("Смена", "UF_PLAN_TOTAL")
    f_fact_code = resolve_code("Смена", "UF_FACT_TOTAL")
    f_eff_code = resolve_code("Смена", "UF_EFF_FINAL")
    f_status_code = resolve_code("Смена", "UF_STATUS")
    f_status_camel = upper_to_camel(f_status_code)
    f_fact_camel = upper_to_camel(f_fact_code)
    f_plan_camel = upper_to_camel(f_plan_code)
    f_eff_camel = upper_to_camel(f_eff_code)
    
    print(f"\nКоды полей:")
    print(f"  UF_DATE: {f_date} -> {f_date_camel}")
    print(f"  UF_PLAN_TOTAL: {f_plan_code} -> {f_plan_camel}")
    print(f"  UF_FACT_TOTAL: {f_fact_code} -> {f_fact_camel}")
    print(f"  UF_STATUS: {f_status_code} -> {f_status_camel}")
    
    # 1. Прямой поиск по объекту
    print(f"\n1. Прямой поиск по объекту {obj_id}...")
    try:
        shifts_res = await bx("crm.item.list", {
            "entityTypeId": SHIFT_ETID,
            "select": ["id", f_date_camel, UF_OBJECT_LINK, f_status_camel, f_plan_camel, f_fact_camel, f_eff_camel, "*"],
            "order": {"id": "desc"},
            "limit": 200
        })
        
        items = shifts_res.get("items", []) if isinstance(shifts_res, dict) else (shifts_res if isinstance(shifts_res, list) else [])
        print(f"   Найдено всего смен в Bitrix24: {len(items)}")
        
        # Фильтруем по объекту
        matching_items = []
        for item in items:
            obj_link = item.get(UF_OBJECT_LINK)
            if not obj_link:
                continue
            
            obj_str = None
            if isinstance(obj_link, list) and len(obj_link) > 0:
                obj_str = obj_link[0]
            elif isinstance(obj_link, str):
                obj_str = obj_link
            
            if not obj_str:
                continue
            
            try:
                if isinstance(obj_str, str) and obj_str.startswith("D_"):
                    obj_id_from_bitrix = int(obj_str[2:])
                else:
                    obj_id_from_bitrix = int(obj_str)
                
                if obj_id_from_bitrix == obj_id:
                    matching_items.append(item)
            except (ValueError, TypeError):
                continue
        
        print(f"   Найдено смен для объекта {obj_id}: {len(matching_items)}")
        
        if matching_items:
            print(f"\n   Детали найденных смен:")
            for item in matching_items[:10]:  # Показываем первые 10
                sid = item.get("id")
                plan_total = float(item.get(f_plan_camel) or item.get(f_plan_code) or 0)
                fact_total = float(item.get(f_fact_camel) or item.get(f_fact_code) or 0)
                eff_final = float(item.get(f_eff_camel) or item.get(f_eff_code) or 0)
                
                item_status = ""
                try:
                    item_status = _get_field_value(item, f_status_camel) or _get_field_value(item, f_status_code) or ""
                    if isinstance(item_status, str):
                        item_status = item_status.lower().strip()
                except:
                    item_status = ""
                
                # Проверяем, закрыта ли смена
                is_closed = (
                    item_status in ("closed", "закрыта", "закрыто") or
                    not item_status or
                    item_status == "" or
                    (item_status != "open" and fact_total > 0)
                )
                
                status_icon = "✅" if is_closed and fact_total > 0 else "❌"
                print(f"   {status_icon} Смена #{sid}: план={plan_total}, факт={fact_total}, eff={eff_final}, status='{item_status}'")
                if not is_closed:
                    print(f"      ⚠️ Пропущена: статус='{item_status}', fact={fact_total}")
                elif fact_total == 0:
                    print(f"      ⚠️ Пропущена: нет фактических данных")
                else:
                    print(f"      ✅ Подходит для ЛПА!")
        else:
            print(f"   ❌ Смен для объекта {obj_id} не найдено")
    
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    # 2. Поиск по дням (последние 7 дней)
    print(f"\n2. Поиск по дням (последние 7 дней)...")
    today = date.today()
    found_by_date = []
    
    for days_ago in range(7):
        check_date = today - timedelta(days=days_ago)
        day_from = check_date.isoformat() + "T00:00:00"
        day_to = check_date.isoformat() + "T23:59:59"
        
        try:
            shifts_res = await bx("crm.item.list", {
                "entityTypeId": SHIFT_ETID,
                "filter": {
                    f">={f_date_camel}": day_from,
                    f"<={f_date_camel}": day_to,
                },
                "select": ["id", f_date_camel, UF_OBJECT_LINK, f_status_camel, f_plan_camel, f_fact_camel, f_eff_camel, "*"],
                "order": {"id": "desc"},
                "limit": 100
            })
            
            items = shifts_res.get("items", []) if isinstance(shifts_res, dict) else (shifts_res if isinstance(shifts_res, list) else [])
            
            if items:
                print(f"   {check_date}: найдено {len(items)} смен")
                for item in items:
                    obj_link = item.get(UF_OBJECT_LINK)
                    if obj_link:
                        if isinstance(obj_link, list) and len(obj_link) > 0:
                            obj_str = obj_link[0]
                        elif isinstance(obj_link, str):
                            obj_str = obj_link
                        else:
                            continue
                        
                        try:
                            if isinstance(obj_str, str) and obj_str.startswith("D_"):
                                obj_id_from_bitrix = int(obj_str[2:])
                            else:
                                obj_id_from_bitrix = int(obj_str)
                            
                            if obj_id_from_bitrix == obj_id:
                                sid = item.get("id")
                                fact_total = float(item.get(f_fact_camel) or item.get(f_fact_code) or 0)
                                found_by_date.append((sid, check_date, fact_total))
                        except:
                            continue
        except Exception as e:
            print(f"   Ошибка для {check_date}: {e}")
    
    if found_by_date:
        print(f"\n   Найдено смен по датам для объекта {obj_id}: {len(found_by_date)}")
        for sid, d, fact in found_by_date:
            print(f"      Смена #{sid} от {d}: факт={fact}")
    else:
        print(f"   ❌ Смен по датам для объекта {obj_id} не найдено")
    
    print("\n" + "=" * 60)
    print("Диагностика завершена")
    print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python tools/debug_lpa_search.py <object_id>")
        print("Пример: python tools/debug_lpa_search.py 7")
        sys.exit(1)
    
    obj_id = int(sys.argv[1])
    asyncio.run(debug_lpa_search(obj_id))







