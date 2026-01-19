# app/services/w6_alerts.py

import os
import json
import math
import datetime as dt
import logging
from pathlib import Path

from app.bitrix_field_map import resolve_code
from app.services.http_client import bx, BitrixError
from dotenv import load_dotenv

log = logging.getLogger("gpo.w6_alerts")

load_dotenv()

ENTITY_OBJECT = int(os.getenv("ENTITY_OBJECT", "0"))
ENTITY_SHIFT = int(os.getenv("ENTITY_SHIFT", "0"))
ENTITY_RESOURCE = int(os.getenv("ENTITY_RESOURCE", "0"))
ENTITY_TIMESHEET = int(os.getenv("ENTITY_TIMESHEET", "0"))

SUBS_FILE = Path("w6_subscriptions.json")


def _load_subs() -> set[int]:
    if not SUBS_FILE.exists():
        return set()
    try:
        return set(json.loads(SUBS_FILE.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _save_subs(s: set[int]) -> None:
    SUBS_FILE.write_text(json.dumps(list(s)), encoding="utf-8")


# Функция bx теперь импортируется из app.services.http_client


# ---------- чтение данных ----------

async def list_shifts_by_date(date: dt.date) -> list[dict]:
    """Получить смены за указанную дату с fallback механизмом."""
    from app.bitrix_field_map import upper_to_camel
    fld_date = resolve_code("Смена", "UF_DATE")
    fld_date_camel = upper_to_camel(fld_date)  # Используем camelCase для Bitrix24 API
    
    day_from = dt.datetime.combine(date, dt.time.min).isoformat()
    day_to = dt.datetime.combine(date, dt.time.max).isoformat()
    
    # 1) точный фильтр по дню (может не работать для UF полей, но пробуем)
    try:
        filter_dict = {}
        filter_dict[f">={fld_date_camel}"] = day_from
        filter_dict[f"<={fld_date_camel}"] = day_to
        
        res = await bx("crm.item.list", {
            "entityTypeId": ENTITY_SHIFT,
            "filter": filter_dict,
            "select": ["id", "title", fld_date_camel, "*", "ufCrm%"]
        })
        
        items = res.get("items", res) if isinstance(res, dict) else (res if isinstance(res, list) else [])
        if items:
            log.info(f"Found {len(items)} shifts for {date} using filter")
            return items
    except Exception as e:
        # Фильтр не поддерживается, переходим к fallback
        log.warning(f"Filter by date failed: {e}, using fallback")
        pass
    
    # 2) fallback: последние 50 записей и ручная фильтрация по дате
    res2 = await bx("crm.item.list", {
        "entityTypeId": ENTITY_SHIFT,
        "order": {"id": "desc"},
        "limit": 50,
        "select": ["id", "title", fld_date_camel, "*", "ufCrm%"]
    })
    
    items2 = res2.get("items", res2) if isinstance(res2, dict) else (res2 if isinstance(res2, list) else [])
    
    out = []
    for it in items2:
        # Пробуем оба варианта: camelCase и UPPER_CASE
        raw = it.get(fld_date_camel) or it.get(fld_date)
        if not raw:
            continue
        try:
            # Парсим дату из разных форматов
            if isinstance(raw, str):
                # Убираем временную зону если есть
                raw_clean = raw.replace("Z", "+00:00")
                d = dt.datetime.fromisoformat(raw_clean).date()
            else:
                continue
        except Exception as e:
            log.debug(f"Could not parse date from {raw}: {e}")
            continue
        if d == date:
            out.append(it)
    
    log.info(f"Found {len(out)} shifts for {date} using fallback (checked {len(items2)} items)")
    return out


async def list_resources_by_shift(shift_id: int) -> list[dict]:
    """Получить ресурсы по ID смены."""
    from app.bitrix_field_map import upper_to_camel
    fld = resolve_code("Ресурс", "UF_SHIFT_ID")
    fld_camel = upper_to_camel(fld)  # Используем camelCase для фильтра
    
    try:
        res = await bx("crm.item.list", {
            "entityTypeId": ENTITY_RESOURCE,
            "filter": {fld_camel: shift_id},
            "select": ["id", "title", "*"]
        })
        return res.get("items", res) or []
    except Exception as e:
        log.warning(f"Error filtering resources by shift_id {shift_id}: {e}, trying without filter")
        # Fallback: получаем все и фильтруем вручную
        res = await bx("crm.item.list", {
            "entityTypeId": ENTITY_RESOURCE,
            "select": ["id", "title", fld_camel, "*"],
            "limit": 100
        })
        items = res.get("items", res) or []
        # Фильтруем вручную
        filtered = []
        for item in items:
            shift_id_value = _get_field_value(item, fld)
            if shift_id_value == shift_id:
                filtered.append(item)
        return filtered


async def list_timesheets_by_shift(shift_id: int) -> list[dict]:
    """Получить табели по ID смены."""
    from app.bitrix_field_map import upper_to_camel
    fld = resolve_code("Табель", "UF_SHIFT_ID")
    fld_camel = upper_to_camel(fld)  # Используем camelCase для фильтра
    
    try:
        res = await bx("crm.item.list", {
            "entityTypeId": ENTITY_TIMESHEET,
            "filter": {fld_camel: shift_id},
            "select": ["id", "title", "*"]
        })
        return res.get("items", res) or []
    except Exception as e:
        log.warning(f"Error filtering timesheets by shift_id {shift_id}: {e}, trying without filter")
        # Fallback: получаем все и фильтруем вручную
        res = await bx("crm.item.list", {
            "entityTypeId": ENTITY_TIMESHEET,
            "select": ["id", "title", fld_camel, "*"],
            "limit": 100
        })
        items = res.get("items", res) or []
        # Фильтруем вручную
        filtered = []
        for item in items:
            shift_id_value = _get_field_value(item, fld)
            if shift_id_value == shift_id:
                filtered.append(item)
        return filtered


# ---------- расчёты ----------

def _get_field_value(item: dict, field_upper: str) -> any:
    """Получить значение поля из записи Bitrix, проверяя оба формата (UPPER_CASE и camelCase)."""
    from app.bitrix_field_map import upper_to_camel
    # Пробуем оба формата
    value = item.get(field_upper)
    if value is None:
        value = item.get(upper_to_camel(field_upper))
    return value


def calc_resource_money(items: list[dict]) -> float:
    # Материалы: qty * price
    from app.bitrix_field_map import upper_to_camel
    m_qty = resolve_code("Ресурс", "UF_MAT_QTY")
    m_price = resolve_code("Ресурс", "UF_MAT_PRICE")
    r_type = resolve_code("Ресурс", "UF_RESOURCE_TYPE")
    e_hours = resolve_code("Ресурс", "UF_EQUIP_HOURS")
    e_rate = resolve_code("Ресурс", "UF_EQUIP_RATE")
    e_rtype = resolve_code("Ресурс", "UF_EQUIP_RATE_TYPE")
    
    total = 0.0
    
    for it in items:
        # Проверяем оба формата для чтения
        kind_raw = _get_field_value(it, r_type)
        kind = str(kind_raw or "").upper()
        
        # Для enum полей Bitrix может возвращать ID вместо значения
        # Если это число, пробуем найти значение по ID
        if kind.isdigit() or kind == "0":
            # Это enum ID, нужно найти значение
            # Пока используем прямое сравнение с ID
            if kind == "0" or kind == "":
                # Пробуем определить тип по другим полям
                if _get_field_value(it, e_hours):
                    kind = "EQUIP"
                elif _get_field_value(it, m_qty):
                    kind = "MAT"
        
        if kind == "MAT":
            q = float(_get_field_value(it, m_qty) or 0)
            p = float(_get_field_value(it, m_price) or 0)
            total += q * p
        elif kind == "EQUIP":
            hours = float(_get_field_value(it, e_hours) or 0)
            rate = float(_get_field_value(it, e_rate) or 0)
            rtype = str(_get_field_value(it, e_rtype) or "HOUR").upper()
            
            if rtype == "HOUR":
                total += hours * rate
            elif rtype == "SHIFT":
                total += rate
            elif rtype == "TRIP":
                # если в карточке машино-часы хранит рейсы
                total += hours * rate
            else:
                total += hours * rate
    
    return round(total, 2)


def calc_timesheet_hours(items: list[dict]) -> float:
    h = resolve_code("Табель", "UF_HOURS")
    total = sum(float(_get_field_value(it, h) or 0) for it in items)
    return round(total, 2)


def calc_eff(plan_total: float, fact_total: float) -> tuple[float, float]:
    if plan_total <= 0:
        return 0.0, 0.0
    
    eff_raw = fact_total / plan_total
    # финалка пока без коэффициентов — оставим как есть
    eff_final = eff_raw
    
    return round(eff_raw, 3), round(eff_final, 3)


# ---------- апдейт смены ----------

async def update_shift_totals(shift_id: int, plan_total: float | None, fact_total: float, eff_raw: float, eff_final: float):
    from app.bitrix_field_map import upper_to_camel
    f_plan = resolve_code("Смена", "UF_PLAN_TOTAL")  # "Плановый объём"
    f_fact = resolve_code("Смена", "UF_FACT_TOTAL")  # "Фактический объём"
    f_raw = resolve_code("Смена", "UF_EFF_RAW")  # "Коэффициент эффективности"
    f_final = resolve_code("Смена", "UF_EFF_FINAL")  # "Итоговая эффективность"
    
    # Конвертируем в camelCase для Bitrix24 API
    fields = {
        upper_to_camel(f_fact): fact_total,
        upper_to_camel(f_raw): eff_raw,
        upper_to_camel(f_final): eff_final,
    }
    
    if plan_total is not None:
        fields[upper_to_camel(f_plan)] = plan_total
    
    await bx("crm.item.update", {"entityTypeId": ENTITY_SHIFT, "id": shift_id, "fields": fields})


# ---------- отчёт ----------

async def build_daily_report(date: dt.date, filter_objects: set[int] | None = None) -> tuple[str, list]:
    """Построить ежедневную сводку за указанную дату.
    
    Args:
        date: Дата для сводки
        filter_objects: Если указано, фильтровать смены только по этим объектам (None = все объекты)
    """
    shifts = await list_shifts_by_date(date)
    
    if not shifts:
        return f"Сводка за {date:%d.%m.%Y}: смен нет."
    
    lines = [f"Сводка за {date:%d.%m.%Y}"]
    
    # Получаем код поля для объекта (UF_OBJECT_LINK из bitrix_ids)
    f_object = None
    try:
        from app.services.bitrix_ids import UF_OBJECT_LINK
        f_object = UF_OBJECT_LINK
    except ImportError:
        # Fallback: пробуем через resolve_code
        try:
            f_object = resolve_code("Смена", "UF_OBJECT_LINK")
        except:
            try:
                f_object = resolve_code("Смена", "UF_OBJECT_ID")
            except:
                pass
    
    for s in shifts:
        sid = s["id"]
        
        # Фильтрация по объектам, если указана
        if filter_objects is not None and f_object:
            object_link = s.get(f_object)
            if object_link:
                try:
                    # UF_OBJECT_LINK может быть массивом вида ["D_1046"] или строкой "D_1046"
                    if isinstance(object_link, list):
                        if not object_link:
                            continue  # Нет привязки к объекту
                        obj_str = object_link[0]
                    else:
                        obj_str = object_link
                    
                    # Извлекаем ID из формата "D_1046" или просто числа
                    if isinstance(obj_str, str) and obj_str.startswith("D_"):
                        obj_id_int = int(obj_str[2:])
                    else:
                        obj_id_int = int(obj_str)
                    
                    if obj_id_int not in filter_objects:
                        continue  # Пропускаем смену, если объект не в списке разрешенных
                except (ValueError, TypeError, IndexError):
                    # Если не удалось преобразовать, пропускаем фильтрацию для этой смены
                    log.debug(f"Could not parse object_id from shift {sid}, field {f_object}, value: {object_link}")
                    pass
        
        resources = await list_resources_by_shift(sid)
        timesheets = await list_timesheets_by_shift(sid)
        
        # Читаем план и факт из JSON-полей (приоритет над агрегатами)
        from app.services.lpa_data import _parse_json_field as parse_json_field
        
        plan_raw = s.get("ufCrm7UfPlanJson") or s.get("UF_CRM_7_UF_PLAN_JSON")
        fact_raw = s.get("ufCrm7UfFactJson") or s.get("UF_CRM_7_UF_FACT_JSON")
        
        plan_json = parse_json_field(plan_raw) if plan_raw else {}
        fact_json = parse_json_field(fact_raw) if fact_raw else {}
        
        # Берем total_plan и total_fact из JSON
        total_plan = float(plan_json.get("total_plan", 0) or 0)
        total_fact = float(fact_json.get("total_fact", 0) or 0)
        
        # Fallback к агрегированным полям, если JSON пуст
        if total_plan == 0:
            f_plan = resolve_code("Смена", "UF_PLAN_TOTAL")
            total_plan = float((_get_field_value(s, f_plan) or 0))
        
        if total_fact == 0:
            f_fact = resolve_code("Смена", "UF_FACT_TOTAL")
            total_fact = float((_get_field_value(s, f_fact) or 0))
            # Если факт все еще 0, пробуем рассчитать из ресурсов (fallback)
            if total_fact == 0:
                money = calc_resource_money(resources)
                total_fact = money
        
        hours = calc_timesheet_hours(timesheets)
        
        # Рассчитываем эффективность из JSON-данных
        if total_plan > 0:
            eff = round((total_fact / total_plan * 100), 1)
        else:
            eff = 0.0
        
        # Причина простоя из fact_json
        downtime_reason = fact_json.get("downtime_reason", "") or "-"
        if not downtime_reason or downtime_reason.strip() == "":
            downtime_reason = "нет"
        
        # Форматируем вывод одной строкой
        lines.append(
            f"— {s.get('title', f'Смена #{sid}')}: факт={total_fact:.1f} | план={total_plan:.1f} | eff={eff:.1f}% | простои={downtime_reason}"
        )
    
    if len(lines) == 1:  # Только заголовок, смен нет после фильтрации
        return f"Сводка за {date:%d.%m.%Y}: смен по выбранным объектам нет.", None
    
    return "\n".join(lines), shifts  # Возвращаем текст и список смен для создания кнопок


async def build_daily_report_for_shift(shift_id: int) -> str:
    """Построить отчёт для конкретной смены по её ID."""
    resources = await list_resources_by_shift(shift_id)
    timesheets = await list_timesheets_by_shift(shift_id)
    
    money = calc_resource_money(resources)
    hours = calc_timesheet_hours(timesheets)
    
    f_plan = resolve_code("Смена", "UF_PLAN_TOTAL")
    # получим саму смену ради плана
    s = await bx("crm.item.get", {"entityTypeId": ENTITY_SHIFT, "id": shift_id})
    item = s.get("item") or {}
    plan = float((item.get(f_plan) or 0))
    
    eff_raw, eff_final = calc_eff(plan, money)
    
    await update_shift_totals(shift_id, None, money, eff_raw, eff_final)
    
    return f"Сводка по смене #{shift_id}: факт={money:.2f} | часы={hours:.2f} | план={plan:.2f} | eff={eff_final:.2f}"


# ---------- подписки ----------

def subscribe(chat_id: int) -> str:
    s = _load_subs()
    s.add(int(chat_id))
    _save_subs(s)
    return "Вы подписаны на ежедневные сводки (09:30 и 18:30)."


def unsubscribe(chat_id: int) -> str:
    s = _load_subs()
    if int(chat_id) in s:
        s.remove(int(chat_id))
        _save_subs(s)
        return "Вы отписаны от ежедневных сводок."
    return "Подписки не было."


def list_subscribers() -> list[int]:
    return list(_load_subs())

