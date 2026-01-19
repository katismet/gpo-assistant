# Makefile для ГПО-Помощник

.PHONY: help dev install test lint format clean docker-up docker-down migrate

# Цвета для вывода
GREEN=\033[0;32m
YELLOW=\033[1;33m
RED=\033[0;31m
NC=\033[0m # No Color

help: ## Показать справку
	@echo "$(GREEN)ГПО-Помощник - команды разработки$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

dev: ## Установка для разработки
	@echo "$(GREEN)Установка зависимостей для разработки...$(NC)"
	pip install -e .
	pip install -e ".[dev]"
	@echo "$(GREEN)Готово!$(NC)"

install: ## Установка зависимостей
	@echo "$(GREEN)Установка зависимостей...$(NC)"
	pip install -e .
	@echo "$(GREEN)Готово!$(NC)"

test: ## Запуск тестов
	@echo "$(GREEN)Запуск тестов...$(NC)"
	pytest -q
	@echo "$(GREEN)Тесты завершены!$(NC)"

test-verbose: ## Запуск тестов с подробным выводом
	@echo "$(GREEN)Запуск тестов с подробным выводом...$(NC)"
	pytest -v
	@echo "$(GREEN)Тесты завершены!$(NC)"

test-coverage: ## Запуск тестов с покрытием
	@echo "$(GREEN)Запуск тестов с покрытием...$(NC)"
	pytest --cov=app --cov-report=html --cov-report=term
	@echo "$(GREEN)Отчёт о покрытии сохранён в htmlcov/index.html$(NC)"

lint: ## Проверка кода
	@echo "$(GREEN)Проверка кода...$(NC)"
	ruff check .
	black --check .
	mypy app/
	@echo "$(GREEN)Проверка завершена!$(NC)"

format: ## Форматирование кода
	@echo "$(GREEN)Форматирование кода...$(NC)"
	black .
	ruff check . --fix
	@echo "$(GREEN)Форматирование завершено!$(NC)"

clean: ## Очистка временных файлов
	@echo "$(GREEN)Очистка временных файлов...$(NC)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	@echo "$(GREEN)Очистка завершена!$(NC)"

docker-up: ## Запуск Docker контейнеров
	@echo "$(GREEN)Запуск Docker контейнеров...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)Контейнеры запущены!$(NC)"

docker-down: ## Остановка Docker контейнеров
	@echo "$(GREEN)Остановка Docker контейнеров...$(NC)"
	docker-compose down
	@echo "$(GREEN)Контейнеры остановлены!$(NC)"

docker-logs: ## Просмотр логов Docker
	@echo "$(GREEN)Просмотр логов...$(NC)"
	docker-compose logs -f

docker-build: ## Сборка Docker образа
	@echo "$(GREEN)Сборка Docker образа...$(NC)"
	docker-compose build
	@echo "$(GREEN)Образ собран!$(NC)"

migrate: ## Применение миграций БД
	@echo "$(GREEN)Применение миграций...$(NC)"
	alembic upgrade head
	@echo "$(GREEN)Миграции применены!$(NC)"

migrate-create: ## Создание новой миграции
	@echo "$(GREEN)Создание новой миграции...$(NC)"
	@read -p "Введите описание миграции: " desc; \
	alembic revision --autogenerate -m "$$desc"
	@echo "$(GREEN)Миграция создана!$(NC)"

run: ## Запуск бота
	@echo "$(GREEN)Запуск бота...$(NC)"
	python -u -m app.telegram.bot

run-dev: ## Запуск бота в режиме разработки
	@echo "$(GREEN)Запуск бота в режиме разработки...$(NC)"
	DEBUG=true python -u -m app.telegram.bot

setup-env: ## Настройка окружения
	@echo "$(GREEN)Настройка окружения...$(NC)"
	cp env.example .env
	@echo "$(YELLOW)Отредактируйте файл .env$(NC)"
	@echo "$(GREEN)Окружение настроено!$(NC)"

check-env: ## Проверка переменных окружения
	@echo "$(GREEN)Проверка переменных окружения...$(NC)"
	@if [ ! -f .env ]; then \
		echo "$(RED)Файл .env не найден!$(NC)"; \
		echo "$(YELLOW)Выполните: make setup-env$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Файл .env найден!$(NC)"

init-db: ## Инициализация БД
	@echo "$(GREEN)Инициализация БД...$(NC)"
	alembic upgrade head
	@echo "$(GREEN)БД инициализирована!$(NC)"

reset-db: ## Сброс БД
	@echo "$(RED)ВНИМАНИЕ: Это удалит все данные!$(NC)"
	@read -p "Продолжить? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		alembic downgrade base; \
		alembic upgrade head; \
		echo "$(GREEN)БД сброшена!$(NC)"; \
	else \
		echo "$(YELLOW)Отменено$(NC)"; \
	fi

backup-db: ## Резервное копирование БД
	@echo "$(GREEN)Создание резервной копии БД...$(NC)"
	@if [ -f .env ]; then \
		source .env && pg_dump $$DATABASE_URL > backup_$$(date +%Y%m%d_%H%M%S).sql; \
		echo "$(GREEN)Резервная копия создана!$(NC)"; \
	else \
		echo "$(RED)Файл .env не найден!$(NC)"; \
	fi

docs: ## Генерация документации
	@echo "$(GREEN)Генерация документации...$(NC)"
	@echo "$(YELLOW)Документация доступна в README.md$(NC)"

security: ## Проверка безопасности
	@echo "$(GREEN)Проверка безопасности...$(NC)"
	safety check
	bandit -r app/
	@echo "$(GREEN)Проверка безопасности завершена!$(NC)"

performance: ## Проверка производительности
	@echo "$(GREEN)Проверка производительности...$(NC)"
	pytest --benchmark-only
	@echo "$(GREEN)Проверка производительности завершена!$(NC)"

ci: ## Запуск CI проверок
	@echo "$(GREEN)Запуск CI проверок...$(NC)"
	make lint
	make test
	make security
	@echo "$(GREEN)CI проверки завершены!$(NC)"

deploy: ## Деплой приложения
	@echo "$(GREEN)Деплой приложения...$(NC)"
	docker-compose build
	docker-compose up -d
	@echo "$(GREEN)Деплой завершён!$(NC)"

status: ## Статус приложения
	@echo "$(GREEN)Статус приложения:$(NC)"
	@echo "$(YELLOW)Docker контейнеры:$(NC)"
	docker-compose ps
	@echo "$(YELLOW)Логи приложения:$(NC)"
	docker-compose logs --tail=10 app

sync-bitrix: ## Синхронизация Bitrix24 → .env и bitrix_field_map.json
	@echo "$(GREEN)Синхронизация Bitrix24...$(NC)"
	python scripts/sync_bitrix_env.py
	@echo "$(GREEN)Синхронизация завершена!$(NC)"

# По умолчанию показываем справку
.DEFAULT_GOAL := help

