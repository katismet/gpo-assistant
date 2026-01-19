from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.models import Shift
from app.db import session_scope
import logging

router = Router(name="root")
log = logging.getLogger("gpo.root")

def main_menu() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="ПЛАН на день", callback_data="act:plan")
    kb.button(text="ОТЧЁТ за смену", callback_data="act:report")
    kb.button(text="Техника/Материалы", callback_data="act:resources")
    kb.button(text="Табель", callback_data="act:tab")
    kb.button(text="📄 ЛПА", callback_data="act:lpa")
    kb.button(text="Мои объекты", callback_data="act:objects")
    kb.adjust(2,2,1,1)
    return kb.as_markup()

# Обработчик /start перенесен в app/handlers/menu.py для ролевого меню
# @router.message(CommandStart())
# async def start(m: types.Message):
#     log.debug("start from %s", m.from_user.id)
#     await m.answer("ГПОПомощник. Выберите действие:", reply_markup=main_menu())

@router.message(Command("resource"))
async def resource_command(m: types.Message, state: FSMContext):
    """Команда для быстрого старта W3."""
    from app.telegram.flow_resources import start_resource_flow
    from aiogram.types import CallbackQuery
    
    # Создаем фиктивный CallbackQuery для переиспользования логики
    fake_cq = CallbackQuery(
        id="fake",
        from_user=m.from_user,
        message=m,
        data="act:resources"
    )
    
    await start_resource_flow(fake_cq, state)

# @router.message(Command("debug_w3"))  # Перемещено в app/handlers/debug.py
# async def debug_w3(m: types.Message):
#     """Отладочная команда для тестирования W3."""
#     ... (удалено, теперь в app/handlers/debug.py)

@router.message(Command("diag"))
async def diag(m: types.Message):
    from app.services.bitrix_ids import OBJECT_ETID, SHIFT_ETID
    await m.answer(f"ok | obj={OBJECT_ETID} shift={SHIFT_ETID}")

@router.message(Command("last"))
async def last(m: types.Message):
    with session_scope() as s:
        sh = s.query(Shift).order_by(Shift.id.desc()).first()
        if not sh:
            await m.answer("Смен нет.")
            return
        await m.answer(
            f"Смена #{sh.id}\nСтатус: {sh.status}\n"
            f"План: {sh.plan_json}\nФакт: {sh.fact_json}\n"
            f"eff_raw={sh.eff_raw}% eff_final={sh.eff_final}%"
        )

# Универсальный перехватчик удален - обработка act:plan и act:report перенесена в соответствующие роутеры

# Обработчик act:tab перенесен в app/telegram/flow_timesheet.py
# @router.callback_query(F.data=="act:tab")
# async def _tab(cq: types.CallbackQuery):
#     await cq.answer()
#     await cq.message.answer("Раздел «Табель» в разработке.")

@router.callback_query(F.data=="act:objects")
async def _objects(cq: types.CallbackQuery):
    await cq.answer()
    await cq.message.answer("Список объектов берётся из Bitrix. Для работы используйте «ПЛАН»/«ОТЧЁТ».")
