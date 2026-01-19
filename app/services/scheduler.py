"""Сервис планировщика задач."""

from datetime import datetime, timedelta
from typing import List, Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User, UserRole, Shift, ShiftStatus, ShiftType


class SchedulerService:
    """Сервис планировщика задач."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()

    def _setup_jobs(self):
        """Настройка задач планировщика."""
        # Cron 09:30 - напоминания об отчётах за вчера
        self.scheduler.add_job(
            self.check_missing_reports,
            CronTrigger(hour=9, minute=30),
            id="check_missing_reports",
            name="Проверка отсутствующих отчётов",
        )

        # Cron 18:30 - свод проблемных отчётов дня
        self.scheduler.add_job(
            self.check_problematic_reports,
            CronTrigger(hour=18, minute=30),
            id="check_problematic_reports",
            name="Проверка проблемных отчётов",
        )

        # Еженедельно - свод по эффективности
        self.scheduler.add_job(
            self.weekly_efficiency_report,
            CronTrigger(day_of_week=0, hour=10, minute=0),  # Воскресенье 10:00
            id="weekly_efficiency_report",
            name="Еженедельный отчёт по эффективности",
        )

    async def start(self):
        """Запуск планировщика."""
        self.scheduler.start()
        logger.info("Scheduler started")

    async def stop(self):
        """Остановка планировщика."""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

    async def check_missing_reports(self):
        """Проверка отсутствующих отчётов за вчера."""
        try:
            yesterday = datetime.now().date() - timedelta(days=1)
            
            async for session in get_session():
                # Находим смены за вчера без отчётов
                stmt = select(Shift).where(
                    Shift.date == yesterday,
                    Shift.status == ShiftStatus.open,
                )
                result = await session.execute(stmt)
                missing_shifts = result.scalars().all()
                
                if missing_shifts:
                    # Получаем всех прорабов и владельцев
                    stmt = select(User).where(
                        User.role.in_([UserRole.FOREMAN, UserRole.OWNER])
                    )
                    result = await session.execute(stmt)
                    users = result.scalars().all()
                    
                    for user in users:
                        await self._send_missing_report_notification(
                            user, missing_shifts, yesterday
                        )
                
                logger.info(f"Checked missing reports for {yesterday}: {len(missing_shifts)} missing")
                break
                
        except Exception as e:
            logger.error(f"Error checking missing reports: {e}")

    async def check_problematic_reports(self):
        """Проверка проблемных отчётов дня."""
        try:
            today = datetime.now().date()
            
            async for session in get_session():
                # Находим смены за сегодня с проблемами
                stmt = select(Shift).where(
                    Shift.date == today,
                    Shift.status == ShiftStatus.closed,
                )
                result = await session.execute(stmt)
                shifts = result.scalars().all()
                
                problematic_shifts = []
                for shift in shifts:
                    if self._is_problematic_shift(shift):
                        problematic_shifts.append(shift)
                
                if problematic_shifts:
                    # Отправляем свод владельцам
                    stmt = select(User).where(User.role == UserRole.OWNER)
                    result = await session.execute(stmt)
                    owners = result.scalars().all()
                    
                    for owner in owners:
                        await self._send_problematic_reports_summary(
                            owner, problematic_shifts, today
                        )
                
                logger.info(f"Checked problematic reports for {today}: {len(problematic_shifts)} problematic")
                break
                
        except Exception as e:
            logger.error(f"Error checking problematic reports: {e}")

    async def weekly_efficiency_report(self):
        """Еженедельный отчёт по эффективности."""
        try:
            week_start = datetime.now().date() - timedelta(days=7)
            week_end = datetime.now().date()
            
            async for session in get_session():
                # Находим все смены за неделю
                stmt = select(Shift).where(
                    Shift.date >= week_start,
                    Shift.date <= week_end,
                    Shift.status == ShiftStatus.closed,
                )
                result = await session.execute(stmt)
                shifts = result.scalars().all()
                
                if shifts:
                    # Отправляем свод владельцам
                    stmt = select(User).where(User.role == UserRole.OWNER)
                    result = await session.execute(stmt)
                    owners = result.scalars().all()
                    
                    for owner in owners:
                        await self._send_weekly_efficiency_summary(
                            owner, shifts, week_start, week_end
                        )
                
                logger.info(f"Generated weekly efficiency report for {week_start} - {week_end}: {len(shifts)} shifts")
                break
                
        except Exception as e:
            logger.error(f"Error generating weekly efficiency report: {e}")

    def _is_problematic_shift(self, shift: Shift) -> bool:
        """Проверка, является ли смена проблемной."""
        try:
            # Триггеры проблем:
            # 1. Перерасход (факт > план на 20%)
            # 2. Недозагрузка (факт < план на 30%)
            # 3. Неполнота отчётности (отсутствуют обязательные поля)
            
            if not shift.plan_json or not shift.fact_json:
                return True
            
            # Проверка перерасхода/недозагрузки
            if "volume" in shift.plan_json and "volume" in shift.fact_json:
                plan_volume = float(shift.plan_json["volume"])
                fact_volume = float(shift.fact_json["volume"])
                
                if plan_volume > 0:
                    deviation = (fact_volume - plan_volume) / plan_volume
                    if abs(deviation) > 0.2:  # 20% отклонение
                        return True
            
            # Проверка неполноты отчётности
            required_fields = ["incidents", "downtime", "completeness"]
            for field in required_fields:
                if field not in shift.fact_json or not shift.fact_json[field]:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking problematic shift: {e}")
            return True

    async def _send_missing_report_notification(
        self,
        user: User,
        missing_shifts: List[Shift],
        date: datetime.date,
    ):
        """Отправка уведомления об отсутствующих отчётах."""
        try:
            shift_info = []
            for shift in missing_shifts:
                shift_info.append(
                    f"• {shift.object.name} - {shift.type.value} смена"
                )
            
            message = (
                f"⚠️ Отсутствуют отчёты за {date.strftime('%d.%m.%Y')}:\n\n"
                + "\n".join(shift_info)
            )
            
            logger.info(f"Missing report notification for user {user.tg_id}: {message}")
            
            # Отправка через Telegram API
            try:
                from app.telegram.bot import gpo_bot
                await gpo_bot.send_message(user.tg_id, message)
                logger.info(f"Sent missing report notification to user {user.tg_id}")
            except Exception as send_error:
                logger.error(f"Error sending Telegram message to user {user.tg_id}: {send_error}")
            
        except Exception as e:
            logger.error(f"Error sending missing report notification: {e}")

    async def _send_problematic_reports_summary(
        self,
        user: User,
        problematic_shifts: List[Shift],
        date: datetime.date,
    ):
        """Отправка свода проблемных отчётов."""
        try:
            shift_info = []
            for shift in problematic_shifts:
                issues = self._get_shift_issues(shift)
                shift_info.append(
                    f"• {shift.object.name} - {shift.type.value} смена: {', '.join(issues)}"
                )
            
            message = (
                f"🚨 Проблемные отчёты за {date.strftime('%d.%m.%Y')}:\n\n"
                + "\n".join(shift_info)
            )
            
            logger.info(f"Problematic reports summary for user {user.tg_id}: {message}")
            
            # Отправка через Telegram API
            try:
                from app.telegram.bot import gpo_bot
                await gpo_bot.send_message(user.tg_id, message)
                logger.info(f"Sent problematic reports summary to user {user.tg_id}")
            except Exception as send_error:
                logger.error(f"Error sending Telegram message to user {user.tg_id}: {send_error}")
            
        except Exception as e:
            logger.error(f"Error sending problematic reports summary: {e}")

    async def _send_weekly_efficiency_summary(
        self,
        user: User,
        shifts: List[Shift],
        week_start: datetime.date,
        week_end: datetime.date,
    ):
        """Отправка еженедельного свода по эффективности."""
        try:
            # Расчёт статистики
            total_shifts = len(shifts)
            avg_efficiency = 0
            over_budget_count = 0
            
            if shifts:
                efficiencies = [float(shift.eff_final) for shift in shifts if shift.eff_final]
                if efficiencies:
                    avg_efficiency = sum(efficiencies) / len(efficiencies)
                
                # Подсчёт перерасходов (упрощённо)
                over_budget_count = sum(1 for shift in shifts if shift.eff_final and float(shift.eff_final) < 70)
            
            message = (
                f"📊 Еженедельный свод ({week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}):\n\n"
                f"📅 Всего смен: {total_shifts}\n"
                f"📈 Средняя эффективность: {avg_efficiency:.1f}%\n"
                f"⚠️ Проблемных смен: {over_budget_count}\n"
                f"💰 Перерасходы: {over_budget_count} смен"
            )
            
            logger.info(f"Weekly efficiency summary for user {user.tg_id}: {message}")
            
            # Отправка через Telegram API
            try:
                from app.telegram.bot import gpo_bot
                await gpo_bot.send_message(user.tg_id, message)
                logger.info(f"Sent weekly efficiency summary to user {user.tg_id}")
            except Exception as send_error:
                logger.error(f"Error sending Telegram message to user {user.tg_id}: {send_error}")
            
        except Exception as e:
            logger.error(f"Error sending weekly efficiency summary: {e}")

    def _get_shift_issues(self, shift: Shift) -> List[str]:
        """Получение списка проблем смены."""
        issues = []
        
        try:
            if not shift.plan_json or not shift.fact_json:
                issues.append("неполные данные")
                return issues
            
            # Проверка объёма
            if "volume" in shift.plan_json and "volume" in shift.fact_json:
                plan_volume = float(shift.plan_json["volume"])
                fact_volume = float(shift.fact_json["volume"])
                
                if plan_volume > 0:
                    deviation = (fact_volume - plan_volume) / plan_volume
                    if deviation > 0.2:
                        issues.append("перерасход")
                    elif deviation < -0.3:
                        issues.append("недозагрузка")
            
            # Проверка отчётности
            if not shift.fact_json.get("incidents"):
                issues.append("нет инцидентов")
            
            if not shift.fact_json.get("downtime"):
                issues.append("нет простоев")
            
            if not shift.completeness:
                issues.append("неполнота")
            
        except Exception as e:
            logger.error(f"Error getting shift issues: {e}")
            issues.append("ошибка данных")
        
        return issues


# Глобальный экземпляр сервиса
scheduler_service = SchedulerService()
 