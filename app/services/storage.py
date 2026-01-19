"""Сервис работы с файлами и загрузками."""

import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import httpx
from loguru import logger

from app.config import get_settings
from app.services.bitrix import BitrixService

settings = get_settings()


class StorageService:
    """Сервис для работы с файлами и загрузками."""

    def __init__(self):
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Асинхронный контекстный менеджер."""
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие клиента."""
        if self._client:
            await self._client.aclose()

    async def download_telegram_file(
        self,
        file_path: str,
        bot_token: str,
    ) -> Tuple[str, bytes]:
        """Скачивание файла из Telegram."""
        try:
            if not self._client:
                raise RuntimeError("Client not initialized")

            # Формируем URL для скачивания
            url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
            
            logger.info(f"Downloading file from Telegram: {url}")
            
            # Скачиваем файл
            response = await self._client.get(url)
            response.raise_for_status()
            
            # Получаем имя файла
            filename = Path(file_path).name
            
            # Сохраняем во временный файл
            temp_file = self.temp_dir / filename
            temp_file.write_bytes(response.content)
            
            logger.info(f"File downloaded: {temp_file}")
            return str(temp_file), response.content
            
        except Exception as e:
            logger.error(f"Error downloading Telegram file: {e}")
            raise

    async def upload_to_bitrix(
        self,
        file_path: str,
        shift_bitrix_id: int,
        filename: Optional[str] = None,
    ) -> int:
        """Загрузка файла в Bitrix24."""
        try:
            if not filename:
                filename = Path(file_path).name
            
            async with BitrixService() as bitrix:
                file_id = await bitrix.attach_pdf(
                    shift_bitrix_id=shift_bitrix_id,
                    file_path=file_path,
                    file_name=filename,
                )
                
                logger.info(f"File uploaded to Bitrix24: {file_id}")
                return file_id
                
        except Exception as e:
            logger.error(f"Error uploading to Bitrix24: {e}")
            raise

    async def process_telegram_document(
        self,
        file_path: str,
        bot_token: str,
        shift_bitrix_id: int,
        filename: Optional[str] = None,
    ) -> int:
        """Обработка документа из Telegram."""
        try:
            # Скачиваем файл из Telegram
            local_path, content = await self.download_telegram_file(file_path, bot_token)
            
            # Загружаем в Bitrix24
            file_id = await self.upload_to_bitrix(
                file_path=local_path,
                shift_bitrix_id=shift_bitrix_id,
                filename=filename,
            )
            
            # Удаляем временный файл
            self.cleanup_file(local_path)
            
            return file_id
            
        except Exception as e:
            logger.error(f"Error processing Telegram document: {e}")
            raise

    async def process_telegram_photo(
        self,
        file_path: str,
        bot_token: str,
        shift_bitrix_id: int,
        filename: Optional[str] = None,
    ) -> int:
        """Обработка фото из Telegram."""
        try:
            # Скачиваем файл из Telegram
            local_path, content = await self.download_telegram_file(file_path, bot_token)
            
            # Если имя файла не указано, генерируем
            if not filename:
                filename = f"photo_{Path(file_path).name}"
            
            # Загружаем в Bitrix24
            file_id = await self.upload_to_bitrix(
                file_path=local_path,
                shift_bitrix_id=shift_bitrix_id,
                filename=filename,
            )
            
            # Удаляем временный файл
            self.cleanup_file(local_path)
            
            return file_id
            
        except Exception as e:
            logger.error(f"Error processing Telegram photo: {e}")
            raise

    def cleanup_file(self, file_path: str):
        """Удаление временного файла."""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.error(f"Error cleaning up file {file_path}: {e}")

    def cleanup_old_files(self, days: int = 1):
        """Очистка старых временных файлов."""
        try:
            import time
            
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            
            for file_path in self.temp_dir.glob("*"):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    logger.info(f"Cleaned up old file: {file_path}")
            
        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")

    def get_file_info(self, file_path: str) -> dict:
        """Получение информации о файле."""
        try:
            path = Path(file_path)
            if not path.exists():
                return {}
            
            stat = path.stat()
            return {
                "name": path.name,
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "extension": path.suffix,
            }
            
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return {}

    def validate_file_type(self, file_path: str, allowed_extensions: list) -> bool:
        """Проверка типа файла."""
        try:
            path = Path(file_path)
            extension = path.suffix.lower()
            return extension in allowed_extensions
        except Exception as e:
            logger.error(f"Error validating file type: {e}")
            return False

    def get_safe_filename(self, filename: str) -> str:
        """Получение безопасного имени файла."""
        try:
            # Удаляем опасные символы
            import re
            
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
            
            # Ограничиваем длину
            if len(safe_name) > 255:
                name, ext = safe_name.rsplit('.', 1) if '.' in safe_name else (safe_name, '')
                safe_name = name[:255-len(ext)-1] + ('.' + ext if ext else '')
            
            return safe_name
            
        except Exception as e:
            logger.error(f"Error getting safe filename: {e}")
            return "file"

    async def save_pdf_to_temp(self, pdf_content: bytes, filename: str) -> str:
        """Сохранение PDF во временный файл."""
        try:
            safe_filename = self.get_safe_filename(filename)
            temp_file = self.temp_dir / safe_filename
            
            temp_file.write_bytes(pdf_content)
            
            logger.info(f"PDF saved to temp file: {temp_file}")
            return str(temp_file)
            
        except Exception as e:
            logger.error(f"Error saving PDF to temp: {e}")
            raise

    def get_temp_file_path(self, filename: str) -> str:
        """Получение пути к временному файлу."""
        safe_filename = self.get_safe_filename(filename)
        return str(self.temp_dir / safe_filename)

    def is_temp_file(self, file_path: str) -> bool:
        """Проверка, является ли файл временным."""
        try:
            path = Path(file_path)
            return path.parent == self.temp_dir
        except Exception:
            return False


# Глобальный экземпляр сервиса
storage_service = StorageService()
