@echo off
echo Активация виртуального окружения...
call "venv_clean\Scripts\activate.bat"
echo.
echo Проверка установленных пакетов...
python -c "import aiogram; print('aiogram version:', aiogram.__version__)"
echo.
echo Запуск бота...
python -m app.telegram.bot
pause
