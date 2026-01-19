"""Тесты для утилит парсинга."""

import pytest
from decimal import Decimal
from datetime import datetime

from app.utils.parsing import (
    parse_json_safe,
    serialize_json_safe,
    parse_decimal,
    parse_datetime,
    extract_phone_number,
    extract_email,
    clean_text,
    parse_shift_type,
    parse_resource_kind,
    parse_tariff_type,
    validate_required_fields,
    normalize_boolean,
)


class TestParsingUtils:
    """Тесты для утилит парсинга."""

    def test_parse_json_safe_valid(self):
        """Тест парсинга валидного JSON."""
        data = '{"key": "value", "number": 123}'
        result = parse_json_safe(data)
        
        assert result == {"key": "value", "number": 123}

    def test_parse_json_safe_invalid(self):
        """Тест парсинга невалидного JSON."""
        data = '{"key": "value", "number": 123'  # Незакрытая скобка
        result = parse_json_safe(data)
        
        assert result is None

    def test_parse_json_safe_with_default(self):
        """Тест парсинга JSON с значением по умолчанию."""
        data = 'invalid json'
        result = parse_json_safe(data, default={})
        
        assert result == {}

    def test_serialize_json_safe(self):
        """Тест сериализации в JSON."""
        data = {"key": "value", "number": 123}
        result = serialize_json_safe(data)
        
        assert isinstance(result, str)
        assert "key" in result
        assert "value" in result

    def test_serialize_json_safe_invalid(self):
        """Тест сериализации невалидных данных."""
        # Функция с циклической ссылкой
        def circular_func():
            pass
        
        data = {"func": circular_func}
        result = serialize_json_safe(data)
        
        assert result == "{}"

    def test_parse_decimal_valid(self):
        """Тест парсинга валидного Decimal."""
        assert parse_decimal("123.45") == Decimal("123.45")
        assert parse_decimal("123,45") == Decimal("123.45")
        assert parse_decimal(123.45) == Decimal("123.45")
        assert parse_decimal(123) == Decimal("123")

    def test_parse_decimal_invalid(self):
        """Тест парсинга невалидного Decimal."""
        assert parse_decimal("invalid") == Decimal("0")
        assert parse_decimal(None) == Decimal("0")
        assert parse_decimal("") == Decimal("0")

    def test_parse_decimal_with_default(self):
        """Тест парсинга Decimal со значением по умолчанию."""
        assert parse_decimal("invalid", Decimal("10")) == Decimal("10")

    def test_parse_datetime_valid(self):
        """Тест парсинга валидного datetime."""
        # ISO формат
        result = parse_datetime("2024-01-15T10:30:00")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

        # Формат с датой и временем
        result = parse_datetime("2024-01-15 10:30:00")
        assert isinstance(result, datetime)

        # Только дата
        result = parse_datetime("2024-01-15")
        assert isinstance(result, datetime)

    def test_parse_datetime_invalid(self):
        """Тест парсинга невалидного datetime."""
        result = parse_datetime("invalid")
        assert result is None

    def test_parse_datetime_with_default(self):
        """Тест парсинга datetime со значением по умолчанию."""
        default = datetime(2024, 1, 1)
        result = parse_datetime("invalid", default=default)
        assert result == default

    def test_extract_phone_number(self):
        """Тест извлечения номера телефона."""
        assert extract_phone_number("+7 123 456 78 90") == "+71234567890"
        assert extract_phone_number("8 123 456 78 90") == "+71234567890"
        assert extract_phone_number("123-456-78-90") == "+71234567890"
        assert extract_phone_number("(123) 456-78-90") == "+71234567890"
        assert extract_phone_number("no phone here") is None

    def test_extract_email(self):
        """Тест извлечения email."""
        assert extract_email("test@example.com") == "test@example.com"
        assert extract_email("Contact: user@domain.ru") == "user@domain.ru"
        assert extract_email("no email here") is None

    def test_clean_text(self):
        """Тест очистки текста."""
        assert clean_text("  hello   world  ") == "hello world"
        assert clean_text("hello\n\nworld") == "hello world"
        assert clean_text("hello\t\tworld") == "hello world"

    def test_clean_text_with_max_length(self):
        """Тест очистки текста с ограничением длины."""
        long_text = "a" * 100
        result = clean_text(long_text, max_length=50)
        assert len(result) <= 53  # 50 + "..."

    def test_parse_shift_type(self):
        """Тест парсинга типа смены."""
        assert parse_shift_type("дневная") == "day"
        assert parse_shift_type("день") == "day"
        assert parse_shift_type("day") == "day"
        assert parse_shift_type("ночная") == "night"
        assert parse_shift_type("ночь") == "night"
        assert parse_shift_type("night") == "night"
        assert parse_shift_type("unknown") is None

    def test_parse_resource_kind(self):
        """Тест парсинга типа ресурса."""
        assert parse_resource_kind("техника") == "machinery"
        assert parse_resource_kind("машина") == "machinery"
        assert parse_resource_kind("экскаватор") == "machinery"
        assert parse_resource_kind("machinery") == "machinery"
        assert parse_resource_kind("материал") == "material"
        assert parse_resource_kind("цемент") == "material"
        assert parse_resource_kind("material") == "material"
        assert parse_resource_kind("unknown") is None

    def test_parse_tariff_type(self):
        """Тест парсинга типа тарифа."""
        assert parse_tariff_type("час") == "hour"
        assert parse_tariff_type("почасовая") == "hour"
        assert parse_tariff_type("hour") == "hour"
        assert parse_tariff_type("смена") == "shift"
        assert parse_tariff_type("shift") == "shift"
        assert parse_tariff_type("рейс") == "trip"
        assert parse_tariff_type("trip") == "trip"
        assert parse_tariff_type("unknown") is None

    def test_validate_required_fields(self):
        """Тест проверки обязательных полей."""
        data = {"field1": "value1", "field2": "value2", "field3": "value3"}
        required = ["field1", "field2"]
        
        missing = validate_required_fields(data, required)
        assert missing == []

    def test_validate_required_fields_missing(self):
        """Тест проверки обязательных полей с отсутствующими."""
        data = {"field1": "value1"}
        required = ["field1", "field2", "field3"]
        
        missing = validate_required_fields(data, required)
        assert "field2" in missing
        assert "field3" in missing
        assert "field1" not in missing

    def test_validate_required_fields_empty(self):
        """Тест проверки обязательных полей с пустыми значениями."""
        data = {"field1": "", "field2": None, "field3": "value3"}
        required = ["field1", "field2", "field3"]
        
        missing = validate_required_fields(data, required)
        assert "field1" in missing
        assert "field2" in missing
        assert "field3" not in missing

    def test_normalize_boolean(self):
        """Тест нормализации булевого значения."""
        assert normalize_boolean(True) is True
        assert normalize_boolean(False) is False
        assert normalize_boolean("true") is True
        assert normalize_boolean("1") is True
        assert normalize_boolean("yes") is True
        assert normalize_boolean("да") is True
        assert normalize_boolean("false") is False
        assert normalize_boolean("0") is False
        assert normalize_boolean("no") is False
        assert normalize_boolean("нет") is False
        assert normalize_boolean(1) is True
        assert normalize_boolean(0) is False
        assert normalize_boolean("unknown") is False
