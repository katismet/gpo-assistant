"""Конфигурация приложения."""

from functools import lru_cache
from typing import Optional

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения."""

    # Telegram Bot
    BOT_TOKEN: str = Field(..., description="Токен Telegram бота")

    # Bitrix24
    BITRIX_BASE: Optional[AnyUrl] = Field(None, description="Базовый URL Bitrix24")
    BITRIX_TOKEN: Optional[str] = Field(None, description="Токен Bitrix24")
    BITRIX_CLIENT_ID: Optional[str] = Field(None, description="Client ID для OAuth")
    BITRIX_CLIENT_SECRET: Optional[str] = Field(None, description="Client Secret для OAuth")
    BITRIX_REFRESH: Optional[str] = Field(None, description="Refresh токен для OAuth")
    BITRIX_DEFAULT_ASSIGNEE_ID: Optional[int] = Field(
        default=None,
        description="ID ответственного в Bitrix24 по умолчанию",
    )
    
    # W3 Resource Management
    BITRIX_WEBHOOK_URL: Optional[str] = Field(None, description="Webhook URL для Bitrix24 REST API")
    ENTITY_RESOURCE: Optional[int] = Field(None, description="entityTypeId SPA Ресурс")
    ENTITY_SHIFT: Optional[int] = Field(None, description="entityTypeId SPA Смена")
    
    # OpenAI for Insights
    OPENAI_API_KEY: Optional[str] = Field(None, description="API ключ OpenAI для генерации инсайтов")
    OPENAI_MODEL: Optional[str] = Field("gpt-4o-mini", description="Модель OpenAI для инсайтов")

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./gpo_assistant.db",
        description="URL базы данных",
    )

    # Timezone
    TZ: str = Field(default="Europe/Moscow", description="Часовой пояс")

    # PDF Generation
    PDF_BASE_URL: Optional[str] = Field(default=None, description="Базовый URL для PDF")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")

    # Application
    DEBUG: bool = Field(default=False, description="Режим отладки")
    HOST: str = Field(default="0.0.0.0", description="Хост приложения")
    PORT: int = Field(default=8000, description="Порт приложения")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"  # Разрешаем дополнительные поля из .env

    @property
    def is_production(self) -> bool:
        """Проверка на продакшн режим."""
        return not self.DEBUG

    @property
    def database_url_sync(self) -> str:
        """Синхронный URL базы данных для Alembic."""
        return self.DATABASE_URL.replace("+aiosqlite", "").replace("+psycopg", "+psycopg2")

    @property
    def bot_token(self) -> str:
        """Токен бота (совместимость)."""
        return self.BOT_TOKEN

    @property
    def bitrix_base(self) -> Optional[str]:
        """Базовый URL Bitrix24 (совместимость)."""
        return str(self.BITRIX_BASE) if self.BITRIX_BASE else None

    @property
    def bitrix_token(self) -> Optional[str]:
        """Токен Bitrix24 (совместимость)."""
        return self.BITRIX_TOKEN

    @property
    def bitrix_client_id(self) -> Optional[str]:
        """Client ID для OAuth (совместимость)."""
        return self.BITRIX_CLIENT_ID

    @property
    def bitrix_client_secret(self) -> Optional[str]:
        """Client Secret для OAuth (совместимость)."""
        return self.BITRIX_CLIENT_SECRET

    @property
    def bitrix_refresh(self) -> Optional[str]:
        """Refresh токен для OAuth (совместимость)."""
        return self.BITRIX_REFRESH

    @property
    def database_url(self) -> str:
        """URL базы данных (совместимость)."""
        return self.DATABASE_URL

    @property
    def tz(self) -> str:
        """Часовой пояс (совместимость)."""
        return self.TZ

    @property
    def pdf_base_url(self) -> str:
        """Базовый URL для PDF (совместимость)."""
        return self.PDF_BASE_URL or "http://localhost:8000"

    @property
    def log_level(self) -> str:
        """Уровень логирования (совместимость)."""
        return self.LOG_LEVEL

    @property
    def debug(self) -> bool:
        """Режим отладки (совместимость)."""
        return self.DEBUG

    @property
    def host(self) -> str:
        """Хост приложения (совместимость)."""
        return self.HOST

    @property
    def port(self) -> int:
        """Порт приложения (совместимость)."""
        return self.PORT


@lru_cache()
def get_settings() -> Settings:
    """Получить настройки приложения."""
    return Settings()


# Глобальный экземпляр настроек
settings = Settings()
