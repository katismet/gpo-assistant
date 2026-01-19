from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Tuple


def to_number(x: Any) -> float:
    """Преобразует значение в число, поддерживая строки с запятой."""
    try:
        return float(str(x).replace(',', '.'))
    except (ValueError, TypeError):
        return 0.0


def normalize_plan_fact(payload: Any) -> Dict[str, Any]:
    """
    Нормализует план/факт из любого формата в стандартный.
    Принимает: None | dict-старый | dict-новый | list (из Bitrix)
    Возвращает: dict с ключами tasks(list[{name,unit,plan,fact,executor}]), total_plan, total_fact
    """
    # Если payload is list: берем первый элемент если это dict
    if isinstance(payload, list):
        if len(payload) == 1 and isinstance(payload[0], dict):
            payload = payload[0]
        elif len(payload) == 0:
            payload = None
        else:
            payload = None
    
    # Если None или не dict - возвращаем пустую структуру
    if not isinstance(payload, dict):
        return {"tasks": [], "total_plan": 0.0, "total_fact": 0.0}
    
    # Если dict и есть ключ 'tasks' (новый формат)
    if "tasks" in payload:
        tasks_raw = payload.get("tasks", [])
        if not isinstance(tasks_raw, list):
            tasks_raw = []
        
        tasks = []
        for t in tasks_raw:
            if not isinstance(t, dict):
                continue
            tasks.append({
                "name": str(t.get("name", "")).strip(),
                "unit": str(t.get("unit", "ед.")).strip() or "ед.",
                "plan": to_number(t.get("plan", 0)),
                "fact": to_number(t.get("fact", 0)),
                "executor": str(t.get("executor", "Бригада")).strip() or "Бригада",
            })
        
        return {
            "tasks": tasks,
            "total_plan": to_number(payload.get("total_plan", 0)),
            "total_fact": to_number(payload.get("total_fact", 0)),
        }
    
    # Если dict без 'tasks' (старый формат: {"земляные": 110, ...})
    tasks = []
    for k, v in payload.items():
        # Пропускаем служебные поля
        if k.lower() in {"tasks", "total_plan", "total_fact", "object_name", "date", 
                         "section", "foreman", "shift_type", "type", "plan_total", 
                         "fact_total", "downtime_reason", "photos"}:
            continue
        if not isinstance(v, (int, float, str)):
            continue
        num_val = to_number(v)
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
    }


def merge_plan_fact(plan_norm: Dict[str, Any], fact_norm: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], float, float]:
    """
    Объединяет нормализованные план и факт по имени задачи.
    Возвращает: (rows, total_plan, total_fact)
    """
    # Индекс задач из плана
    idx = {t["name"]: {**t} for t in plan_norm.get("tasks", []) if t.get("name")}
    
    # Добавляем/обновляем факт
    for f in fact_norm.get("tasks", []):
        name = f.get("name", "").strip()
        if not name:
            continue
        
        if name in idx:
            # Обновляем факт в существующей задаче
            idx[name]["fact"] = to_number(f.get("fact", 0))
        else:
            # Добавляем новую задачу из факта
            idx[name] = {
                "name": name,
                "unit": f.get("unit", "ед.") or "ед.",
                "plan": 0.0,
                "fact": to_number(f.get("fact", 0)),
                "executor": f.get("executor", "Бригада") or "Бригада",
            }
    
    rows = list(idx.values())
    
    # Вычисляем итоги
    total_plan = sum(to_number(r.get("plan", 0)) for r in rows)
    total_fact = sum(to_number(r.get("fact", 0)) for r in rows)
    
    return rows, total_plan, total_fact


# Старые функции для обратной совместимости
SERVICE_PLAN_FIELDS = {
    "object_name",
    "date",
    "section",
    "foreman",
    "shift_type",
    "type",
    "total_plan",
    "plan_total",
}


def build_plan_json_from_raw(
    plan_raw: Dict[str, Any],
    *,
    object_name: Optional[str] = None,
    date: Optional[str] = None,
    section: Optional[str] = None,
    foreman: Optional[str] = None,
    shift_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Преобразует словарь {работа: объём} в стандартную структуру плана (для обратной совместимости)."""
    tasks: List[Dict[str, Any]] = []
    for raw_name, raw_value in (plan_raw or {}).items():
        name = str(raw_name).strip()
        if not name:
            continue
        # Пропускаем служебные поля
        if name.lower() in {f.lower() for f in SERVICE_PLAN_FIELDS}:
            continue
        qty = _round(to_number(raw_value))
        tasks.append({
            "name": name,
            "unit": "ед.",
            "plan": qty,
            "fact": 0.0,
            "executor": "Бригада",
        })

    total_plan = _round(sum(task["plan"] for task in tasks))

    plan_json = {
        "tasks": tasks,
        "total_plan": total_plan,
        "object_name": object_name,
        "date": date,
        "section": section,
        "foreman": foreman,
        "shift_type": shift_type,
    }
    return plan_json


def build_fact_json_from_raw(
    fact_raw: Dict[str, Any],
    *,
    plan_tasks: Optional[Iterable[Dict[str, Any]]] = None,
    downtime_reason: Optional[str] = None,
    photos: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Преобразует словарь {работа: объём} в стандартную структуру факта (для обратной совместимости)."""
    plan_index = {_normalize_name(task["name"]): task for task in (plan_tasks or []) if "name" in task}

    tasks: List[Dict[str, Any]] = []
    used = set()

    for task in plan_tasks or []:
        name = task.get("name")
        if not name:
            continue
        norm = _normalize_name(name)
        fact_value = _round(to_number(_get_from_dict(fact_raw, name)))
        tasks.append({"name": name, "fact": fact_value})
        used.add(norm)

    for raw_name, raw_value in (fact_raw or {}).items():
        norm = _normalize_name(raw_name)
        if norm in used or norm in plan_index:
            continue
        fact_value = _round(to_number(raw_value))
        if math.isclose(fact_value, 0.0):
            continue
        tasks.append({"name": str(raw_name).strip(), "fact": fact_value})

    total_fact = _round(sum(task["fact"] for task in tasks))

    fact_json = {
        "tasks": tasks,
        "total_fact": total_fact,
        "downtime_reason": downtime_reason or "",
        "photos": photos or [],
    }
    return fact_json


def _get_from_dict(data: Dict[str, Any], key: str) -> Any:
    """Получает значение из словаря по ключу (с учетом регистра)."""
    if key in data:
        return data[key]
    lower_key = _normalize_name(key)
    for k, v in data.items():
        if _normalize_name(k) == lower_key:
            return v
    return 0.0


def _parse_float(value: Any) -> float:
    """Безопасно преобразует значение в float, поддерживая строки с запятой."""
    return to_number(value)


def _round(value: float) -> float:
    return round(value, 3)


def _normalize_name(name: str) -> str:
    return (name or "").strip().lower()


def plan_tasks_from_json(
    plan_json: Dict[str, Any],
    fallback_raw: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Обратная совместимость - использует normalize_plan_fact."""
    plan_norm = normalize_plan_fact(plan_json or fallback_raw)
    meta = {
        "total_plan": plan_norm.get("total_plan", 0),
    }
    return plan_norm.get("tasks", []), meta


def fact_tasks_from_json(
    fact_json: Dict[str, Any],
    fallback_raw: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Обратная совместимость - использует normalize_plan_fact."""
    fact_norm = normalize_plan_fact(fact_json or fallback_raw)
    meta = {
        "total_fact": fact_norm.get("total_fact", 0),
    }
    return fact_norm.get("tasks", []), meta


def merge_plan_fact_tasks(
    plan_tasks: Iterable[Dict[str, Any]],
    fact_tasks: Iterable[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], float, float]:
    """Обратная совместимость - использует merge_plan_fact."""
    plan_norm = {"tasks": list(plan_tasks)}
    fact_norm = {"tasks": list(fact_tasks)}
    rows, total_plan, total_fact = merge_plan_fact(plan_norm, fact_norm)
    
    # Форматируем для старого формата (строки)
    formatted_rows = []
    for row in rows:
        formatted_rows.append({
            "name": row["name"],
            "unit": row["unit"],
            "plan": str(row["plan"]),
            "fact": str(row["fact"]),
            "executor": row["executor"],
            "reason": "" if abs(row["plan"] - row["fact"]) < 0.01 else (
                "Работа вне плана" if row["plan"] == 0 else "Отклонение от плана"
            ),
        })
    
    return formatted_rows, total_plan, total_fact
