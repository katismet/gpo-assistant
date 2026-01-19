"""Сервис для работы с фото из Bitrix24."""

import base64
import logging
from typing import List, Optional, Tuple
from pathlib import Path
from io import BytesIO
from PIL import Image

from app.services.http_client import bx
from app.bitrix_field_map import resolve_code, upper_to_camel

log = logging.getLogger("gpo.bitrix_photos")


def _get_field_value(item: dict, field_upper: str) -> any:
    """Получить значение поля из записи Bitrix, проверяя оба формата (UPPER_CASE и camelCase)."""
    value = item.get(field_upper)
    if value is None:
        value = item.get(upper_to_camel(field_upper))
    return value


async def get_shift_photos(shift_bitrix_id: int, max_photos: int = 5) -> List[Tuple[str, bytes]]:
    """Получить фото из смены Bitrix24.
    
    Args:
        shift_bitrix_id: ID смены в Bitrix24
        max_photos: Максимальное количество фото для вставки в документ
        
    Returns:
        Список кортежей (имя_файла, байты_изображения)
    """
    try:
        # Получаем смену из Bitrix24
        shift_data = await bx("crm.item.get", {
            "entityTypeId": 1050,  # ENTITY_SHIFT
            "id": shift_bitrix_id
        })
        
        item = shift_data.get("item", shift_data)
        if not item:
            log.warning(f"Shift {shift_bitrix_id} not found")
            return []
        
        # Получаем код поля для фото
        f_photos = resolve_code("Смена", "UF_SHIFT_PHOTOS")
        f_photos_camel = upper_to_camel(f_photos)
        
        # Читаем фото (может быть массивом или одним файлом)
        photos_raw = _get_field_value(item, f_photos_camel) or _get_field_value(item, f_photos)
        
        if not photos_raw:
            log.info(f"No photos found for shift {shift_bitrix_id}")
            return []
        
        # Нормализуем в список
        if not isinstance(photos_raw, list):
            photos_raw = [photos_raw]
        
        # Ограничиваем количество
        photos_raw = photos_raw[:max_photos]
        
        # Скачиваем фото
        photos = []
        import httpx
        
        for i, photo_data in enumerate(photos_raw):
            try:
                # Bitrix24 возвращает файлы в разных форматах
                # Может быть: {"id": 123, "downloadUrl": "..."} или просто ID или массив [{"id": 123}]
                file_id = None
                download_url = None
                
                if isinstance(photo_data, dict):
                    file_id = photo_data.get("id") or photo_data.get("ID")
                    download_url = photo_data.get("downloadUrl") or photo_data.get("DOWNLOAD_URL")
                elif isinstance(photo_data, (int, str)):
                    file_id = photo_data
                
                if not file_id:
                    continue
                
                # Пробуем получить downloadUrl через disk.file.get
                try:
                    file_data = await bx("disk.file.get", {"id": file_id})
                    if file_data:
                        download_url = file_data.get("downloadUrl") or file_data.get("DOWNLOAD_URL")
                        file_name = file_data.get("name") or file_data.get("NAME") or f"photo_{i+1}.jpg"
                    else:
                        file_name = f"photo_{i+1}.jpg"
                except Exception as e:
                    log.warning(f"Could not get file info for {file_id}: {e}")
                    file_name = f"photo_{i+1}.jpg"
                
                # Скачиваем файл через downloadUrl
                if download_url:
                    try:
                        async with httpx.AsyncClient(timeout=30) as client:
                            response = await client.get(download_url)
                            if response.status_code == 200:
                                file_bytes = response.content
                                photos.append((file_name, file_bytes))
                                continue
                    except Exception as e:
                        log.warning(f"Could not download from URL {download_url}: {e}")
                
                # Fallback: пробуем получить через disk.file.getcontent (base64)
                try:
                    file_content = await bx("disk.file.getcontent", {"id": file_id})
                    if file_content and "data" in file_content:
                        file_bytes = base64.b64decode(file_content["data"])
                        photos.append((file_name, file_bytes))
                        continue
                except Exception as e:
                    log.warning(f"Could not get file content for {file_id}: {e}")
                
                log.warning(f"Could not download photo {i+1} (file_id={file_id})")
                
            except Exception as e:
                log.error(f"Error downloading photo {i+1} from shift {shift_bitrix_id}: {e}")
                continue
        
        log.info(f"Downloaded {len(photos)} photos from shift {shift_bitrix_id}")
        return photos
        
    except Exception as e:
        log.error(f"Error getting shift photos: {e}", exc_info=True)
        return []


async def get_shift_downtime_reason(shift_bitrix_id: int) -> Optional[str]:
    """Получить причину простоя из смены Bitrix24.
    
    Args:
        shift_bitrix_id: ID смены в Bitrix24
        
    Returns:
        Причина простоя или None
    """
    try:
        shift_data = await bx("crm.item.get", {
            "entityTypeId": 1050,  # ENTITY_SHIFT
            "id": shift_bitrix_id
        })
        
        item = shift_data.get("item", shift_data)
        if not item:
            return None
        
        f_downtime = resolve_code("Смена", "UF_DOWNTIME_REASON")
        f_downtime_camel = upper_to_camel(f_downtime)
        
        reason = _get_field_value(item, f_downtime_camel) or _get_field_value(item, f_downtime)
        return reason if reason else None
        
    except Exception as e:
        log.error(f"Error getting downtime reason: {e}", exc_info=True)
        return None


def resize_image_for_document(image_bytes: bytes, max_width: int = 800, max_height: int = 600, quality: int = 85) -> bytes:
    """Уменьшить изображение для вставки в документ.
    
    Args:
        image_bytes: Байты исходного изображения
        max_width: Максимальная ширина в пикселях
        max_height: Максимальная высота в пикселях
        quality: Качество JPEG (1-100)
        
    Returns:
        Байты уменьшенного изображения
    """
    # Проверяем тип входных данных
    if not isinstance(image_bytes, bytes):
        if isinstance(image_bytes, str):
            log.error(f"resize_image_for_document received string instead of bytes: {image_bytes[:50]}...")
        else:
            log.error(f"resize_image_for_document received {type(image_bytes)} instead of bytes")
        # Возвращаем пустые байты или оригинал, если это не строка
        return b"" if isinstance(image_bytes, str) else image_bytes
    
    try:
        img = Image.open(BytesIO(image_bytes))
        
        # Конвертируем в RGB если нужно
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Уменьшаем если нужно
        if img.width > max_width or img.height > max_height:
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        
        # Сохраняем в JPEG
        output = BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        return output.getvalue()
        
    except Exception as e:
        log.error(f"Error resizing image: {e}")
        # Возвращаем оригинал если не удалось обработать
        return image_bytes

