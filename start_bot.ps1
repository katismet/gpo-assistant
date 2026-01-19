Write-Host "Активация виртуального окружения..." -ForegroundColor Green
& ".\venv_clean\Scripts\Activate.ps1"

Write-Host "Проверка установленных пакетов..." -ForegroundColor Yellow
python -c "import aiogram; print('aiogram version:', aiogram.__version__)"

Write-Host "Запуск бота..." -ForegroundColor Cyan
python -m app.telegram.bot
