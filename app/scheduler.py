# app/scheduler.py

import datetime as dt
from datetime import timedelta
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.w6_alerts import list_subscribers, build_daily_report
from app.services.authz import list_by_role
from app.services.insights import collect_kpis, generate_insights

log = logging.getLogger("gpo.scheduler")


def setup_scheduler(bot_send_func):
    """
    bot_send_func: coroutine(chat_id: int, text: str) -> None
    """
    sched = AsyncIOScheduler()

    async def job_morning(send_time: str):
        """Утренняя сводка за вчера."""
        yesterday = dt.date.today() - timedelta(days=1)
        
        # OWNER - общая сводка по всем объектам
        owners = list_by_role("OWNER")
        if owners:
            txt_common, _ = await build_daily_report(yesterday, filter_objects=None)
            for o in owners:
                chat_id = o.get("chat_id")
                if chat_id:
                    try:
                        await bot_send_func(chat_id, f"{send_time}\n{txt_common}")
                        log.info(f"Sent morning report to OWNER {o.get('tg_id')} (chat_id={chat_id})")
                    except Exception as e:
                        log.error(f"Error sending morning report to OWNER {o.get('tg_id')}: {e}")
        
        # FOREMAN - сводка только по их объектам
        foremen = list_by_role("FOREMAN")
        for f in foremen:
            chat_id = f.get("chat_id")
            objects = f.get("objects", [])
            if not chat_id:
                continue
            
            if not objects:
                log.info(f"FOREMAN {f.get('tg_id')} has no objects assigned, skipping")
                continue
            
            # Фильтруем сводку по объектам прораба
            filter_objects = set(objects)
            txt_filtered, _ = await build_daily_report(yesterday, filter_objects=filter_objects)
            
            try:
                await bot_send_func(chat_id, f"{send_time}\n{txt_filtered}")
                log.info(f"Sent morning report to FOREMAN {f.get('tg_id')} (chat_id={chat_id}, objects={objects})")
            except Exception as e:
                log.error(f"Error sending morning report to FOREMAN {f.get('tg_id')}: {e}")
        
        # Старая система подписок (для обратной совместимости)
        # Отправляем только тем, кто не в ACL
        acl_chat_ids = {u.get("chat_id") for u in (owners + foremen) if u.get("chat_id")}
        for chat_id in list_subscribers():
            # Пропускаем пользователей, которые уже получили сводку через ACL
            if chat_id not in acl_chat_ids:
                try:
                    txt, _ = await build_daily_report(yesterday)
                    await bot_send_func(chat_id, f"{send_time}\n{txt}")
                    log.info(f"Sent morning report to subscriber {chat_id} (legacy)")
                except Exception as e:
                    log.error(f"Error sending morning report to subscriber {chat_id}: {e}")

    async def job_evening(send_time: str):
        """Вечерняя сводка за сегодня."""
        today = dt.date.today()
        
        # OWNER - общая сводка по всем объектам
        owners = list_by_role("OWNER")
        if owners:
            txt_common, _ = await build_daily_report(today, filter_objects=None)
            for o in owners:
                chat_id = o.get("chat_id")
                if chat_id:
                    try:
                        await bot_send_func(chat_id, f"{send_time}\n{txt_common}")
                        log.info(f"Sent evening report to OWNER {o.get('tg_id')} (chat_id={chat_id})")
                    except Exception as e:
                        log.error(f"Error sending evening report to OWNER {o.get('tg_id')}: {e}")
        
        # FOREMAN - сводка только по их объектам
        foremen = list_by_role("FOREMAN")
        for f in foremen:
            chat_id = f.get("chat_id")
            objects = f.get("objects", [])
            if not chat_id:
                continue
            
            if not objects:
                log.info(f"FOREMAN {f.get('tg_id')} has no objects assigned, skipping")
                continue
            
            # Фильтруем сводку по объектам прораба
            filter_objects = set(objects)
            txt_filtered, _ = await build_daily_report(today, filter_objects=filter_objects)
            
            try:
                await bot_send_func(chat_id, f"{send_time}\n{txt_filtered}")
                log.info(f"Sent evening report to FOREMAN {f.get('tg_id')} (chat_id={chat_id}, objects={objects})")
            except Exception as e:
                log.error(f"Error sending evening report to FOREMAN {f.get('tg_id')}: {e}")
        
        # Старая система подписок (для обратной совместимости)
        acl_chat_ids = {u.get("chat_id") for u in (owners + foremen) if u.get("chat_id")}
        for chat_id in list_subscribers():
            if chat_id not in acl_chat_ids:
                try:
                    txt, _ = await build_daily_report(today)
                    await bot_send_func(chat_id, f"{send_time}\n{txt}")
                    log.info(f"Sent evening report to subscriber {chat_id} (legacy)")
                except Exception as e:
                    log.error(f"Error sending evening report to subscriber {chat_id}: {e}")

    async def job_insights(send_time: str):
        """Ежедневные AI-инсайты для владельца."""
        try:
            today = dt.date.today()
            yesterday = today - dt.timedelta(days=1)
            
            k_today = await collect_kpis(today)
            k_yesterday = await collect_kpis(yesterday)
            
            txt = await generate_insights(k_today, k_yesterday)
            
            # Отправляем только владельцам (OWNER)
            owners = list_by_role("OWNER")
            for o in owners:
                chat_id = o.get("chat_id")
                if chat_id:
                    try:
                        await bot_send_func(chat_id, f"{send_time}\n\n{txt}")
                        log.info(f"Sent insights to OWNER {o.get('tg_id')} (chat_id={chat_id})")
                    except Exception as e:
                        log.error(f"Error sending insights to OWNER {o.get('tg_id')}: {e}")
            
            if not owners:
                log.info("No OWNER users found for insights")
                
        except Exception as e:
            log.error(f"Error in job_insights: {e}", exc_info=True)

    # 09:30 - утренняя сводка за вчера, 18:30 - вечерняя сводка за сегодня, 19:00 - AI-инсайты для владельца
    sched.add_job(
        job_morning, "cron", hour=9, minute=30,
        args=["🌅 Утреннее напоминание"]
    )
    sched.add_job(
        job_evening, "cron", hour=18, minute=30,
        args=["🌆 Вечерняя сводка"]
    )
    sched.add_job(
        job_insights, "cron", hour=19, minute=0,
        args=["🤖 Ежедневные инсайты"]
    )

    sched.start()
    return sched

