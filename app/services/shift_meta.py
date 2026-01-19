"""Вспомогательные функции для работы с типами смены и связанными полями."""

from __future__ import annotations

from typing import Dict


SHIFT_TYPE_MAP: Dict[str, Dict[str, str]] = {
    "day": {
        "bitrix": "Дневная",
        "display": "Дневная смена",
    },
    "night": {
        "bitrix": "Ночная",
        "display": "Ночная смена",
    },
    "evening": {
        "bitrix": "Вечерняя",
        "display": "Вечерняя смена",
    },
    "morning": {
        "bitrix": "Утренняя",
        "display": "Утренняя смена",
    },
}

SHIFT_STATUS_MAP: Dict[str, Dict[str, str]] = {
    "open": {
        "bitrix": "Открыта",
        "display": "Открыта",
    },
    "closed": {
        "bitrix": "Закрыта",
        "display": "Закрыта",
    },
}


def normalize_shift_type(code: str | None) -> str:
    """Приводит код типа смены к нижнему регистру."""
    if not code:
        return ""
    return str(code).strip().lower()


def shift_type_bitrix_label(code: str | None) -> str:
    """Возвращает человекочитаемое значение для записи в Bitrix."""
    normalized = normalize_shift_type(code)
    return SHIFT_TYPE_MAP.get(normalized, {}).get("bitrix") or (code or "")


def shift_type_display_label(code: str | None) -> str:
    """Возвращает строку для отображения в ЛПА / интерфейсе."""
    normalized = normalize_shift_type(code)
    return SHIFT_TYPE_MAP.get(normalized, {}).get("display") or (
        (str(code).strip().capitalize() + " смена") if code else ""
    )


def shift_status_bitrix_label(code: str | None) -> str | None:
    """Возвращает значение статуса для записи в Bitrix (enumeration)."""
    if not code:
        return None
    normalized = str(code).strip().lower()
    if normalized in SHIFT_STATUS_MAP:
        return SHIFT_STATUS_MAP[normalized]["bitrix"]
    # Если передали уже русское название — используем как есть
    return str(code).strip()


def shift_status_display_label(code: str | None) -> str:
    """Возвращает человекочитаемое значение статуса для отчётов."""
    if not code:
        return ""
    normalized = str(code).strip().lower()
    if normalized in SHIFT_STATUS_MAP:
        return SHIFT_STATUS_MAP[normalized]["display"]
    return str(code).strip()


