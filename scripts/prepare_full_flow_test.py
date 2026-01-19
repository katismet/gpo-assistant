#!/usr/bin/env python
"""Подготовка bot.log для чистого запуска интеграционного теста.

Этот скрипт очищает bot.log, чтобы тест писал логи в чистый файл.
Запускать перед pytest tests/test_gpo_full_flow.py
"""

import os
from pathlib import Path

def main():
    """Очищает bot.log."""
    log_path = Path("bot.log")
    
    if log_path.exists():
        # Очищаем файл (truncate)
        log_path.open("w").close()
        print(f"✓ bot.log очищен (truncated)")
    else:
        # Создаём пустой файл
        log_path.touch()
        print(f"✓ bot.log создан (пустой)")
    
    print(f"✓ Готово к запуску теста: pytest -q tests/test_gpo_full_flow.py")

if __name__ == "__main__":
    main()
