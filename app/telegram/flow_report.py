from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from .fsm_states import ReportFlow
from app.utils.parsing import kv_pairs
from app.services.shift_repo import get_last_open_shift, save_fact
from app.services.efficiency import compute_eff_raw, blend_eff
from app.services.bitrix import bx_post
from app.services.bitrix_ids import SHIFT_ETID, UF_EFF_RAW, UF_EFF_FINAL, UF_STATUS
from app.db import session_scope
from app.models import Shift
from .objects_ui import page_kb
from app.services.objects import fetch_all_objects
from app.services.lpa_utils import plan_tasks_from_json, build_fact_json_from_raw
from app.services.shift_client import bitrix_update_shift_aggregates
from typing import List
from datetime import datetime
import json

router = Router()

@router.callback_query(F.data=="act:report")
async def start_report(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    await state.clear()
    objs = await fetch_all_objects()
    await state.update_data(objects_cache=objs, page=0)
    await cq.message.answer("Выберите объект:", reply_markup=page_kb(objs, 0, "repobj"))

@router.callback_query(F.data.startswith("repobj:page:"))
async def repobj_page(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    page = int(cq.data.split(":")[-1])
    data = await state.get_data()
    objs = data.get("objects_cache", [])
    await cq.message.edit_reply_markup(reply_markup=page_kb(objs, page, "repobj"))
    await state.update_data(page=page)

@router.callback_query(F.data.startswith("repobj:") & ~F.data.contains(":page:"))
async def repobj_pick(cq: CallbackQuery, state: FSMContext):
    """Обработчик выбора объекта для отчета. Работает без фильтра по состоянию FSM."""
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
    
    import logging
    log = logging.getLogger("gpo.report")
    log.info(f"[OBJECT] Selected object: bitrix_id={object_bitrix_id}, name={object_name}")
    
    # Получаем смену через единую функцию (НЕ создаем новую, только ищем существующую)
    from datetime import date
    from app.services.shift_client import bitrix_get_shift_for_object_and_date
    from app.services.http_client import bx
    from app.services.bitrix_ids import SHIFT_ETID
    from app.bitrix_field_map import resolve_code, upper_to_camel
    
    shift_date = date.today()
    bitrix_shift_id = None
    plan_json = {}
    
    # Получаем смену через единую функцию (НЕ создаем новую)
    bitrix_shift_id, _ = await bitrix_get_shift_for_object_and_date(
        object_bitrix_id=object_bitrix_id,
        target_date=shift_date,
        create_if_not_exists=False,
    )
    
    if not bitrix_shift_id:
        log.warning(f"[SHIFT] no shift found for report object={object_bitrix_id} date={shift_date} – plan missing")
        await cq.message.answer(
            "❌ <b>Не найден план</b>\n\n"
            f"Не найдена смена с планом для объекта и даты.\n\n"
            "Сначала сформируйте <b>ПЛАН</b> для этого объекта.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    log.info(f"[REPORT] Found shift_bitrix_id={bitrix_shift_id} for object={object_bitrix_id}, date={shift_date}")
    
    # Получаем план из найденной смены
    try:
        import json
        f_plan_json = resolve_code("Смена", "UF_PLAN_JSON")
        f_plan_json_camel = upper_to_camel(f_plan_json) if f_plan_json and f_plan_json.startswith("UF_") else None
        
        # Получаем полные данные смены из Bitrix24
        shift_item = await bx("crm.item.get", {
            "entityTypeId": SHIFT_ETID,
            "id": bitrix_shift_id,
        })
        
        if shift_item:
            item = shift_item.get("item", shift_item) if isinstance(shift_item, dict) else shift_item
            # Пробуем получить план из Bitrix24 (если есть)
            plan_json_raw = item.get(f_plan_json_camel) or item.get("ufCrm7UfPlanJson") or ""
            if plan_json_raw:
                try:
                    plan_json = json.loads(plan_json_raw) if isinstance(plan_json_raw, str) else plan_json_raw
                    log.info(f"[REPORT] Loaded plan_json from shift {bitrix_shift_id}: {len(plan_json.get('tasks', []))} tasks")
                except Exception as e:
                    log.warning(f"Could not parse plan_json from Bitrix24: {e}")
                    plan_json = {}
            else:
                plan_json = {}
                log.info(f"[REPORT] No plan_json in shift {bitrix_shift_id}")
    except Exception as e:
        log.warning(f"Could not get plan from shift {bitrix_shift_id}: {e}", exc_info=True)
        plan_json = {}
    
    # Сохраняем данные в FSM
    if bitrix_shift_id:
        await state.update_data(
            shift_id=bitrix_shift_id, 
            plan_json=plan_json, 
            object_id=object_bitrix_id,  # Для обратной совместимости
            object_bitrix_id=object_bitrix_id,  # Bitrix ID объекта
            object_name=object_name  # Полное название из Bitrix
        )
        await state.set_state(ReportFlow.input_facts)
        await cq.message.answer("Введите факты: земляные=110, подушка=75, щебень=18")
        return
    
    # Пробуем найти смену в локальной базе (fallback)
    try:
        result = get_last_open_shift(object_bitrix_id)  # Используем Bitrix ID
        if result:
            shift_id, plan_json = result
            log.info(f"Found shift in local DB: {shift_id}, plan_json keys: {list(plan_json.keys())}")
            await state.update_data(
                shift_id=shift_id, 
                plan_json=plan_json, 
                object_id=object_bitrix_id,  # Для обратной совместимости
                object_bitrix_id=object_bitrix_id,  # Bitrix ID объекта
                object_name=object_name  # Полное название из Bitrix
            )
            await state.set_state(ReportFlow.input_facts)
            await cq.message.answer("Введите факты: земляные=110, подушка=75, щебень=18")
            return
    except Exception as e:
        log.error(f"Error getting shift from local DB: {e}", exc_info=True)
    
    # Если не нашли нигде
    log.warning(f"No shift found for object_bitrix_id={object_bitrix_id}, date={shift_date}")
    await cq.message.answer("Открытых смен не найдено. Сначала создайте ПЛАН.")
    await state.clear()

@router.message(ReportFlow.input_facts)
async def rep_input(m: Message, state: FSMContext):
    """Обработчик ввода фактов для отчета."""
    import logging
    log = logging.getLogger("gpo.report")
    
    data = await state.get_data()
    try:
        fact = kv_pairs(m.text)
    except ValueError as e:
        await m.answer(f"Ошибка формата: {e}\nПример: земляные=110, подушка=75, щебень=18")
        return

    plan = data.get("plan_json") or {}
    plan_tasks, _ = plan_tasks_from_json(plan, fallback_raw=plan)
    plan_for_eff = {task["name"]: task["plan"] for task in plan_tasks}
    shift_id = data.get("shift_id")
    
    if not shift_id:
        log.error("shift_id not found in state data")
        await m.answer("❌ Ошибка: не найден ID смены. Начните заново.")
        await state.clear()
        return
    
    try:
        shift_id = int(shift_id)
    except (ValueError, TypeError):
        log.error(f"Invalid shift_id: {shift_id}")
        await m.answer("❌ Ошибка: неверный ID смены. Начните заново.")
        await state.clear()
        return
    
    try:
        eff_raw = compute_eff_raw(plan_for_eff, fact)
        eff_final = blend_eff(eff_raw, None)
        
        # Создаем структуру fact_json (без downtime_reason и photos, они добавятся позже)
        fact_json_struct = build_fact_json_from_raw(
            fact,
            plan_tasks=plan_tasks,
            downtime_reason="",  # Будет добавлено позже
            photos=[],  # Будет добавлено позже
        )
        
        # Сохраняем факты в локальную БД только если shift_id - локальный ID
        # Если shift_id - это bitrix_id, пропускаем сохранение в локальную БД
        if shift_id < 100000:  # Локальные ID обычно меньше 100000
            try:
                save_fact(shift_id, fact, eff_raw, eff_final, plan_json=plan)
                log.info(f"Saved fact to local DB for shift_id={shift_id}")
            except Exception as e:
                log.warning(f"Could not save fact to local DB: {e}, continuing with Bitrix24 only")
        else:
            log.info(f"Skipping local DB save for bitrix_id={shift_id}")
        
        # Сохраняем факты в state для дальнейшего использования
        await state.update_data(fact=fact, eff_raw=eff_raw, eff_final=eff_final, fact_json=fact_json_struct)
        await state.set_state(ReportFlow.downtime_reason)
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb = InlineKeyboardBuilder()
        kb.button(text="⏭ Пропустить", callback_data="skip_downtime")
        kb.button(text="❌ Отмена", callback_data="cancel_report")
        kb.adjust(1, 1)
        
        await m.answer(
            "⏸ <b>Причина простоя</b> (опционально)\n\n"
            "Если был простой, укажите причину или нажмите «Пропустить»:",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        log.error(f"Error in rep_input: {e}", exc_info=True)
        await m.answer(f"❌ Ошибка обработки фактов: {e}\nПопробуйте еще раз.")

@router.callback_query(ReportFlow.downtime_reason, F.data == "skip_downtime")
async def skip_downtime_reason(cq: CallbackQuery, state: FSMContext):
    """Пропуск причины простоя."""
    await cq.answer()
    await state.update_data(downtime_reason="")
    await _ask_shift_photos(cq.message, state)

@router.message(ReportFlow.downtime_reason)
async def downtime_reason_input(message: Message, state: FSMContext):
    """Ввод причины простоя."""
    await state.update_data(downtime_reason=message.text)
    await _ask_shift_photos(message, state)

async def _ask_shift_photos(message: Message, state: FSMContext):
    """Спросить о фото для смены."""
    await state.set_state(ReportFlow.shift_photos)
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="📷 Добавить фото", callback_data="add_shift_photos")
    kb.button(text="⏭ Пропустить", callback_data="skip_shift_photos")
    kb.button(text="❌ Отмена", callback_data="cancel_report")
    kb.adjust(1, 1, 1)
    
    await message.answer(
        "📷 <b>Фото смены</b> (опционально)\n\n"
        "Вы можете добавить несколько фото. Отправьте фото или нажмите «Пропустить»:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(ReportFlow.shift_photos, F.data == "skip_shift_photos")
async def skip_shift_photos(cq: CallbackQuery, state: FSMContext):
    """Пропуск фото для смены."""
    await cq.answer()
    await state.update_data(shift_photos=[])
    await _save_report(cq.message, state)

@router.callback_query(ReportFlow.shift_photos, F.data == "add_shift_photos")
async def add_shift_photos_start(cq: CallbackQuery, state: FSMContext):
    """Начало добавления фото."""
    await cq.answer()
    await state.update_data(shift_photos=[])
    await cq.message.answer(
        "📷 Отправьте фото. Можно несколько. После отправки всех фото нажмите «Готово»:",
        reply_markup=None
    )

@router.message(ReportFlow.shift_photos, F.photo)
async def shift_photo_received(message: Message, state: FSMContext):
    """Получено фото для смены."""
    data = await state.get_data()
    photos = data.get("shift_photos", [])
    photos.append(message)
    await state.update_data(shift_photos=photos)
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Готово", callback_data="shift_photos_done")
    kb.button(text="📷 Добавить ещё", callback_data="add_shift_photos")
    kb.button(text="❌ Отмена", callback_data="cancel_report")
    kb.adjust(1, 1, 1)
    
    await message.answer(
        f"✅ Фото добавлено ({len(photos)} шт.)\n\n"
        "Отправьте ещё фото или нажмите «Готово»:",
        reply_markup=kb.as_markup()
    )

@router.callback_query(ReportFlow.shift_photos, F.data == "shift_photos_done")
async def shift_photos_done(cq: CallbackQuery, state: FSMContext):
    """Завершение добавления фото."""
    await cq.answer()
    await _save_report(cq.message, state)

@router.callback_query(F.data == "cancel_report")
async def cancel_report_flow(cq: CallbackQuery, state: FSMContext):
    """Отмена отчёта."""
    await cq.answer()
    await state.clear()
    await cq.message.answer("❌ Отчёт отменён")

@router.callback_query(F.data == "report:act:lpa")
async def report_go_to_lpa(cq: CallbackQuery, state: FSMContext):
    """Переход к ЛПА из отчета."""
    await cq.answer()
    await state.clear()
    from app.services.objects import fetch_all_objects
    from app.telegram.objects_ui import page_kb
    from app.telegram.flow_lpa import LPAFlow
    objs = await fetch_all_objects()
    await state.update_data(objects_cache=objs, page=0)
    await state.set_state(LPAFlow.select_object)
    await cq.message.answer(
        "📄 <b>Генерация ЛПА (Лист производственного анализа)</b>\n\n"
        "Выберите объект для которого нужно сформировать ЛПА:",
        reply_markup=page_kb(objs, 0, "lpaobj"),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "report:act:resources")
async def report_go_to_resources(cq: CallbackQuery, state: FSMContext):
    """Переход к ресурсам из отчета."""
    from app.telegram.flow_resources import start_resource_flow
    await start_resource_flow(cq, state)

@router.callback_query(F.data == "report:act:tab")
async def report_go_to_timesheet(cq: CallbackQuery, state: FSMContext):
    """Переход к табелю из отчета."""
    from app.telegram.flow_timesheet import start_timesheet_flow
    await start_timesheet_flow(cq, state)

async def _save_report(message: Message, state: FSMContext):
    """Сохранение отчёта в Bitrix24 и локальную БД."""
    import logging
    log = logging.getLogger("gpo.report")
    
    data = await state.get_data()
    
    plan = data.get("plan_json") or {}
    shift_id_raw = data.get("shift_id")
    fact = data.get("fact", {})
    eff_raw = data.get("eff_raw", 0)
    eff_final = data.get("eff_final", 0)
    downtime_reason = data.get("downtime_reason", "").strip()
    photos = data.get("shift_photos", [])

    plan_tasks, plan_meta = plan_tasks_from_json(plan, fallback_raw=plan)
    def _num(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    plan_total_value = 0.0
    if isinstance(plan, dict):
        plan_total_value = _num(plan.get("total_plan"))
    if plan_total_value <= 0 and plan_tasks:
        plan_total_value = sum(_num(task.get("plan")) for task in plan_tasks)
    photo_ids: List[str] = []
    for photo_msg in photos or []:
        try:
            if getattr(photo_msg, "photo", None):
                photo_ids.append(photo_msg.photo[-1].file_id)
        except Exception:
            continue

    fact_json_struct = build_fact_json_from_raw(
        fact,
        plan_tasks=plan_tasks,
        downtime_reason=downtime_reason,
        photos=photo_ids,
    )

    # Определяем, это bitrix_id или локальный ID
    try:
        shift_id = int(shift_id_raw)
    except (ValueError, TypeError):
        log.error(f"Invalid shift_id: {shift_id_raw}")
        await message.answer("❌ Ошибка: неверный ID смены.")
        await state.clear()
        return

    # Пробуем найти смену в локальной БД по ID
    # Если найдена - это локальный ID, получаем bitrix_id
    # Если не найдена - это bitrix_id
    bx_id = None
    local_shift_id = None
    
    try:
        with session_scope() as s:
            # Пробуем найти по локальному ID
            sh = s.get(Shift, shift_id)
            if sh:
                # Это локальный ID
                local_shift_id = shift_id
                bx_id = getattr(sh, "bitrix_id", None)
                log.info(f"Found local shift {local_shift_id}, bitrix_id={bx_id}")
            else:
                # Не найдена по локальному ID - пробуем найти по bitrix_id
                sh = s.query(Shift).filter(Shift.bitrix_id == shift_id).first()
                if sh:
                    # Это bitrix_id, нашли локальную смену
                    local_shift_id = sh.id
                    bx_id = shift_id
                    log.info(f"Found local shift {local_shift_id} for bitrix_id {shift_id}")
                else:
                    # Не найдена ни по локальному ID, ни по bitrix_id
                    # Скорее всего это bitrix_id, но локальной смены нет
                    bx_id = shift_id
                    log.info(f"No local shift found, assuming bitrix_id={bx_id}")
    except Exception as e:
        log.warning(f"Error checking shift in local DB: {e}, assuming bitrix_id={shift_id}")
        bx_id = shift_id  # В случае ошибки предполагаем, что это bitrix_id

    # Сохраняем в Bitrix24
    if bx_id:
        try:
            from app.bitrix_field_map import resolve_code, upper_to_camel
            from app.services.bitrix_files import upload_photos_to_bitrix_field
            import json
            
            # Подготавливаем поля для обновления (используем camelCase для Bitrix24 API)
            f_eff_raw = resolve_code("Смена", "UF_EFF_RAW")
            f_eff_final = resolve_code("Смена", "UF_EFF_FINAL")
            f_status = resolve_code("Смена", "UF_STATUS")
            f_fact_json = resolve_code("Смена", "UF_FACT_JSON")
            f_plan_json = resolve_code("Смена", "UF_PLAN_JSON")
            
            # ВАЖНО: Считаем fact_total из табеля (сумма UF_HOURS), а не из fact_json
            # Это единый источник правды для фактического объёма
            from app.services.lpa_data import _fetch_timesheet
            from app.services.bitrix_ids import TIMESHEET_ETID
            
            timesheets = await _fetch_timesheet(bx_id)
            fact_total_value = sum(
                float(t.get("ufCrm11UfHours") or t.get("UF_CRM_11_UF_HOURS") or 0)
                for t in timesheets
            )
            
            log.info(f"[REPORT] Calculated fact_total from timesheet: {fact_total_value} (items={len(timesheets)})")
            
            # Если табель пустой, используем fallback из fact_json (для обратной совместимости)
            if fact_total_value == 0:
                fact_total_value = fact_json_struct.get("total_fact", 0)
                if fact_total_value > 0:
                    log.info(f"[REPORT] Using fact_total from fact_json (fallback): {fact_total_value}")
            
            fields = {}
            if f_eff_raw:
                fields[upper_to_camel(f_eff_raw)] = eff_raw
            if f_eff_final:
                fields[upper_to_camel(f_eff_final)] = eff_final
            # Статус обновляется через bitrix_update_shift_aggregates
            
            log.info(f"Updating shift {bx_id} with fields: {list(fields.keys())}, fact_total={fact_total_value}")
            
            # Сохраняем детальный факт в JSON (если поле существует)
            if f_fact_json:
                f_fact_json_camel = upper_to_camel(f_fact_json)
                fields[f_fact_json_camel] = json.dumps(fact_json_struct, ensure_ascii=False)
                log.info(f"[LPA] UF_FACT_JSON updated")
            
            # Обновляем план JSON, если он изменился (например, если план был обновлен)
            if f_plan_json and plan:
                f_plan_json_camel = upper_to_camel(f_plan_json)
                if plan.get("tasks"):
                    plan_serializable = plan
                else:
                    plan_serializable = {
                        "tasks": plan_tasks,
                        "total_plan": sum(task["plan"] for task in plan_tasks),
                        "object_name": plan.get("object_name") or plan_meta.get("object_name"),
                        "date": plan.get("date") or plan_meta.get("date"),
                        "section": plan.get("section") or plan_meta.get("section"),
                        "foreman": plan.get("foreman") or plan_meta.get("foreman"),
                        "shift_type": plan.get("shift_type") or plan_meta.get("shift_type"),
                    }
                fields[f_plan_json_camel] = json.dumps(plan_serializable, ensure_ascii=False)
                log.info(f"[LPA] UF_PLAN_JSON updated")
            
            # Причина простоя
            if downtime_reason:
                f_downtime = resolve_code("Смена", "UF_DOWNTIME_REASON")
                fields[upper_to_camel(f_downtime)] = downtime_reason
            
            if fields:
                await bx_post("crm.item.update", {
                    "entityTypeId": SHIFT_ETID,
                    "id": bx_id,
                    "fields": fields
                })
                log.info(f"Updated shift {bx_id} in Bitrix24 (aux fields)")
            
            # Обновляем агрегаты смены (план/факт/эффективность/статус)
            try:
                await bitrix_update_shift_aggregates(
                    shift_id=bx_id,
                    plan_total=plan_total_value,
                    fact_total=fact_total_value,
                    efficiency=eff_final or eff_raw,
                    status="closed",
                )
            except Exception as agg_err:
                log.warning(f"[REPORT] Could not update shift aggregates: {agg_err}")

            # Загружаем фото, если есть
            if photos:
                await upload_photos_to_bitrix_field(
                    bot=message.bot,
                    entity_type_id=1050,  # ENTITY_SHIFT
                    item_id=bx_id,
                    field_logical_name="UF_SHIFT_PHOTOS",
                    entity_ru_name="Смена",
                    photo_messages=photos
                )
                log.info(f"Uploaded {len(photos)} photos to shift {bx_id}")
            
            # Генерируем ЛПА после сохранения отчета (единая функция)
            try:
                log.info(f"[LPA] Starting automatic LPA generation for shift {bx_id}")
                from app.services.lpa_generator import generate_lpa_for_shift
                from app.services.bitrix_files import upload_docx_to_bitrix_field
                from app.services.lpa_pdf import LPAPlaceholderError
                
                result = await generate_lpa_for_shift(
                    shift_bitrix_id=bx_id,
                    fallback_plan=plan,
                    fallback_fact=fact_json_struct,
                    meta=None,
                )

                pdf_path = result.pdf_path
                lpa_context = result.context
                log.info(f"[LPA] LPA generated successfully: {pdf_path}")
                
                # Загружаем файл в Bitrix (используем правильное поле UF_CRM_7_UF_CRM_PDF_FILE)
                if pdf_path:
                    uploaded = False
                    # Приоритет: UF_PDF_FILE (должно разрешиться в UF_CRM_7_UF_CRM_PDF_FILE)
                    for field_name in ["UF_PDF_FILE", "UF_LPA_FILE", "UF_FILE_PDF"]:
                        if await upload_docx_to_bitrix_field(
                            str(pdf_path),
                            entity_type_id=1050,
                            item_id=bx_id,
                            field_logical_name=field_name,
                            entity_ru_name="Смена",
                        ):
                            uploaded = True
                            log.info(f"[LPA] Uploaded LPA file to Bitrix24 field {field_name} for shift_id={bx_id}")
                            break
                    
                    if uploaded:
                        log.info(f"[LPA] LPA file uploaded successfully to shift_id={bx_id}")
                        # Обновляем агрегаты после успешной генерации ЛПА
                        try:
                            await bitrix_update_shift_aggregates(
                                shift_id=bx_id,
                                plan_total=plan_total_value,
                                fact_total=fact_total_value,
                                efficiency=eff_final or eff_raw,
                                status="closed",
                            )
                        except Exception as agg_err:
                            log.warning(f"[REPORT] Could not update shift aggregates after LPA: {agg_err}")
                    else:
                        log.warning(f"[LPA] Could not upload LPA file to Bitrix24 (field not found) for shift_id={bx_id}")
                    
            except LPAPlaceholderError:
                log.error("[LPA] Placeholder error during LPA generation", exc_info=True)
                await message.answer(
                    "❌ <b>Ошибка генерации ЛПА</b>\n\n"
                    "Не удалось сформировать ЛПА. В шаблоне остались пустые поля.\n"
                    "Передайте это сообщение разработчику.",
                    parse_mode="HTML",
                )
            except Exception as lpa_error:
                # Не падаем, если генерация ЛПА не удалась
                log.error(f"[LPA] Error generating LPA: {lpa_error}", exc_info=True)
            
        except Exception as e:
            log.error(f"Error updating shift in Bitrix24: {e}", exc_info=True)
            await message.answer(f"⚠️ Bitrix24: обновление не удалось: {e}\nПродолжаем сохранение в локальную БД...")

    # Сохраняем в локальную БД
    if local_shift_id:
        try:
            from app.models import ShiftStatus
            
            with session_scope() as s:
                sh = s.get(Shift, local_shift_id)
                if sh:
                    # Сохраняем факты
                    sh.fact_json = fact_json_struct
                    sh.eff_raw = eff_raw
                    sh.eff_final = eff_final
                    
                    # Закрываем смену
                    sh.status = ShiftStatus.CLOSED
                    
                    # Сохраняем причину простоя
                    if downtime_reason:
                        setattr(sh, "uf_downtime_reason", downtime_reason)
                    
                    s.add(sh)
                    s.commit()
                    log.info(f"Updated and closed local shift {local_shift_id}: fact={fact}, eff={eff_final}")
                else:
                    log.warning(f"Local shift {local_shift_id} not found")
        except Exception as e:
            log.error(f"Error updating local shift: {e}", exc_info=True)
            await message.answer(f"⚠️ Локальная БД: обновление не удалось: {e}")

    # Показываем результат с меню следующих шагов
    fact_total = fact_json_struct.get("total_fact", sum(fact.values()) if fact else 0)
    success_msg = f"✅ <b>Отчёт сохранён!</b>\n\n"
    success_msg += f"Фактический объём: {fact_total:.1f}\n"
    success_msg += f"Эффективность: {eff_final:.1f}%\n"
    if downtime_reason:
        success_msg += f"Причина простоя: {downtime_reason}\n"
    if photos:
        success_msg += f"Фото: {len(photos)} шт.\n"
    success_msg += f"\nСмена закрыта и готова для генерации ЛПА.\n\n"
    success_msg += "Что дальше?"
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="📄 Сформировать ЛПА", callback_data="report:act:lpa")
    if bx_id:
        kb.button(text="🔁 Перегенерировать ЛПА", callback_data=f"regen_lpa:{bx_id}")
    kb.button(text="🔄 Добавить ресурс", callback_data="report:act:resources")
    kb.button(text="👥 Добавить табель", callback_data="report:act:tab")
    kb.button(text="🏠 В главное меню", callback_data="back_to_menu")
    kb.adjust(1, 1, 1, 1)
    
    await state.clear()
    await message.answer(success_msg, reply_markup=kb.as_markup(), parse_mode="HTML")