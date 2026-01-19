# app/handlers/debug_shift.py

import os
import datetime as dt
import logging

from aiogram import Router, F
from aiogram.types import Message

from app.bitrix_field_map import resolve_code
from app.services.http_client import bx, BitrixError
from dotenv import load_dotenv

load_dotenv()

router = Router()
log = logging.getLogger("gpo.debug_shift")

ENTITY_SHIFT = int(os.getenv("ENTITY_SHIFT", "0"))
ENTITY_RESOURCE = int(os.getenv("ENTITY_RESOURCE", "0"))
ENTITY_TIMESHEET = int(os.getenv("ENTITY_TIMESHEET", "0"))


@router.message(F.text.lower() == "/debug_shift_today")
async def debug_shift_today(m: Message):
    """Создать тестовую смену на сегодня и привязать к ней ресурсы/табель.
    
    Debug команда - доступна только в режиме DEBUG.
    """
    from app.config import get_settings
    settings = get_settings()
    
    if not settings.DEBUG:
        log.warning(f"User {m.from_user.id} tried to use debug_shift_today in production")
        await m.answer("❌ Команда недоступна в продакшене.")
        return
    
    try:
        log.info(f"User {m.from_user.id} creating debug shift for today")
        
        # 1) создаём смену с сегодняшней датой
        from app.bitrix_field_map import upper_to_camel
        f_date = resolve_code("Смена", "UF_DATE")
        # Используем текущую дату/время в формате ISO для Bitrix24
        now = dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
        # Конвертируем в camelCase для Bitrix24 API
        f_date_camel = upper_to_camel(f_date) if f_date.startswith("UF_") else f_date
        
        res = await bx("crm.item.add", {
            "entityTypeId": ENTITY_SHIFT,
            "fields": {"TITLE": "Тест смена (сегодня)", f_date_camel: now}
        })
        
        shift_id = res.get("item", {}).get("id") or res.get("id")
        log.info(f"Created shift id={shift_id}")
        
        # 2) берём по одному последнему ресурсу и табелю и привязываем к смене
        from app.bitrix_field_map import upper_to_camel
        f_rs = resolve_code("Ресурс", "UF_SHIFT_ID")
        f_ts = resolve_code("Табель", "UF_SHIFT_ID")
        
        # Конвертируем в camelCase для Bitrix24 API
        f_rs_camel = upper_to_camel(f_rs) if f_rs.startswith("UF_") else f_rs
        f_ts_camel = upper_to_camel(f_ts) if f_ts.startswith("UF_") else f_ts
        
        # Получаем последние ресурсы
        last_res = await bx("crm.item.list", {
            "entityTypeId": ENTITY_RESOURCE,
            "order": {"id": "desc"},
            "limit": 2,
            "select": ["id"]
        })
        
        resources_updated = 0
        for it in (last_res.get("items") or []):
            await bx("crm.item.update", {
                "entityTypeId": ENTITY_RESOURCE,
                "id": it["id"],
                "fields": {f_rs_camel: shift_id}
            })
            resources_updated += 1
            log.info(f"Updated resource id={it['id']} with shift_id={shift_id}")
        
        # Получаем последний табель
        last_ts = await bx("crm.item.list", {
            "entityTypeId": ENTITY_TIMESHEET,
            "order": {"id": "desc"},
            "limit": 1,
            "select": ["id"]
        })
        
        timesheets_updated = 0
        for it in (last_ts.get("items") or []):
            await bx("crm.item.update", {
                "entityTypeId": ENTITY_TIMESHEET,
                "id": it["id"],
                "fields": {f_ts_camel: shift_id}
            })
            timesheets_updated += 1
            log.info(f"Updated timesheet id={it['id']} with shift_id={shift_id}")
        
        await m.answer(
            f"✅ Создана смена id={shift_id} (сегодня).\n"
            f"Привязано ресурсов: {resources_updated}\n"
            f"Привязано табелей: {timesheets_updated}"
        )
        log.info(f"Debug shift created successfully: shift_id={shift_id}")
        
    except Exception as e:
        log.error(f"Error in debug_shift_today: {e}", exc_info=True)
        await m.answer(f"❌ /debug_shift_today: {e}")

