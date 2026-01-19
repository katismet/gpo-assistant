# Чек-лист "Почему ЛПА пустой"

## 1. Формат полей (camelCase)

❌ **Проблема:** Используется UPPER_CASE вместо camelCase
- `UF_CRM_7_UF_PLAN_JSON` → не работает
- `UF_CRM_7_UF_FACT_JSON` → не работает

✅ **Решение:** Использовать только camelCase
- `ufCrm7UfPlanJson` ✓
- `ufCrm7UfFactJson` ✓
- `ufCrm7UfCrmPlanTotal` ✓

**Проверка:**
```python
# Правильно
fields = {
    "ufCrm7UfPlanJson": json.dumps(plan_json, ensure_ascii=False),
    "ufCrm7UfCrmPlanTotal": float(total_plan),
}
```

---

## 2. Формат значения (строка JSON)

❌ **Проблема:** В `ufCrm7UfPlanJson` кладется dict, а не строка
```python
fields["ufCrm7UfPlanJson"] = plan_json  # НЕПРАВИЛЬНО
```

✅ **Решение:** Обязательно использовать `json.dumps()`
```python
fields["ufCrm7UfPlanJson"] = json.dumps(plan_json, ensure_ascii=False)  # ПРАВИЛЬНО
```

**Проверка:**
```bash
python scripts/check_shift.py <shift_id>
# Должно показать: plan_raw = ['{"tasks": [...], "total_plan": 220}']
```

---

## 3. План не записался в Bitrix24

❌ **Проблема:** `crm.item.get` показывает `ufCrm7UfPlanJson = []`

✅ **Решение:** 
1. Проверить, что функция `save_plan_to_bitrix()` вызывается после создания смены
2. Проверить логи: должно быть `[LPA] UF_PLAN_JSON updated`
3. Повторить сохранение плана

**Проверка:**
```bash
python scripts/check_shift.py <shift_id>
# Должно показать: plan_raw = ['{"tasks": [...], "total_plan": 220}']
```

---

## 4. Ресурсы и табель пустые

❌ **Проблема:** Таблицы "Техника", "Материалы", "Табель" пустые

✅ **Решение:** Использовать `select: ["id", "*", "ufCrm%"]` при запросе
```python
result = await bx("crm.item.list", {
    "entityTypeId": RESOURCE_ETID,
    "filter": {"=ufCrm9UfShiftId": shift_id},
    "select": ["id", "title", "*"],  # Важно: "*" включает все UF поля
})
```

**Проверка:**
- Убедиться, что ресурсы созданы в Bitrix24
- Проверить, что `ufCrm9UfShiftId` правильно заполнен
- Проверить, что `ufCrm9UfResourceType` = "TECH" или "MAT"

---

## 5. Фото не попадают в документ

❌ **Проблема:** Фото есть только как Telegram file_id в `fact_json.photos`

✅ **Решение:** 
1. При сохранении отчёта загружать фото в Bitrix24 через `upload_photos_to_bitrix_field()`
2. Фото должны сохраняться в поле `ufCrm7UfShiftPhotos` как файлы Bitrix24
3. Формат: `{"fileData": ["name.jpg", base64]}`

**Проверка:**
```bash
python scripts/check_shift.py <shift_id>
# Должно показать: photosUF = [{"id": 123, "downloadUrl": "..."}]
```

**Если фото только в fact_json.photos:**
- В генераторе ЛПА перед рендером скачивать их из Telegram
- Использовать `bot.get_file(file_id)` и `bot.download_file()`
- Подставлять в список `photos` для `lpa_pdf.py`

---

## Быстрая диагностика

```bash
# 1. Проверить данные смены
python scripts/check_shift.py <shift_id>

# 2. Проверить логи
Get-Content bot.log | Select-String -Pattern "\[LPA\]"

# 3. Экспортировать полные данные
python scripts/export_shift_data.py <shift_id>
```

---

## Ожидаемый результат

После исправления всех проблем:

**В Bitrix24:**
```json
{
  "ufCrm7UfPlanJson": ["{\"tasks\": [...], \"total_plan\": 220}"],
  "ufCrm7UfFactJson": ["{\"tasks\": [...], \"total_fact\": 203}"],
  "ufCrm7UfShiftPhotos": [{"id": 123, "downloadUrl": "..."}]
}
```

**В логах:**
```
[LPA] Bitrix shift get: 200
[LPA] plan_json: tasks=3, total_plan=220 ✓
[LPA] fact_json: tasks=3, total_fact=203 ✓
[LPA] Merged: tasks=3, plan_total=220.0, fact_total=203.0
```

**В документе ЛПА:**
- ✅ Производственные задания заполнены (план и факт)
- ✅ Техника заполнена
- ✅ Материалы заполнены
- ✅ Табель заполнен
- ✅ Фото вставлены в документ





