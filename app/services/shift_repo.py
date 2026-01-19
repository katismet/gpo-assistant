from contextlib import contextmanager
from datetime import datetime, date
from typing import Dict, Any, List, Optional

from app.db import SessionLocal
from app.models import Shift, ShiftType, ShiftStatus
from app.services.lpa_utils import (
    build_plan_json_from_raw,
    plan_tasks_from_json,
    build_fact_json_from_raw,
)

@contextmanager
def session_scope():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except:
        s.rollback()
        raise
    finally:
        s.close()

def save_plan(object_id: int, date_key: str, plan: dict, created_by: int = 1, **extra_fields) -> int:
    import logging

    log = logging.getLogger("gpo.shift_repo")

    d = date.today() if date_key == "today" else date.fromordinal(date.today().toordinal() + 1)

    log.info(f"[save_plan] Input plan keys: {list(plan.keys()) if isinstance(plan, dict) else 'N/A'}")
    log.info(f"[save_plan] Extra fields: {extra_fields}")

    if isinstance(plan, dict) and plan.get("tasks"):
        tasks, meta = plan_tasks_from_json(plan)
        plan_json = plan.copy()
        plan_json["tasks"] = tasks
        plan_json["total_plan"] = meta.get("total_plan") or sum(task["plan"] for task in tasks)
    else:
        plan_json = build_plan_json_from_raw(
            plan or {},
            object_name=extra_fields.get("object_name"),
            date=extra_fields.get("date"),
            section=extra_fields.get("section"),
            foreman=extra_fields.get("foreman"),
            shift_type=extra_fields.get("shift_type"),
        )

    for meta_key in ("object_name", "date", "section", "foreman", "shift_type"):
        if extra_fields.get(meta_key):
            plan_json[meta_key] = extra_fields[meta_key]

    log.info(
        "[save_plan] Normalized plan: tasks=%s, total_plan=%s",
        len(plan_json.get("tasks", [])),
        plan_json.get("total_plan"),
    )

    with session_scope() as s:
        sh = Shift(
            object_id=object_id,
            date=d,
            type=ShiftType.DAY,
            plan_json=plan_json,
            status=ShiftStatus.OPEN,
            created_by=created_by,
        )
        s.add(sh)
        s.flush()
        log.info(f"[save_plan] Saved shift_id={sh.id}")
        return sh.id

def get_last_open_shift(object_id: int) -> tuple[int, dict] | None:
    """Получить последнюю открытую смену для объекта.
    
    Returns:
        (shift_id, plan) - где plan это словарь {работа: количество}
    """
    try:
        with session_scope() as s:
            # Используем только поля, которые точно есть в БД (без bitrix_id в SELECT)
            sh = s.query(Shift.id, Shift.object_id, Shift.status, Shift.plan_json)\
                     .filter(Shift.object_id==object_id, Shift.status==ShiftStatus.OPEN)\
                     .order_by(Shift.id.desc()).first()
            if not sh:
                return None
            
            plan_json = sh.plan_json or {}
            if not plan_json.get("tasks"):
                plan_json = build_plan_json_from_raw(plan_json or {})
            return (sh.id, plan_json)
    except Exception as e:
        # Если ошибка из-за отсутствия колонки bitrix_id, пробуем без явного SELECT
        import logging
        log = logging.getLogger("gpo.shift_repo")
        try:
            with session_scope() as s:
                sh = s.query(Shift).filter(Shift.object_id==object_id, Shift.status==ShiftStatus.OPEN)\
                         .order_by(Shift.id.desc()).first()
                if not sh:
                    return None
                
                plan_json = sh.plan_json or {}
                if not plan_json.get("tasks"):
                    plan_json = build_plan_json_from_raw(plan_json or {})
                return (sh.id, plan_json)
        except Exception as e2:
            log.error(f"Error in get_last_open_shift: {e2}", exc_info=True)
            return None

def get_shift_by_bitrix_id(bitrix_id: int) -> tuple[int, dict] | None:
    """Получить смену по bitrix_id из локальной БД.
    
    Returns:
        (shift_id, {"object_id": int, ...}) или None
    """
    try:
        with session_scope() as s:
            sh = s.query(Shift).filter(Shift.bitrix_id == bitrix_id).first()
            if not sh:
                return None
            return (sh.id, {"object_id": sh.object_id})
    except Exception as e:
        import logging
        log = logging.getLogger("gpo.shift_repo")
        log.debug(f"Error in get_shift_by_bitrix_id: {e}")
        return None

def get_last_closed_shift(object_id: int) -> tuple[int, dict] | None:
    """Получить последнюю закрытую смену для объекта."""
    with session_scope() as s:
        sh = s.query(Shift).filter(Shift.object_id==object_id, Shift.status==ShiftStatus.CLOSED)\
                 .order_by(Shift.id.desc()).first()
        if not sh:
            return None
        
        # Получаем название объекта из БД (актуальное, не из plan_json!)
        object_name = sh.object.name if sh.object else f"Объект #{object_id}"
        
        # Форматируем дату в нужном формате
        formatted_date = sh.date.strftime("%d.%m.%Y") if sh.date else "Не указана"
        
        plan_data_raw = sh.plan_json or {}
        fact_data_raw = sh.fact_json or {}

        import logging
        log = logging.getLogger("gpo.shift_repo")
        log.info(f"[get_last_closed_shift] Shift {sh.id}, object_id={object_id}, object_name={object_name}")

        plan_json = plan_data_raw if isinstance(plan_data_raw, dict) else {}
        if not plan_json.get("tasks"):
            plan_json = build_plan_json_from_raw(
                plan_json or {},
                object_name=object_name,
                date=formatted_date,
                section=plan_json.get("section"),
                foreman=plan_json.get("foreman"),
                shift_type=sh.type.value if sh.type else "day",
            )
        plan_json["object_name"] = object_name
        plan_json["date"] = formatted_date
        plan_json.setdefault("section", "Не указан")
        plan_json.setdefault("foreman", "Не указан")
        plan_json.setdefault("shift_type", sh.type.value if sh.type else "day")

        plan_tasks, _ = plan_tasks_from_json(plan_json)

        fact_json = fact_data_raw if isinstance(fact_data_raw, dict) else {}
        if not fact_json.get("tasks"):
            fact_json = build_fact_json_from_raw(
                fact_data_raw or {},
                plan_tasks=plan_tasks,
                downtime_reason=fact_data_raw.get("downtime_reason") if isinstance(fact_data_raw, dict) else None,
                photos=fact_data_raw.get("photos") if isinstance(fact_data_raw, dict) else None,
            )

        return (sh.id, {
            "plan": plan_json,
            "fact": fact_json,
            "efficiency": sh.eff_final or 0,
            "date": formatted_date,
            "type": sh.type.value if sh.type else None,
            "status": sh.status.value if sh.status else None
        })

def save_fact(
    shift_id: int,
    fact: dict,
    eff_raw: float,
    eff_final: float,
    *,
    plan_json: Optional[Dict[str, Any]] = None,
    downtime_reason: Optional[str] = None,
    photos: Optional[List[str]] = None,
) -> None:
    """Сохранить факты смены. Не закрывает смену, только сохраняет данные."""
    with session_scope() as s:
        sh = s.get(Shift, shift_id)
        if not sh:
            return

        plan_tasks, _ = plan_tasks_from_json(plan_json or {}, fallback_raw=None)
        fact_json = build_fact_json_from_raw(
            fact or {},
            plan_tasks=plan_tasks,
            downtime_reason=downtime_reason,
            photos=photos,
        )

        sh.fact_json = fact_json
        sh.eff_raw = eff_raw
        sh.eff_final = eff_final
        s.add(sh)
