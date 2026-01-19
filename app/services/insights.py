# app/services/insights.py
"""AI-сервис для генерации аналитических инсайтов для владельца."""

import os
import datetime as dt
import logging
from typing import Optional
import httpx
from dotenv import load_dotenv

from app.services.w6_alerts import (
    list_shifts_by_date,
    list_resources_by_shift,
    list_timesheets_by_shift,
    calc_resource_money,
    calc_timesheet_hours,
    calc_eff
)
from app.bitrix_field_map import resolve_code

load_dotenv()

log = logging.getLogger("gpo.insights")

# Получаем настройки из config (с fallback на os.getenv)
try:
    from app.config import get_settings
    settings = get_settings()
    OPENAI_API_KEY = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = settings.OPENAI_MODEL or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
except:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


async def collect_kpis(date: dt.date) -> dict:
    """Собрать KPI по сменам за указанную дату."""
    shifts = await list_shifts_by_date(date)
    
    kpis = {
        "date": date.isoformat(),
        "shifts": [],
        "total_fact": 0.0,
        "total_hours": 0.0,
        "total_plan": 0.0,
        "shift_count": 0,
    }
    
    f_plan = resolve_code("Смена", "UF_PLAN_TOTAL")
    
    # Вспомогательная функция для чтения полей в обоих форматах
    def _get_field_value(item: dict, field_upper: str) -> any:
        """Получить значение поля из записи Bitrix, проверяя оба формата."""
        from app.bitrix_field_map import upper_to_camel
        value = item.get(field_upper)
        if value is None:
            value = item.get(upper_to_camel(field_upper))
        return value
    
    for s in shifts:
        sid = s["id"]
        resources = await list_resources_by_shift(sid)
        timesheets = await list_timesheets_by_shift(sid)
        
        fact = calc_resource_money(resources)
        hours = calc_timesheet_hours(timesheets)
        plan = float(_get_field_value(s, f_plan) or 0)
        
        eff_raw, eff_final = calc_eff(plan, fact)
        
        kpis["shifts"].append({
            "shift_id": sid,
            "fact": fact,
            "hours": hours,
            "plan": plan,
            "eff_final": eff_final
        })
        
        kpis["total_fact"] += fact
        kpis["total_hours"] += hours
        kpis["total_plan"] += plan
        kpis["shift_count"] += 1
    
    # Вычисляем среднюю эффективность
    if kpis["shift_count"] > 0:
        kpis["avg_eff"] = sum(s["eff_final"] for s in kpis["shifts"]) / kpis["shift_count"]
    else:
        kpis["avg_eff"] = 0.0
    
    return kpis


def _prompt_from_kpis(today: dict, yesterday: Optional[dict] = None) -> str:
    """Сформировать промпт из KPI данных."""
    lines = []
    lines.append(f"📊 Сводка за {today['date']}")
    lines.append(f"Смен: {today['shift_count']}")
    lines.append(f"Факт: {today['total_fact']:.2f} руб.")
    lines.append(f"Часы: {today['total_hours']:.2f} ч.")
    lines.append(f"План: {today['total_plan']:.2f} руб.")
    lines.append(f"Средняя эффективность: {today['avg_eff']:.2%}")
    
    if yesterday:
        diff_fact = today["total_fact"] - yesterday["total_fact"]
        diff_hours = today["total_hours"] - yesterday["total_hours"]
        diff_plan = today["total_plan"] - yesterday["total_plan"]
        diff_eff = today["avg_eff"] - yesterday.get("avg_eff", 0)
        
        lines.append(f"\n📈 Изменения относительно вчера:")
        lines.append(f"Факт: {diff_fact:+.2f} руб. ({diff_fact/yesterday['total_fact']*100:+.1f}%)" if yesterday['total_fact'] > 0 else f"Факт: {diff_fact:+.2f} руб.")
        lines.append(f"Часы: {diff_hours:+.2f} ч.")
        lines.append(f"План: {diff_plan:+.2f} руб.")
        lines.append(f"Эффективность: {diff_eff:+.2%}")
    
    # Топ-3 смены по факту
    if today["shifts"]:
        top_shifts = sorted(today["shifts"], key=lambda x: x["fact"], reverse=True)[:3]
        lines.append(f"\n🔝 Топ-3 смены по факту:")
        for i, s in enumerate(top_shifts, 1):
            lines.append(f"{i}. Смена #{s['shift_id']}: {s['fact']:.2f} руб. (эфф. {s['eff_final']:.2%})")
    
    return "\n".join(lines)


async def generate_insights(today: dict, yesterday: Optional[dict] = None) -> str:
    """Сгенерировать AI-инсайты на основе KPI."""
    if not OPENAI_API_KEY:
        # Fallback — простая ручная сводка без LLM
        log.warning("OPENAI_API_KEY not set, using fallback insights")
        return _prompt_from_kpis(today, yesterday) + "\n\n(🤖 AI-анализ отключён: не указан OPENAI_API_KEY)"
    
    prompt = (
        "Ты — помощник собственника строительной фирмы. "
        "Проанализируй краткую сводку по сменам и ресурсам: сравни с предыдущим днём, "
        "обозначь причины отклонений (гипотезы) и дай 3–5 конкретных управленческих рекомендаций. "
        "Кратко и по делу, на русском языке.\n\n" + _prompt_from_kpis(today, yesterday)
    )
    
    try:
        # Минимальный клиент OpenAI (HTTP)
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": OPENAI_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 1000
                }
            )
            r.raise_for_status()
            data = r.json()
            
        result = data["choices"][0]["message"]["content"].strip()
        log.info(f"Generated insights for {today['date']}")
        return result
        
    except httpx.HTTPStatusError as e:
        log.error(f"OpenAI API error: {e.response.status_code} - {e.response.text}")
        return _prompt_from_kpis(today, yesterday) + f"\n\n❌ Ошибка AI-анализа: {e.response.status_code}"
    except Exception as e:
        log.error(f"Error generating insights: {e}", exc_info=True)
        return _prompt_from_kpis(today, yesterday) + f"\n\n❌ Ошибка AI-анализа: {e}"

