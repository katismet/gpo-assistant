"""Планировщик для W6: ежедневные уведомления."""

import logging
from datetime import date, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.w6_alerts import build_daily_report, list_subscribers
from app.telegram.bot import gpo_bot

log = logging.getLogger("gpo.w6_scheduler")


class W6Scheduler:
    """Планировщик для отправки ежедневных сводок W6."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()

    def _setup_jobs(self):
        """Настройка задач планировщика."""
        # Cron 09:30 - утренняя сводка за вчера
        self.scheduler.add_job(
            self.send_morning_report,
            CronTrigger(hour=9, minute=30),
            id="w6_morning_report",
            name="Утренняя сводка W6 (09:30)",
        )

        # Cron 18:30 - вечерняя сводка за сегодня
        self.scheduler.add_job(
            self.send_evening_report,
            CronTrigger(hour=18, minute=30),
            id="w6_evening_report",
            name="Вечерняя сводка W6 (18:30)",
        )

    async def start(self):
        """Запуск планировщика."""
        self.scheduler.start()
        log.info("W6 Scheduler started (09:30 and 18:30)")

    async def stop(self):
        """Остановка планировщика."""
        self.scheduler.shutdown()
        log.info("W6 Scheduler stopped")

    async def send_morning_report(self):
        """Отправка утренней сводки за вчера."""
        try:
            yesterday = date.today() - timedelta(days=1)
            report, _ = await build_daily_report(yesterday)
            
            subscribers = list_subscribers()
            if not subscribers:
                log.info("No subscribers for W6 morning report")
                return

            message = f"🌅 Утренняя сводка\n\n{report}"
            
            for chat_id in subscribers:
                try:
                    await gpo_bot.send_message(chat_id, message)
                    log.info(f"Sent morning W6 report to {chat_id}")
                except Exception as e:
                    log.error(f"Error sending W6 report to {chat_id}: {e}")
            
            log.info(f"Sent morning W6 report to {len(subscribers)} subscribers")
            
        except Exception as e:
            log.error(f"Error in send_morning_report: {e}", exc_info=True)

    async def send_evening_report(self):
        """Отправка вечерней сводки за сегодня."""
        try:
            today = date.today()
            report, _ = await build_daily_report(today)
            
            subscribers = list_subscribers()
            if not subscribers:
                log.info("No subscribers for W6 evening report")
                return

            message = f"🌆 Вечерняя сводка\n\n{report}"
            
            for chat_id in subscribers:
                try:
                    await gpo_bot.send_message(chat_id, message)
                    log.info(f"Sent evening W6 report to {chat_id}")
                except Exception as e:
                    log.error(f"Error sending W6 report to {chat_id}: {e}")
            
            log.info(f"Sent evening W6 report to {len(subscribers)} subscribers")
            
        except Exception as e:
            log.error(f"Error in send_evening_report: {e}", exc_info=True)


# Глобальный экземпляр планировщика
w6_scheduler = W6Scheduler()

