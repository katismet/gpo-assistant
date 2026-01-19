"""Middleware для Telegram бота."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, User
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User as DBUser, UserRole
from app.telegram.fsm_states import WorkflowState


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для работы с базой данных."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Обработка middleware."""
        async for session in get_session():
            data["session"] = session
            try:
                return await handler(event, data)
            except Exception as e:
                await session.rollback()
                logger.error(f"Database error in middleware: {e}")
                raise
            finally:
                await session.close()


class UserMiddleware(BaseMiddleware):
    """Middleware для работы с пользователями."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Обработка middleware."""
        session: AsyncSession = data["session"]
        
        # Получаем пользователя из события
        user: User = None
        if isinstance(event, Message):
            user = event.from_user
        elif hasattr(event, "from_user"):
            user = event.from_user
        
        if not user:
            return await handler(event, data)
        
        # Ищем пользователя в базе данных
        db_user = await session.get(DBUser, user.id)
        
        if not db_user:
            # Создаем нового пользователя
            db_user = DBUser(
                tg_id=user.id,
                role=UserRole.FOREMAN,  # По умолчанию прораб
            )
            session.add(db_user)
            await session.commit()
            logger.info(f"Created new user: {user.id}")
        
        data["db_user"] = db_user
        return await handler(event, data)


class ACLMiddleware(BaseMiddleware):
    """Middleware для контроля доступа."""

    def __init__(self, allowed_roles: list[UserRole] = None):
        self.allowed_roles = allowed_roles or [UserRole.FOREMAN, UserRole.OWNER]

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Обработка middleware."""
        db_user: DBUser = data.get("db_user")
        
        if not db_user:
            logger.warning("No user found in ACL middleware")
            return await handler(event, data)
        
        if db_user.role not in self.allowed_roles:
            logger.warning(f"Access denied for user {db_user.tg_id} with role {db_user.role}")
            # Можно отправить сообщение об отказе в доступе
            return await handler(event, data)
        
        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Обработка middleware."""
        db_user: DBUser = data.get("db_user")
        user_id = db_user.tg_id if db_user else "unknown"
        
        logger.info(f"Processing event from user {user_id}: {type(event).__name__}")
        
        try:
            result = await handler(event, data)
            logger.info(f"Event processed successfully for user {user_id}")
            return result
        except Exception as e:
            logger.error(f"Error processing event for user {user_id}: {e}")
            raise


class FSMStateMiddleware(BaseMiddleware):
    """Middleware для работы с FSM состояниями."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Обработка middleware."""
        # Получаем текущее состояние FSM
        from aiogram.fsm.context import FSMContext
        
        fsm_context: FSMContext = data.get("fsm_context")
        if fsm_context:
            current_state = await fsm_context.get_state()
            data["current_fsm_state"] = current_state
            logger.debug(f"Current FSM state: {current_state}")
        
        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов."""

    def __init__(self, max_requests: int = 10, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.user_requests: Dict[int, list] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Обработка middleware."""
        import time
        
        db_user: DBUser = data.get("db_user")
        if not db_user:
            return await handler(event, data)
        
        user_id = db_user.tg_id
        current_time = time.time()
        
        # Очищаем старые запросы
        if user_id in self.user_requests:
            self.user_requests[user_id] = [
                req_time for req_time in self.user_requests[user_id]
                if current_time - req_time < self.time_window
            ]
        else:
            self.user_requests[user_id] = []
        
        # Проверяем лимит
        if len(self.user_requests[user_id]) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            # Можно отправить сообщение об ограничении
            return await handler(event, data)
        
        # Добавляем текущий запрос
        self.user_requests[user_id].append(current_time)
        
        return await handler(event, data)

