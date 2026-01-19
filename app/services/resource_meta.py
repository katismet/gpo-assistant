"""Маппинги для типов ресурсов и тарифов."""

from __future__ import annotations

from typing import Dict


RESOURCE_TYPE_MAP: Dict[str, Dict[str, str]] = {
    "MAT": {"bitrix": "Материал", "display": "Материалы"},
    "EQUIP": {"bitrix": "Техника", "display": "Техника"},
    "HR": {"bitrix": "Рабочая сила", "display": "Рабочая сила"},
}

RATE_TYPE_MAP: Dict[str, str] = {
    "HOUR": "час",
    "SHIFT": "смена",
    "TRIP": "рейс",
}


def normalize(value: str | None) -> str:
    return str(value or "").strip().upper()


def resource_type_bitrix_label(code: str | None) -> str | None:
    normalized = normalize(code)
    if normalized in RESOURCE_TYPE_MAP:
        return RESOURCE_TYPE_MAP[normalized]["bitrix"]
    return None


def resource_type_display_label(code: str | None) -> str:
    normalized = normalize(code)
    if normalized in RESOURCE_TYPE_MAP:
        return RESOURCE_TYPE_MAP[normalized]["display"]
    return str(code or "").strip()


def rate_type_bitrix_label(code: str | None) -> str | None:
    normalized = normalize(code)
    if normalized in RATE_TYPE_MAP:
        return RATE_TYPE_MAP[normalized]
    return None


