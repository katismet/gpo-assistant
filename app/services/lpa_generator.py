"""Единый генератор ЛПА для всех сценариев."""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

from app.services.lpa_data import collect_lpa_data
from app.services.lpa_pdf import render_lpa_docx, docx_to_pdf, LPAPlaceholderError
from app.services.shift_client import bitrix_update_shift_aggregates

log = logging.getLogger("gpo.lpa_generator")


@dataclass
class LPAGenerationResult:
    pdf_path: Path
    context: dict


async def generate_lpa_for_shift(
    shift_bitrix_id: int,
    *,
    fallback_plan: Optional[dict] = None,
    fallback_fact: Optional[dict] = None,
    meta: Optional[dict] = None,
) -> LPAGenerationResult:
    """
    Единая точка генерации ЛПА.
    
    1) collect_lpa_data
    2) render_lpa_docx
    3) docx_to_pdf (если есть)
    4) удаление временных файлов (tmpl_*, tmp_*, промежуточный docx)
    5) вернуть путь к финальному PDF (или docx, если PDF недоступен)
    
    Args:
        shift_bitrix_id: Bitrix ID смены
        fallback_plan: Fallback данные плана (опционально)
        fallback_fact: Fallback данные факта (опционально)
        meta: Дополнительные метаданные (опционально)
        
    Returns:
        Tuple[Path, dict]: (путь к финальному PDF файлу (или DOCX, если PDF недоступен), контекст ЛПА)
        или (None, None) при ошибке
    """
    log.info(f"[LPA GENERATOR] ===== START generate_lpa_for_shift =====")
    log.info(f"[LPA GENERATOR] shift_bitrix_id={shift_bitrix_id}")
    
    try:
        # 1. Собираем данные для ЛПА (единый контекст)
        log.info(f"[LPA GENERATOR] Collecting LPA data...")
        context, photos = await collect_lpa_data(
            shift_bitrix_id=shift_bitrix_id,
            fallback_plan=fallback_plan,
            fallback_fact=fallback_fact,
            meta=meta,
        )
        
        log.info(f"[LPA GENERATOR] Data collected successfully:")
        log.info(f"[LPA GENERATOR]   - object_name: {context.get('object_name')}")
        log.info(f"[LPA GENERATOR]   - plan_total: {context.get('plan_total')}")
        log.info(f"[LPA GENERATOR]   - fact_total: {context.get('fact_total')}")
        log.info(f"[LPA GENERATOR]   - tasks: {len(context.get('tasks', []))}")
        log.info(f"[LPA GENERATOR]   - photos: {len(photos)}")

        try:
            await bitrix_update_shift_aggregates(
                shift_id=shift_bitrix_id,
                plan_total=context.get("plan_total", 0.0),
                fact_total=context.get("fact_total", 0.0),
                efficiency=context.get("efficiency"),
                status="closed",  # Устанавливаем статус "Закрыта" после генерации ЛПА
            )
        except Exception as agg_err:
            log.warning(f"[LPA GENERATOR] Could not update shift aggregates: {agg_err}")
        
        # 2. Проверяем наличие шаблона
        template_path = Path("app/templates/pdf/lpa_template.docx")
        if not template_path.exists():
            log.error(f"[LPA GENERATOR] Template not found: {template_path}")
            raise FileNotFoundError(f"LPA template not found: {template_path}")
        
        # 3. Подготавливаем выходную директорию
        output_dir = Path("output/pdf")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 3.1. Удаляем старые ЛПА файлы для этой смены (чтобы не копить мусор)
        try:
            old_lpa_pattern = f"LPA_{shift_bitrix_id}_*.pdf"
            old_lpa_files = list(output_dir.glob(old_lpa_pattern))
            for old_file in old_lpa_files:
                try:
                    old_file.unlink()
                    log.info(f"[LPA GENERATOR] Deleted old LPA file: {old_file.name}")
                except Exception as e:
                    log.debug(f"[LPA GENERATOR] Could not delete old file {old_file.name}: {e}")
            if old_lpa_files:
                log.info(f"[LPA GENERATOR] Cleaned up {len(old_lpa_files)} old LPA file(s) for shift {shift_bitrix_id}")
        except Exception as cleanup_err:
            log.warning(f"[LPA GENERATOR] Could not cleanup old LPA files: {cleanup_err}")
        
        # 4. Формируем имя файла на основе контекста
        object_name = context.get("object_name", "Не указан")
        # Убеждаемся, что object_name не "Не указан" - это признак ошибки
        if object_name == "Не указан":
            log.warning(f"[LPA GENERATOR] object_name is 'Не указан', checking context...")
            # Пробуем получить из meta или других источников
            if meta and meta.get("object_name"):
                object_name = meta.get("object_name")
                log.info(f"[LPA GENERATOR] Using object_name from meta: {object_name}")
        
        # Санитизация имени объекта для файла
        object_name_safe = object_name.replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_").replace("?", "_").replace('"', "_").replace("<", "_").replace(">", "_").replace("|", "_")
        # Убираем лишние пробелы и ограничиваем длину
        object_name_safe = "_".join(object_name_safe.split())[:50]  # Максимум 50 символов
        
        # Получаем дату из контекста или используем текущую
        date_from_context = context.get("date", "")
        if date_from_context:
            # Парсим дату из формата "DD.MM.YYYY" или "YYYY-MM-DD"
            try:
                if "." in date_from_context:
                    date_obj = datetime.strptime(date_from_context, "%d.%m.%Y").date()
                else:
                    date_obj = datetime.strptime(date_from_context.split()[0], "%Y-%m-%d").date()
                date_str = date_obj.strftime("%Y%m%d")
            except:
                date_str = datetime.now().strftime("%Y%m%d")
        else:
            date_str = datetime.now().strftime("%Y%m%d")
        
        # Стабильный формат имени файла: LPA_{shift_id}_{date}_{sanitized_object_name}.pdf
        filename_prefix = f"LPA_{shift_bitrix_id}_{date_str}_{object_name_safe}"
        
        # Логируем для отладки
        log.info(f"[LPA GENERATOR] Filename prefix: {filename_prefix}, object_name: {object_name_safe}")
        
        log.info(f"[LPA GENERATOR] Rendering DOCX: prefix={filename_prefix}, object={object_name}")
        
        # 5. Рендерим DOCX
        try:
            docx_path = render_lpa_docx(
                template_path=template_path,
                data=context,  # Единый контекст
                out_dir=output_dir,
                filename_prefix=filename_prefix,
                photos=photos,
                max_photos_in_doc=5,
            )
        except LPAPlaceholderError as placeholder_err:
            log.error(
                f"[LPA GENERATOR] Placeholder error while rendering DOCX: {placeholder_err}"
            )
            raise
        
        if not docx_path.exists():
            log.error(f"[LPA GENERATOR] Generated DOCX file does not exist: {docx_path}")
            raise FileNotFoundError(f"Generated DOCX file does not exist: {docx_path}")
        
        log.info(f"[LPA GENERATOR] DOCX rendered successfully: {docx_path} (size={docx_path.stat().st_size} bytes)")
        
        # 6. Конвертируем в PDF (в executor, чтобы не блокировать event loop)
        log.info(f"[LPA GENERATOR] LPA: converting file {docx_path} to PDF (non-blocking)")
        import asyncio
        import time
        start_time = time.time()
        loop = asyncio.get_event_loop()
        pdf_path = await loop.run_in_executor(None, docx_to_pdf, docx_path, None, True)
        conversion_time = time.time() - start_time
        log.info(f"[LPA GENERATOR] PDF conversion completed in {conversion_time:.2f} seconds (non-blocking)")
        
        if not pdf_path or not pdf_path.exists():
            raise RuntimeError(f"PDF conversion failed for {docx_path}")
        
        log.info(f"[LPA GENERATOR] PDF generated successfully: {pdf_path} (size={pdf_path.stat().st_size} bytes)")
        
        # Удаляем промежуточный DOCX после успешной конвертации
        try:
            docx_path.unlink()
            log.debug(f"[LPA GENERATOR] Deleted intermediate DOCX: {docx_path}")
        except Exception as e:
            log.debug(f"[LPA GENERATOR] Could not delete DOCX: {e}")
        
        # 7. Очищаем временные файлы
        _cleanup_temp_files(output_dir)
        
        log.info(f"[LPA GENERATOR] ===== END generate_lpa_for_shift: SUCCESS =====")
        log.info(f"[LPA GENERATOR] Final file: {pdf_path}")
        
        return LPAGenerationResult(pdf_path=pdf_path, context=context)
        
    except LPAPlaceholderError as placeholder_err:
        log.error(f"[LPA GENERATOR] LPA generation failed: {placeholder_err}")
        raise
    except Exception as e:
        log.error(f"[LPA GENERATOR] Error generating LPA: {e}", exc_info=True)
        raise


def _cleanup_temp_files(output_dir: Path) -> None:
    """Удаляет временные файлы из output_dir."""
    try:
        import os
        cleaned = 0
        for pattern in ["tmpl_*.docx", "tmp_*.docx", "tmp_lpa_after_render_*.docx"]:
            for tmp_file in output_dir.glob(pattern):
                try:
                    tmp_file.unlink()
                    cleaned += 1
                    log.debug(f"[LPA GENERATOR] Deleted temporary file: {tmp_file}")
                except Exception:
                    pass
        if cleaned > 0:
            log.info(f"[LPA GENERATOR] Cleaned up {cleaned} temporary files")
    except Exception as cleanup_err:
        log.debug(f"[LPA GENERATOR] Could not cleanup temp files: {cleanup_err}")
