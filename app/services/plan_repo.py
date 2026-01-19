from datetime import date
from sqlalchemy import select
from app.models import Shift, ShiftType
from app.db import session_scope

def save_plan(object_id: int, date_key: str, plan: dict) -> int:
    d = date.today() if date_key == "today" else date.today().fromordinal(date.today().toordinal() + 1)
    with session_scope() as s:
        sh = Shift(object_id=object_id, date=d, type=ShiftType.DAY, plan_json=plan)
        s.add(sh)
        s.flush()
        return sh.id
