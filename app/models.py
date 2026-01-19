"""Модели базы данных."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class UserRole(str, Enum):
    """Роли пользователей."""

    FOREMAN = "foreman"  # Прораб
    OWNER = "owner"  # Владелец


class ShiftType(str, Enum):
    """Типы смен."""

    DAY = "day"  # Дневная
    NIGHT = "night"  # Ночная


class ShiftStatus(str, Enum):
    """Статусы смен."""

    OPEN = "open"  # Открыта
    CLOSED = "closed"  # Закрыта


class ResourceKind(str, Enum):
    """Типы ресурсов."""

    MACHINERY = "machinery"  # Техника
    MATERIAL = "material"  # Материал


class TariffType(str, Enum):
    """Типы тарифов."""

    HOUR = "hour"  # Почасовая
    SHIFT = "shift"  # За смену
    TRIP = "trip"  # За рейс


class WorkflowState(str, Enum):
    """Состояния рабочих процессов."""

    # W0 - ACL и меню
    MENU = "menu"
    
    # W1 - План
    PLAN_START = "plan_start"
    PLAN_OBJECT_SELECT = "plan_object_select"
    PLAN_SHIFT_SELECT = "plan_shift_select"
    PLAN_RESOURCES = "plan_resources"
    PLAN_CONFIRM = "plan_confirm"
    
    # W2 - Отчёт
    REPORT_START = "report_start"
    REPORT_PLAN_FACT = "report_plan_fact"
    REPORT_INCIDENTS = "report_incidents"
    REPORT_DOWNTIME = "report_downtime"
    REPORT_CONFIRM = "report_confirm"
    
    # W3/W4 - Ресурсы
    RESOURCES_TECHNIQUE = "resources_technique"
    RESOURCES_MATERIALS = "resources_materials"
    RESOURCES_TIMESHEET = "resources_timesheet"
    
    # W5 - Объекты
    OBJECTS_LIST = "objects_list"
    OBJECTS_DETAILS = "objects_details"


class User(Base):
    """Пользователь системы."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), nullable=False)
    bitrix_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи
    shifts: Mapped[list["Shift"]] = relationship("Shift", back_populates="created_by_user")


class Object(Base):
    """Объект."""

    __tablename__ = "objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    bitrix_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Связи
    shifts: Mapped[list["Shift"]] = relationship("Shift", back_populates="object")


class Shift(Base):
    """Смена."""

    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    object_id: Mapped[int] = mapped_column(Integer, ForeignKey("objects.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    type: Mapped[ShiftType] = mapped_column(SQLEnum(ShiftType), nullable=False)
    plan_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    fact_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    uf_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    uf_end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    uf_downtime_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    uf_downtime_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uf_incidents_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completeness: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    eff_raw: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    eff_user: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    eff_final: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[ShiftStatus] = mapped_column(SQLEnum(ShiftStatus), default=ShiftStatus.OPEN)
    bitrix_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # ID смены в Bitrix24
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи
    object: Mapped["Object"] = relationship("Object", back_populates="shifts")
    created_by_user: Mapped["User"] = relationship("User", back_populates="shifts")
    resources: Mapped[list["Resource"]] = relationship("Resource", back_populates="shift")
    timesheets: Mapped[list["Timesheet"]] = relationship("Timesheet", back_populates="shift")

    # Индексы
    __table_args__ = (
        Index("ix_shifts_object_date_type", "object_id", "date", "type"),
    )


class Resource(Base):
    """Ресурс."""

    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_id: Mapped[int] = mapped_column(Integer, ForeignKey("shifts.id"), nullable=False)
    kind: Mapped[ResourceKind] = mapped_column(SQLEnum(ResourceKind), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    tariff: Mapped[Optional[TariffType]] = mapped_column(SQLEnum(TariffType), nullable=True)
    meta_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Связи
    shift: Mapped["Shift"] = relationship("Shift", back_populates="resources")


class Timesheet(Base):
    """Табель."""

    __tablename__ = "timesheets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_id: Mapped[int] = mapped_column(Integer, ForeignKey("shifts.id"), nullable=False)
    crew: Mapped[str] = mapped_column(String(500), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Связи
    shift: Mapped["Shift"] = relationship("Shift", back_populates="timesheets")


class Param(Base):
    """Параметры системы."""

    __tablename__ = "params"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
