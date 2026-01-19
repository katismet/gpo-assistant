"""Pydantic схемы для валидации данных."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models import EfficiencyType, UserRole, WorkflowState


class UserBase(BaseModel):
    """Базовая схема пользователя."""

    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: UserRole = UserRole.WORKER


class UserCreate(UserBase):
    """Схема создания пользователя."""

    pass


class UserUpdate(BaseModel):
    """Схема обновления пользователя."""

    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class User(UserBase):
    """Схема пользователя."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowBase(BaseModel):
    """Базовая схема рабочего процесса."""

    state: WorkflowState
    data: Optional[str] = None


class WorkflowCreate(WorkflowBase):
    """Схема создания рабочего процесса."""

    user_id: int


class WorkflowUpdate(BaseModel):
    """Схема обновления рабочего процесса."""

    state: Optional[WorkflowState] = None
    data: Optional[str] = None


class Workflow(WorkflowBase):
    """Схема рабочего процесса."""

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BitrixObjectBase(BaseModel):
    """Базовая схема объекта Bitrix24."""

    bitrix_id: int
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None


class BitrixObjectCreate(BitrixObjectBase):
    """Схема создания объекта Bitrix24."""

    pass


class BitrixObjectUpdate(BaseModel):
    """Схема обновления объекта Bitrix24."""

    name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None


class BitrixObject(BitrixObjectBase):
    """Схема объекта Bitrix24."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BitrixShiftBase(BaseModel):
    """Базовая схема смены Bitrix24."""

    bitrix_id: int
    object_id: int
    name: str
    start_date: datetime
    end_date: datetime
    status: Optional[str] = None


class BitrixShiftCreate(BitrixShiftBase):
    """Схема создания смены Bitrix24."""

    pass


class BitrixShiftUpdate(BaseModel):
    """Схема обновления смены Bitrix24."""

    name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None


class BitrixShift(BitrixShiftBase):
    """Схема смены Bitrix24."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BitrixResourceBase(BaseModel):
    """Базовая схема ресурса Bitrix24."""

    bitrix_id: int
    shift_id: int
    name: str
    resource_type: str
    quantity: Decimal
    unit: Optional[str] = None
    cost: Optional[Decimal] = None


class BitrixResourceCreate(BitrixResourceBase):
    """Схема создания ресурса Bitrix24."""

    pass


class BitrixResourceUpdate(BaseModel):
    """Схема обновления ресурса Bitrix24."""

    name: Optional[str] = None
    resource_type: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    cost: Optional[Decimal] = None


class BitrixResource(BitrixResourceBase):
    """Схема ресурса Bitrix24."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReportBase(BaseModel):
    """Базовая схема отчёта."""

    object_id: int
    shift_id: int
    report_type: str
    data: str


class ReportCreate(ReportBase):
    """Схема создания отчёта."""

    user_id: int


class ReportUpdate(BaseModel):
    """Схема обновления отчёта."""

    report_type: Optional[str] = None
    data: Optional[str] = None
    pdf_path: Optional[str] = None


class Report(ReportBase):
    """Схема отчёта."""

    id: int
    user_id: int
    pdf_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EfficiencyBase(BaseModel):
    """Базовая схема эффективности."""

    object_id: int
    shift_id: int
    efficiency_type: EfficiencyType
    value: Decimal = Field(..., ge=0, le=100)
    calculation_data: Optional[str] = None


class EfficiencyCreate(EfficiencyBase):
    """Схема создания эффективности."""

    user_id: int


class EfficiencyUpdate(BaseModel):
    """Схема обновления эффективности."""

    efficiency_type: Optional[EfficiencyType] = None
    value: Optional[Decimal] = Field(None, ge=0, le=100)
    calculation_data: Optional[str] = None


class Efficiency(EfficiencyBase):
    """Схема эффективности."""

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationBase(BaseModel):
    """Базовая схема уведомления."""

    title: str
    message: str
    notification_type: str
    scheduled_at: datetime


class NotificationCreate(NotificationBase):
    """Схема создания уведомления."""

    user_id: int


class NotificationUpdate(BaseModel):
    """Схема обновления уведомления."""

    title: Optional[str] = None
    message: Optional[str] = None
    notification_type: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    is_sent: Optional[bool] = None


class Notification(NotificationBase):
    """Схема уведомления."""

    id: int
    user_id: int
    is_sent: bool
    sent_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# Схемы для FSM состояний
class PlanData(BaseModel):
    """Данные для планирования."""

    object_id: Optional[int] = None
    shift_id: Optional[int] = None
    resources: Optional[dict] = None
    notes: Optional[str] = None


class ReportData(BaseModel):
    """Данные для отчёта."""

    object_id: Optional[int] = None
    shift_id: Optional[int] = None
    plan_fact: Optional[dict] = None
    incidents: Optional[list] = None
    downtime: Optional[list] = None
    notes: Optional[str] = None


class ResourceData(BaseModel):
    """Данные для ресурсов."""

    technique: Optional[list] = None
    materials: Optional[list] = None
    timesheet: Optional[list] = None
    notes: Optional[str] = None
