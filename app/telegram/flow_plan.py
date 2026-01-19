from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from .fsm_states import PlanFlow
from app.services.shift_repo import save_plan
from app.services.objects import fetch_all_objects
from .objects_ui import page_kb
from app.utils.parsing import kv_pairs
from app.services.lpa_utils import build_plan_json_from_raw
from app.bitrix_field_map import resolve_code, upper_to_camel
from app.config import settings
import logging
import json

router = Router(name="flow_plan")
log = logging.getLogger("gpo.plan")
lpa_log = logging.getLogger("gpo.lpa")


async def save_plan_to_bitrix(shift_id: int, plan_tasks: list, meta: dict, bx):
    """Явная запись плана в Bitrix24 с нормализацией данных.
    
    Args:
        shift_id: Bitrix ID смены (не локальный shift_id!)
        plan_tasks: Список задач плана
        meta: Метаданные (object_bitrix_id, object_name, date, section, foreman, shift_type)
        bx: Функция для вызова Bitrix API
    """
    log.info(f"[PLAN SAVE] ===== START save_plan_to_bitrix =====")
    log.info(f"[PLAN SAVE] shift_id (bitrix_id)={shift_id}, plan_tasks_count={len(plan_tasks)}")
    log.info(f"[PLAN SAVE] meta keys: {list(meta.keys())}")
    
    def _num(x):
        try:
            return float(str(x).replace(',', '.'))
        except Exception:
            return 0.0
    
    tasks_norm = [{
        "name": t.get("name", "").strip(),
        "unit": (t.get("unit") or "ед.").strip(),
        "plan": _num(t.get("plan", 0)),
        "executor": (t.get("executor") or "Бригада").strip(),
    } for t in plan_tasks]
    
    # ВСЕГДА считаем total_plan как сумму всех задач
    # Если явно передан total_plan в meta, используем его только если он больше суммы задач
    total_plan_from_tasks = sum(_num(t["plan"]) for t in tasks_norm)
    total_plan_explicit = meta.get("total_plan") or meta.get("plan_total")
    if total_plan_explicit:
        total_plan_explicit = _num(total_plan_explicit)
        # Используем явно переданный только если он больше суммы задач (возможно, есть дополнительные работы)
        total_plan = max(total_plan_from_tasks, total_plan_explicit)
        if total_plan_explicit > total_plan_from_tasks:
            log.info(f"[PLAN SAVE] Using explicit total_plan={total_plan_explicit} (sum of tasks={total_plan_from_tasks})")
    else:
        total_plan = total_plan_from_tasks
    
    log.info(f"[PLAN SAVE] Normalized tasks: {len(tasks_norm)}, total_plan={total_plan} (calculated from tasks: {total_plan_from_tasks})")
    
    # Формируем meta с данными объекта (если есть)
    meta_dict = {}
    if meta.get("object_bitrix_id"):
        meta_dict["object_bitrix_id"] = int(meta["object_bitrix_id"])
    if meta.get("object_name"):
        meta_dict["object_name"] = str(meta["object_name"]).strip()
    
    plan_json = {
        "tasks": tasks_norm,
        "total_plan": total_plan,
        "date": meta.get("date"),
        "section": meta.get("section"),
        "foreman": meta.get("foreman"),
        "shift_type": meta.get("shift_type"),
    }
    
    # Добавляем meta только если есть данные объекта
    if meta_dict:
        plan_json["meta"] = meta_dict
        log.info(f"[PLAN SAVE] Plan JSON includes meta: object_bitrix_id={meta_dict.get('object_bitrix_id')}, object_name={meta_dict.get('object_name')}")
        lpa_log.info("[LPA] Plan JSON includes meta: object_bitrix_id=%s, object_name=%s", 
                     meta_dict.get("object_bitrix_id"), meta_dict.get("object_name"))
    
    # Определяем реальные коды полей Bitrix24
    f_plan_json = resolve_code("Смена", "UF_PLAN_JSON")
    f_plan_json_camel = upper_to_camel(f_plan_json) if f_plan_json else None
    f_plan_total = resolve_code("Смена", "UF_PLAN_TOTAL")
    f_plan_total_camel = upper_to_camel(f_plan_total) if f_plan_total else None
    f_object_link = resolve_code("Смена", "UF_OBJECT_LINK")
    f_object_link_camel = upper_to_camel(f_object_link) if f_object_link else None
    
    log.info(f"[PLAN SAVE] Field codes: UF_PLAN_JSON={f_plan_json}, camelCase={f_plan_json_camel}")
    log.info(f"[PLAN SAVE] Field codes: UF_PLAN_TOTAL={f_plan_total}, camelCase={f_plan_total_camel}")
    
    fields_payload = {}
    plan_json_str = json.dumps(plan_json, ensure_ascii=False)
    if f_plan_json_camel:
        fields_payload[f_plan_json_camel] = plan_json_str
        log.info(f"[PLAN SAVE] Using field: {f_plan_json_camel}")
    else:
        fields_payload["ufCrm7UfPlanJson"] = plan_json_str
        log.info(f"[PLAN SAVE] Using fallback field: ufCrm7UfPlanJson")
    
    log.info(f"[PLAN SAVE] Plan JSON string length: {len(plan_json_str)} chars")
    log.info(f"[PLAN SAVE] Plan JSON preview (first 200 chars): {plan_json_str[:200]}...")
    
    plan_total_value = float(total_plan)
    if f_plan_total_camel:
        fields_payload[f_plan_total_camel] = plan_total_value
    else:
        fields_payload["ufCrm7UfCrmPlanTotal"] = plan_total_value

    # Привязка к объекту в Bitrix (для отображения колонки «Объект»)
    object_bitrix_id = meta_dict.get("object_bitrix_id") or meta.get("object_bitrix_id")
    if object_bitrix_id and f_object_link_camel:
        fields_payload[f_object_link_camel] = [f"D_{int(object_bitrix_id)}"]
        log.info(f"[PLAN SAVE] Linking shift to object via {f_object_link_camel}: D_{int(object_bitrix_id)}")

    assigned_by = meta.get("assigned_by_id") or settings.BITRIX_DEFAULT_ASSIGNEE_ID
    if assigned_by:
        try:
            fields_payload["assignedById"] = int(assigned_by)
            log.info(f"[PLAN SAVE] assignedById set to {fields_payload['assignedById']}")
        except (TypeError, ValueError):
            log.warning(f"[PLAN SAVE] Invalid assigned_by_id value: {assigned_by}")
    
    payload = {
        "entityTypeId": 1050,
        "id": int(shift_id),
        "fields": fields_payload,
    }
    
    log.info(f"[PLAN SAVE] Full payload to crm.item.update:")
    log.info(f"[PLAN SAVE]   entityTypeId: {payload['entityTypeId']}")
    log.info(f"[PLAN SAVE]   id: {payload['id']}")
    log.info(f"[PLAN SAVE]   fields keys: {list(payload['fields'].keys())}")
    for field_key, field_value in payload['fields'].items():
        if isinstance(field_value, str) and len(field_value) > 200:
            log.info(f"[PLAN SAVE]   {field_key}: <string length={len(field_value)}>")
        else:
            log.info(f"[PLAN SAVE]   {field_key}: {field_value}")
    
    try:
        res = await bx("crm.item.update", payload)
        log.info(f"[PLAN SAVE] Bitrix API response: success=True")
        log.info(f"[PLAN SAVE] Response keys: {list(res.keys()) if isinstance(res, dict) else 'not a dict'}")
        if isinstance(res, dict) and "result" in res:
            log.info(f"[PLAN SAVE] Response result: {res['result']}")
        lpa_log.info("[LPA] UF_PLAN_JSON updated | shift=%s total_plan=%.2f tasks=%d", shift_id, total_plan, len(tasks_norm))
        shift_type_meta = meta.get("shift_type")
        if shift_type_meta:
            try:
                from app.services.shift_client import bitrix_update_shift_type
                await bitrix_update_shift_type(shift_id, shift_type_meta)
            except Exception as type_err:
                log.warning(f"[PLAN SAVE] Could not update shift type: {type_err}")
        log.info(f"[PLAN SAVE] ===== END save_plan_to_bitrix: SUCCESS =====")
        return res
    except Exception as e:
        log.error(f"[PLAN SAVE] Bitrix API error: {e}", exc_info=True)
        log.error(f"[PLAN SAVE] ===== END save_plan_to_bitrix: ERROR =====")
        raise


async def objects_kb(page=0):
    objects, has_next = await fetch_objects_page(page, 8)
    # Convert to list format expected by objects_page_kb (поддерживаем новый формат с кодом)
    # Если объекты в формате (bitrix_id, title, code), оставляем как есть
    # Если в формате (bitrix_id, title), оставляем как есть (page_kb поддерживает оба формата)
    obj_list = objects  # page_kb теперь поддерживает оба формата
    return objects_page_kb(obj_list, page)

def dates_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Сегодня", callback_data="date:today")
    kb.button(text="Завтра", callback_data="date:tomorrow")
    kb.adjust(2)
    return kb.as_markup()

@router.callback_query(F.data == "act:plan")
async def start_plan(cq: types.CallbackQuery, state: FSMContext):
    try:
        await cq.answer()
        await state.clear()
        log.debug("step=start_plan, user=%s data=%s", cq.from_user.id, await state.get_data())
        await state.set_state(PlanFlow.pick_object)
        
        # Загружаем все объекты и кэшируем
        objs = await fetch_all_objects()
        await state.update_data(objects_cache=objs, page=0)
        await cq.message.edit_text("Выберите объект:", reply_markup=page_kb(objs, 0, "obj"))
    except Exception as e:
        log.error("Error in start_plan: %s", e)
        await cq.answer("Ошибка при загрузке объектов")

@router.callback_query(PlanFlow.pick_object, F.data.startswith("obj:page:"))
async def obj_page(cq: types.CallbackQuery, state: FSMContext):
    await cq.answer()
    data = await state.get_data()
    objs = data.get("objects_cache", [])
    page = int(cq.data.split(":")[-1])
    await state.update_data(page=page)
    await cq.message.edit_reply_markup(reply_markup=page_kb(objs, page, "obj"))

@router.callback_query(PlanFlow.pick_object, F.data.startswith("obj:") & ~F.data.contains(":page:"))
async def set_object(cq: types.CallbackQuery, state: FSMContext):
    await cq.answer()
    # Извлекаем Bitrix ID объекта из callback_data
    object_bitrix_id = int(cq.data.split(":")[1])
    
    # Получаем название объекта из кэша (поддерживаем старый и новый формат)
    data = await state.get_data()
    objects_cache = data.get("objects_cache", [])
    # Поддерживаем формат (bitrix_id, title, code) и (bitrix_id, title)
    object_name = None
    for obj_data in objects_cache:
        obj_id = obj_data[0] if isinstance(obj_data, (list, tuple)) else obj_data
        if obj_id == object_bitrix_id:
            object_name = obj_data[1] if len(obj_data) > 1 else f"Объект #{object_bitrix_id}"
            break
    if not object_name:
        object_name = f"Объект #{object_bitrix_id}"
    
    # Сохраняем и object_bitrix_id, и object_name в FSM
    await state.update_data(
        object_id=object_bitrix_id,  # Для обратной совместимости
        object_bitrix_id=object_bitrix_id,  # Bitrix ID объекта
        object_name=object_name  # Полное название из Bitrix
    )
    log.info(f"[OBJECT] Selected object: bitrix_id={object_bitrix_id}, name={object_name}")
    await state.set_state(PlanFlow.pick_date)
    await cq.message.edit_text("Дата плана?", reply_markup=dates_kb())

@router.callback_query(PlanFlow.pick_date, F.data.startswith("date:"))
async def set_date(cq: types.CallbackQuery, state: FSMContext):
    await cq.answer()
    await state.update_data(plan_date=cq.data.split(":")[1])
    await state.set_state(PlanFlow.pick_works)
    await cq.message.edit_text("Укажите объёмы в формате: земляные=120, подушка=80, щебень=20")

@router.message(PlanFlow.pick_works)
async def set_works(m: types.Message, state: FSMContext):
    log.debug("step=set_works, user=%s data=%s", m.from_user.id, await state.get_data())
    try:
        plan = kv_pairs(m.text)
    except ValueError as e:
        await m.answer(f"Ошибка формата: {e}. Пример: земляные=120, подушка=80, щебень=20")
        return
    await state.update_data(plan=plan)
    data = await state.get_data()
    text = (
        "Подтвердите план\n"
        f"Объект: {data['object_id']}\n"
        f"Дата: {data['plan_date']}\n"
        f"Работы: {plan}"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="Подтвердить", callback_data="plan:ok")
    kb.button(text="Исправить", callback_data="plan:edit")
    await state.set_state(PlanFlow.confirm)
    await m.answer(text, reply_markup=kb.as_markup())

@router.callback_query(PlanFlow.confirm, F.data == "plan:edit")
async def back_to_edit(cq: types.CallbackQuery, state: FSMContext):
    await cq.answer()
    await state.set_state(PlanFlow.pick_works)
    await cq.message.edit_text("Исправьте объёмы: земляные=120, подушка=80, щебень=20")

@router.callback_query(PlanFlow.confirm, F.data == "plan:ok")
async def plan_ok(cq: types.CallbackQuery, state: FSMContext):
    await cq.answer("Сохранено")
    data = await state.get_data()
    
    # Логируем данные плана перед сохранением
    plan_dict = data.get("plan", {})
    log.info(f"[PLAN SAVE] Input plan keys: {list(plan_dict.keys()) if isinstance(plan_dict, dict) else 'not a dict'}")
    log.info(f"[PLAN SAVE] Input plan content: {plan_dict}")
    log.info(f"[PLAN SAVE] Input plan type: {type(plan_dict)}")
    
    # Проверяем, что план не пустой
    if not plan_dict or (isinstance(plan_dict, dict) and len(plan_dict) == 0):
        log.warning(f"[PLAN SAVE] Plan is empty! data keys: {list(data.keys())}")
        await cq.message.answer("❌ План пуст. Пожалуйста, укажите объёмы работ.")
        return
    
    # Получаем название объекта и Bitrix ID из FSM (уже сохранены при выборе объекта)
    object_bitrix_id = data.get("object_bitrix_id") or data.get("object_id")  # Используем object_bitrix_id, если есть
    object_name = data.get("object_name") or f"Объект #{object_bitrix_id}"
    
    # Если object_name не был сохранен, получаем из Bitrix
    if not data.get("object_name"):
        from app.services.objects import fetch_all_objects
        objects = await fetch_all_objects()
        # Поддерживаем формат (bitrix_id, title, code) и (bitrix_id, title)
        object_name = None
        for obj_data in objects:
            obj_id = obj_data[0] if isinstance(obj_data, (list, tuple)) else obj_data
            if obj_id == object_bitrix_id:
                object_name = obj_data[1] if len(obj_data) > 1 else f"Объект #{object_bitrix_id}"
                break
        if not object_name:
            object_name = f"Объект #{object_bitrix_id}"
    
    log.info(f"[PLAN SAVE] Using object: object_bitrix_id={object_bitrix_id}, object_name={object_name}")
    
    # Форматируем дату
    from datetime import date as dt_date, timedelta
    if data["plan_date"] == "today":
        date_val = dt_date.today()
        formatted_date_display = "Сегодня"
    else:
        date_val = dt_date.today() + timedelta(days=1)
        formatted_date_display = "Завтра"
    date_str = date_val.strftime("%d.%m.%Y")
    
    # Сохраняем план с дополнительными полями
    shift_type_code = "day"

    try:
        plan_json = build_plan_json_from_raw(
            plan_dict,
            object_name=object_name,
            date=date_str,
            section="Строительство",
            foreman="Прораб",
            shift_type=shift_type_code
        )
        plan_total = plan_json.get("total_plan", 0.0)

        log.info(f"[PLAN SAVE] Saving plan to DB: tasks={len(plan_json.get('tasks', []))}, total={plan_total}")
        # ВАЖНО: Используем object_bitrix_id для записи в локальную БД
        shift_id = save_plan(
            object_bitrix_id,  # Используем Bitrix ID объекта, а не локальный ID
            data["plan_date"], 
            plan_json,
            object_name=object_name,
            date=date_str,
            section="Строительство",
            foreman="Прораб"
        )
        log.info(f"[PLAN SAVE] Saved to DB with shift_id={shift_id}")
    except Exception as e:
        log.error(f"Error saving plan to local DB: {e}", exc_info=True)
        # Продолжаем работу даже если локальная БД недоступна
        # Используем фиктивный ID для продолжения работы
        shift_id = 99999
        log.warning(f"Using fake shift_id={shift_id} due to DB error")
        plan_json = build_plan_json_from_raw(
            plan_dict,
            object_name=object_name,
            date=date_str,
            section="Строительство",
            foreman="Прораб",
            shift_type=shift_type_code
        )
        plan_total = plan_json.get("total_plan", 0.0)
    
    # Получаем или создаем смену в Bitrix через единую функцию
    from app.services.shift_client import (
        bitrix_get_shift_for_object_and_date,
        bitrix_update_shift_type,
    )
    from app.services.bitrix_ids import SHIFT_ETID
    from app.db import session_scope
    from app.models import Shift
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    # ВАЖНО: Используем object_bitrix_id из FSM (это Bitrix ID объекта)
    object_bitrix_id = data.get("object_bitrix_id") or data.get("object_id")
    if not object_bitrix_id:
        log.error(f"[PLAN SAVE] object_bitrix_id not found in FSM data: {list(data.keys())}")
        raise ValueError("object_bitrix_id not found in FSM")
    
    # Получаем или создаем смену через единую функцию
    bx_id, _ = await bitrix_get_shift_for_object_and_date(
        object_bitrix_id=object_bitrix_id,
        target_date=date_val,
        create_if_not_exists=True,
    )
    
    if not bx_id:
        log.error(f"[PLAN SAVE] Failed to get or create shift for object={object_bitrix_id}, date={date_val}")
        await cq.message.answer("❌ Ошибка: не удалось создать или найти смену в Bitrix24")
        return
    
    log.info(f"[PLAN SAVE] Using shift_bitrix_id={bx_id} for object={object_bitrix_id}, date={date_val}")
    
    # Обновляем существующую смену планом
    try:
        import json
        # Явная запись плана в Bitrix24 с нормализацией
        # ВАЖНО: Вызываем всегда, даже если tasks пустой, чтобы записать meta с объектом
        try:
            from app.services.http_client import bx as bx_client
            plan_tasks_list = plan_json.get("tasks", [])
            log.info(f"[PLAN SAVE] Calling save_plan_to_bitrix: bx_id={bx_id}, tasks_count={len(plan_tasks_list)}, object_bitrix_id={object_bitrix_id}, object_name={object_name}")
            # Передаем данные объекта в meta для сохранения в plan_json
            await save_plan_to_bitrix(
                bx_id,
                plan_tasks_list,
                {
                    "date": date_str,
                    "shift_type": shift_type_code,
                    "section": "Строительство",
                    "foreman": "Прораб",
                    "object_bitrix_id": object_bitrix_id,  # Bitrix ID объекта
                    "object_name": object_name,  # Полное название из Bitrix
                },
                bx_client
            )
            await bitrix_update_shift_type(bx_id, shift_type_code)
            log.info(f"[PLAN SAVE] save_plan_to_bitrix completed successfully for bx_id={bx_id}")
        except Exception as e:
            log.error(f"[PLAN SAVE] Could not save plan to Bitrix24 explicitly: {e}", exc_info=True)
            lpa_log.error(f"[PLAN SAVE] Could not save plan to Bitrix24 explicitly: {e}", exc_info=True)
        
        # Сохраняем bitrix_id в локальную БД
        try:
            with session_scope() as s:
                sh = s.get(Shift, shift_id)
                if sh:
                    sh.bitrix_id = bx_id
            log.info(f"Saved bitrix_id={bx_id} for shift_id={shift_id}")
        except Exception as e:
            log.warning(f"Could not save bitrix_id to local DB: {e}")
    except Exception as e:
        log.error(f"Error creating shift in Bitrix24: {e}", exc_info=True)
        # Продолжаем работу даже если Bitrix24 недоступен
    
    # Предлагаем следующие шаги
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Перейти к отчёту", callback_data="plan:act:report")
    kb.button(text="🔄 Добавить ресурс", callback_data="plan:act:resources")
    kb.button(text="👥 Добавить табель", callback_data="plan:act:tab")
    kb.button(text="🏠 В главное меню", callback_data="back_to_menu")
    kb.adjust(1, 1, 1, 1)
    
    success_msg = f"✅ <b>План сохранён!</b>\n\n"
    success_msg += f"ID смены: {shift_id}\n"
    if bx_id:
        success_msg += f"Bitrix ID: {bx_id}\n"
    success_msg += f"\nОбъект: {object_name}\n"
    success_msg += f"Дата: {formatted_date_display}\n"
    success_msg += f"Плановый объём: {plan_total:.1f}\n\n"
    success_msg += "Что дальше?"
    
    await state.clear()
    await cq.message.edit_text(success_msg, reply_markup=kb.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_from_plan(cq: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню."""
    await cq.answer()
    await state.clear()
    from app.handlers.menu import kb_main, role_of
    role = role_of(cq.message)
    await cq.message.edit_text(
        "ГПО-Помощник. Выберите действие:",
        reply_markup=kb_main(role)
    )

@router.callback_query(F.data == "plan:act:report")
async def go_to_report_from_plan(cq: types.CallbackQuery, state: FSMContext):
    """Переход к отчету из плана."""
    await cq.answer()
    await state.clear()
    from app.services.objects import fetch_all_objects
    from app.telegram.objects_ui import page_kb
    objs = await fetch_all_objects()
    await state.update_data(objects_cache=objs, page=0)
    await cq.message.edit_text("Выберите объект:", reply_markup=page_kb(objs, 0, "repobj"))

@router.callback_query(F.data == "plan:act:resources")
async def go_to_resources_from_plan(cq: types.CallbackQuery, state: FSMContext):
    """Переход к ресурсам из плана."""
    from app.telegram.flow_resources import start_resource_flow
    await start_resource_flow(cq, state)

@router.callback_query(F.data == "plan:act:tab")
async def go_to_timesheet_from_plan(cq: types.CallbackQuery, state: FSMContext):
    """Переход к табелю из плана."""
    from app.telegram.flow_timesheet import start_timesheet_flow
    await start_timesheet_flow(cq, state)