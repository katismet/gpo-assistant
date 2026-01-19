from aiogram.fsm.state import StatesGroup, State

class PlanFlow(StatesGroup):
    pick_object = State()
    pick_date = State()
    pick_works = State()
    confirm = State()

class ReportFlow(StatesGroup):
    input_facts = State()

class ResourceFlow(StatesGroup):
    """FSM состояния для W3 Resource Management."""
    # Общие шаги
    choose_object = State()
    choose_shift = State()
    choose_type = State()
    
    # Ветка техники
    equip_type = State()
    equip_hours = State()
    equip_rate_type = State()
    equip_rate = State()
    
    # Ветка материалов
    mat_type = State()
    mat_qty = State()
    mat_unit = State()
    mat_price = State()
    
    # Общие финальные шаги
    resource_comment = State()  # Опциональный комментарий
    resource_photos = State()   # Опциональные фото (можно несколько)
    
    # Финальный шаг
    confirm_resource = State()


class TimesheetFlow(StatesGroup):
    """FSM состояния для W4 Timesheet Management."""
    choose_object = State()
    choose_shift = State()
    input_worker = State()      # Бригада/сотрудник
    input_hours = State()       # Часы
    input_rate = State()        # Ставка
    timesheet_comment = State() # Опциональный комментарий
    timesheet_photos = State()  # Опциональные фото
    confirm_timesheet = State()


class ReportFlow(StatesGroup):
    input_facts = State()
    downtime_reason = State()   # Опциональная причина простоя
    shift_photos = State()      # Опциональные фото смены