# Интеграционный тест полного flow ГПО

## Описание

Полный автоматизированный тест контура ГПО: **План → Табель → Ресурс → ЛПА**.

Тест проверяет:
- Создание/получение смены через единую функцию `bitrix_get_shift_for_object_and_date`
- Сохранение плана в Bitrix24
- Добавление табеля (факт)
- Добавление ресурса
- Генерацию ЛПА через единую функцию `generate_lpa_for_shift`
- Единственность смены (отсутствие дублей)

## Последовательность запуска

### 1. Подготовка логов

Очищает `bot.log` для чистого запуска:

```bash
python scripts/prepare_full_flow_test.py
```

### 2. Запуск теста

```bash
pytest -q tests/test_gpo_full_flow.py
```

Или с подробным выводом:

```bash
pytest -v tests/test_gpo_full_flow.py
```

## Результаты в bot.log

После успешного прогона в `bot.log` будет блок от:

```
=== FULL_FLOW_TEST_START ===
```

до

```
=== FULL_FLOW_TEST_SUCCESS ===
```

### Ключевые логи в блоке теста:

- `[TEST] Используем объект: object_bitrix_id=...`
- `[TEST] Got shift_bitrix_id=... for object=... date=...`
- `[TEST] Plan saved: tasks=..., total_plan=...`
- `[TEST] Timesheet added: timesheet_id=..., hours=... (UF_HOURS)`
- `[TEST] Resource added: resource_id=..., type=..., material=...`
- `[TEST] Shift uniqueness check: found shift_id=..., expected=..., match=True`
- `[TEST] LPA Generation Summary:`
  - `shift_bitrix_id: ...`
  - `object_bitrix_id: ...`
  - `plan_total: ...`
  - `fact_total: ...`
  - `tasks_count: ...`
  - `timesheet_count: ...`
  - `pdf_path: ...`

### Итоговые значения в конце теста:

- `object_bitrix_id`: ID объекта из Bitrix24
- `shift_bitrix_id`: ID смены (должен быть один для пары объект+дата)
- `plan_total`: Плановый объём (ожидается 200.0)
- `fact_total`: Фактический объём из табеля (ожидается > 0, например 5.0)
- `tasks_count`: Количество задач в плане (ожидается 2)
- `timesheet_count`: Количество записей табеля (ожидается 1)

## Используемые функции

- `bitrix_get_shift_for_object_and_date()` - единая функция поиска/создания смены
- `save_plan_to_bitrix()` - сохранение плана в Bitrix24
- `bitrix_add_resource()` - добавление ресурса
- `generate_lpa_for_shift()` - единая функция генерации ЛПА

## Ожидаемый результат

- ✅ Тест проходит успешно (`PASSED`)
- ✅ В `bot.log` есть полный блок логов теста
- ✅ `plan_total = 200.0` (из плана)
- ✅ `fact_total > 0` (из табеля, например 5.0)
- ✅ Смена единственная (нет дублей)
- ✅ PDF файл ЛПА создан




