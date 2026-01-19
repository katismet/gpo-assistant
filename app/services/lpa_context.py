"""Билдер контекста для генерации ЛПА."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional


def _num(x: Any) -> float:
    """Преобразует значение в float."""
    try:
        return float(Decimal(str(x)))
    except Exception:
        return 0.0


def _pad(rows: List[Dict[str, Any]], size: int, filler: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Дополняет список до нужного размера."""
    rows = list(rows)[:size]
    while len(rows) < size:
        rows.append(filler.copy())
    return rows


def normalize_plan_fact_json(data: Any) -> Dict[str, Any]:
    """Нормализует план/факт из старого или нового формата."""
    if not isinstance(data, dict):
        return {"tasks": [], "total_plan": 0.0, "total_fact": 0.0}
    
    # Если есть tasks - новый формат
    if "tasks" in data and isinstance(data.get("tasks"), list):
        return {
            "tasks": data["tasks"],
            "total_plan": _num(data.get("total_plan", 0)),
            "total_fact": _num(data.get("total_fact", 0)),
            "downtime_reason": data.get("downtime_reason", ""),
        }
    
    # Старый формат: {"земляные": 110, ...}
    tasks = []
    for k, v in data.items():
        # Пропускаем служебные поля
        if k.lower() in {"tasks", "total_plan", "total_fact", "object_name", "date", 
                         "section", "foreman", "shift_type", "type", "plan_total", 
                         "fact_total", "downtime_reason", "photos"}:
            continue
        if not isinstance(v, (int, float, str)):
            continue
        num_val = _num(v)
        if num_val == 0:
            continue
        tasks.append({
            "name": str(k).strip(),
            "unit": "ед.",
            "plan": 0.0,
            "fact": num_val,
            "executor": "Бригада",
        })
    
    return {
        "tasks": tasks,
        "total_plan": 0.0,
        "total_fact": sum(t["fact"] for t in tasks),
        "downtime_reason": data.get("downtime_reason", ""),
    }


def build_lpa_context(
    shift_item: Dict[str, Any],
    plan_json: Dict[str, Any],
    fact_json: Dict[str, Any],
    resources: List[Dict[str, Any]],
    timesheets: List[Dict[str, Any]],
    photos: List[tuple],
    object_name: str,
    section: str,
    date_str: str,
    foreman: str,
) -> Dict[str, Any]:
    """Строит контекст для docxtpl из данных смены."""
    
    # Нормализуем план и факт
    plan_norm = normalize_plan_fact_json(plan_json)
    fact_norm = normalize_plan_fact_json(fact_json)
    
    # 1) Нормализация задач
    plan_tasks = {
        t["name"]: {
            "unit": t.get("unit", ""),
            "plan": _num(t.get("plan", 0)),
            "executor": t.get("executor", "")
        }
        for t in plan_norm.get("tasks", [])
        if t.get("name")
    }
    
    fact_tasks = {
        t["name"]: {
            "unit": t.get("unit", ""),
            "fact": _num(t.get("fact", 0)),
            "executor": t.get("executor", ""),
            "reason": t.get("reason", "")
        }
        for t in fact_norm.get("tasks", [])
        if t.get("name")
    }
    
    # Объединённый список имён в порядке факта (если он есть) или плана
    names = list(fact_tasks.keys()) or list(plan_tasks.keys())
    
    tasks = []
    for name in names:
        p = plan_tasks.get(name, {})
        f = fact_tasks.get(name, {})
        tasks.append({
            "name": name,
            "unit": f.get("unit") or p.get("unit", ""),
            "plan": p.get("plan", 0.0),
            "fact": f.get("fact", 0.0),
            "executor": f.get("executor") or p.get("executor", ""),
            "reason": f.get("reason", "") or ("Работа вне плана" if name not in plan_tasks else "")
        })
    
    # 2) Итоги
    plan_total = plan_norm.get("total_plan")
    if plan_total is None:
        plan_total = sum(_num(t["plan"]) for t in tasks)
    else:
        plan_total = _num(plan_total)
    
    fact_total = fact_norm.get("total_fact")
    if fact_total is None:
        fact_total = sum(_num(t["fact"]) for t in tasks)
    else:
        fact_total = _num(fact_total)
    
    efficiency = round((fact_total / plan_total * 100.0), 2) if plan_total > 0 else 0.0
    
    # 3) Ресурсы
    equip = []
    mats = []
    for r in resources:
        rtype = r.get("ufCrm9UfResourceType") or r.get("UF_CRM_9_UF_RESOURCE_TYPE")
        rtype_str = str(rtype).upper()
        
        if rtype_str.startswith("TECH") or rtype == "0" or rtype == 0:
            equip.append({
                "name": r.get("ufCrm9UfEquipType") or r.get("UF_CRM_9_UF_EQUIP_TYPE", ""),
                "hours": _num(r.get("ufCrm9UfEquipHours") or r.get("UF_CRM_9_UF_EQUIP_HOURS", 0)),
                "comment": r.get("ufCrm9UfResComment") or r.get("UF_CRM_9_UF_RES_COMMENT") or ""
            })
        else:
            qty = _num(r.get("ufCrm9UfMatQty") or r.get("UF_CRM_9_UF_MAT_QTY", 0))
            price = _num(r.get("ufCrm9UfMatPrice") or r.get("UF_CRM_9_UF_MAT_PRICE", 0))
            mats.append({
                "name": r.get("ufCrm9UfMatType") or r.get("UF_CRM_9_UF_MAT_TYPE", ""),
                "unit": r.get("ufCrm9UfMatUnit") or r.get("UF_CRM_9_UF_MAT_UNIT", ""),
                "qty": qty,
                "price": price,
                "sum": round(qty * price, 2)
            })
    
    # 4) Табель
    trows = []
    for t in timesheets:
        hours = _num(t.get("ufCrm11UfHours") or t.get("UF_CRM_11_UF_HOURS", 0))
        rate = _num(t.get("ufCrm11UfRate") or t.get("UF_CRM_11_UF_RATE", 0))
        trows.append({
            "name": t.get("ufCrm11UfWorker") or t.get("UF_CRM_11_UF_WORKER", ""),
            "hours": hours,
            "rate": rate,
            "sum": round(hours * rate, 2)
        })
    
    # 5) Пэддинг под шаблон
    tasks = _pad(tasks, 10, {"name": "", "unit": "", "plan": "", "fact": "", "executor": "", "reason": ""})
    equip = _pad(equip, 7, {"name": "", "hours": "", "comment": ""})
    trows = _pad(trows, 7, {"name": "", "hours": "", "rate": "", "sum": ""})
    mats = _pad(mats, 7, {"name": "", "unit": "", "qty": "", "price": "", "sum": ""})
    
    # 6) Контекст docxtpl
    ctx = {
        "object_name": object_name,
        "section": section,
        "date": date_str,
        "foreman": foreman,
        "plan_total": plan_total,
        "fact_total": fact_total,
        "downtime_min": 0,
        "downtime_reason": fact_norm.get("downtime_reason", "") or "Нет простоев",
        "efficiency": efficiency,
        "report_status": "closed" if str(shift_item.get("stageId", "")).upper() in ("CLOSED", "SUCCESS") else "open",
        "reasons_text": "\n".join([t["reason"] for t in tasks if t.get("reason")]) or "",
        "photos_attached": "Да" if photos else "Нет",
    }
    
    # Разворачивание в плоские ключи под шаблон
    for i, t in enumerate(tasks, 1):
        ctx.update({
            f"task{i}_name": t["name"],
            f"task{i}_unit": t["unit"],
            f"task{i}_plan": t["plan"],
            f"task{i}_fact": t["fact"],
            f"task{i}_executor": t["executor"],
            f"task{i}_reason": t["reason"],
        })
    
    for i, e in enumerate(equip, 1):
        ctx.update({
            f"equip{i}_name": e["name"],
            f"equip{i}_hours": e["hours"],
            f"equip{i}_comment": e["comment"],
        })
    
    for i, r in enumerate(trows, 1):
        ctx.update({
            f"worker{i}_name": r["name"],
            f"worker{i}_hours": r["hours"],
            f"worker{i}_rate": r["rate"],
            f"worker{i}_sum": r["sum"],
        })
    
    for i, m in enumerate(mats, 1):
        ctx.update({
            f"mat{i}_name": m["name"],
            f"mat{i}_unit": m["unit"],
            f"mat{i}_qty": m["qty"],
            f"mat{i}_price": m["price"],
            f"mat{i}_sum": m["sum"],
        })
    
    return ctx





