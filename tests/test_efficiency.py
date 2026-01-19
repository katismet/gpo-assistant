"""Тесты для сервиса эффективности."""

import pytest
from decimal import Decimal

from app.services.efficiency import EfficiencyService


class TestEfficiencyService:
    """Тесты для сервиса эффективности."""

    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.service = EfficiencyService()

    def test_calculate_raw_efficiency_basic(self):
        """Тест базового расчёта эффективности Raw."""
        plan_data = {
            "hours": 8.0,
            "volume": 100.0,
            "resources": {
                "technique": [{"name": "Экскаватор", "qty": 1}],
                "materials": [{"name": "Цемент", "qty": 50}],
                "timesheet": [{"name": "Бригада 1", "hours": 8}],
            }
        }
        
        fact_data = {
            "hours": 8.0,
            "volume": 95.0,
            "resources": {
                "technique": [{"name": "Экскаватор", "qty": 1}],
                "materials": [{"name": "Цемент", "qty": 45}],
                "timesheet": [{"name": "Бригада 1", "hours": 8}],
            }
        }
        
        efficiency = self.service.calculate_raw_efficiency(plan_data, fact_data)
        
        assert isinstance(efficiency, Decimal)
        assert 0 <= float(efficiency) <= 100

    def test_calculate_raw_efficiency_perfect(self):
        """Тест расчёта эффективности при идеальном выполнении."""
        plan_data = {
            "hours": 8.0,
            "volume": 100.0,
            "resources": {
                "technique": [{"name": "Экскаватор", "qty": 1}],
                "materials": [{"name": "Цемент", "qty": 50}],
                "timesheet": [{"name": "Бригада 1", "hours": 8}],
            }
        }
        
        fact_data = {
            "hours": 8.0,
            "volume": 100.0,
            "resources": {
                "technique": [{"name": "Экскаватор", "qty": 1}],
                "materials": [{"name": "Цемент", "qty": 50}],
                "timesheet": [{"name": "Бригада 1", "hours": 8}],
            }
        }
        
        efficiency = self.service.calculate_raw_efficiency(plan_data, fact_data)
        
        # При идеальном выполнении эффективность должна быть близка к 100%
        assert float(efficiency) >= 90

    def test_calculate_raw_efficiency_poor(self):
        """Тест расчёта эффективности при плохом выполнении."""
        plan_data = {
            "hours": 8.0,
            "volume": 100.0,
            "resources": {
                "technique": [{"name": "Экскаватор", "qty": 1}],
                "materials": [{"name": "Цемент", "qty": 50}],
                "timesheet": [{"name": "Бригада 1", "hours": 8}],
            }
        }
        
        fact_data = {
            "hours": 12.0,  # Перерасход времени
            "volume": 50.0,  # Недовыполнение объёма
            "resources": {
                "technique": [{"name": "Экскаватор", "qty": 2}],  # Перерасход техники
                "materials": [{"name": "Цемент", "qty": 100}],  # Перерасход материалов
                "timesheet": [{"name": "Бригада 1", "hours": 12}],  # Перерасход времени
            }
        }
        
        efficiency = self.service.calculate_raw_efficiency(plan_data, fact_data)
        
        # При плохом выполнении эффективность должна быть низкой
        assert float(efficiency) < 70

    def test_calculate_user_efficiency(self):
        """Тест расчёта пользовательской эффективности."""
        base_efficiency = Decimal("80.0")
        
        user_input = {
            "time_adjustment": 5.0,
            "quality_adjustment": -3.0,
            "resource_adjustment": 2.0,
        }
        
        efficiency = self.service.calculate_user_efficiency(user_input, base_efficiency)
        
        assert isinstance(efficiency, Decimal)
        assert 0 <= float(efficiency) <= 100

    def test_calculate_final_efficiency(self):
        """Тест расчёта финальной эффективности."""
        raw_efficiency = Decimal("75.0")
        user_efficiency = Decimal("85.0")
        
        efficiency = self.service.calculate_final_efficiency(
            raw_efficiency, user_efficiency
        )
        
        assert isinstance(efficiency, Decimal)
        assert 0 <= float(efficiency) <= 100
        
        # Финальная эффективность должна быть между raw и user
        assert float(raw_efficiency) <= float(efficiency) <= float(user_efficiency)

    def test_calculate_final_efficiency_with_factors(self):
        """Тест расчёта финальной эффективности с дополнительными факторами."""
        raw_efficiency = Decimal("80.0")
        user_efficiency = Decimal("80.0")
        
        additional_factors = {
            "weather_factor": 0.9,  # Плохая погода
            "equipment_factor": 1.1,  # Хорошее оборудование
            "team_factor": 0.95,  # Неопытная команда
        }
        
        efficiency = self.service.calculate_final_efficiency(
            raw_efficiency, user_efficiency, additional_factors
        )
        
        assert isinstance(efficiency, Decimal)
        assert 0 <= float(efficiency) <= 100

    def test_get_efficiency_analysis(self):
        """Тест получения анализа эффективности."""
        raw_efficiency = Decimal("75.0")
        user_efficiency = Decimal("85.0")
        final_efficiency = Decimal("80.0")
        
        analysis = self.service.get_efficiency_analysis(
            raw_efficiency, user_efficiency, final_efficiency
        )
        
        assert isinstance(analysis, dict)
        assert "raw_efficiency" in analysis
        assert "user_efficiency" in analysis
        assert "final_efficiency" in analysis
        assert "grade" in analysis
        assert "recommendations" in analysis
        assert "trend" in analysis

    def test_get_efficiency_grade(self):
        """Тест получения оценки эффективности."""
        assert self.service._get_efficiency_grade(Decimal("95")) == "Отлично"
        assert self.service._get_efficiency_grade(Decimal("85")) == "Хорошо"
        assert self.service._get_efficiency_grade(Decimal("75")) == "Удовлетворительно"
        assert self.service._get_efficiency_grade(Decimal("65")) == "Неудовлетворительно"
        assert self.service._get_efficiency_grade(Decimal("45")) == "Плохо"

    def test_get_recommendations(self):
        """Тест получения рекомендаций."""
        recommendations = self.service._get_recommendations(Decimal("65"))
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

    def test_calculate_trend(self):
        """Тест расчёта тренда."""
        assert self.service._calculate_trend(Decimal("70"), Decimal("80")) == "Растёт"
        assert self.service._calculate_trend(Decimal("80"), Decimal("70")) == "Падает"
        assert self.service._calculate_trend(Decimal("75"), Decimal("76")) == "Стабильно"

    def test_extract_hours(self):
        """Тест извлечения часов из данных."""
        data = {"hours": 8.0}
        assert self.service._extract_hours(data) == 8.0
        
        data = {"work_hours": 10.0}
        assert self.service._extract_hours(data) == 10.0
        
        data = {"duration": 6.0}
        assert self.service._extract_hours(data) == 6.0
        
        data = {"time": "8:00-17:00"}
        assert self.service._extract_hours(data) == 9.0

    def test_extract_volume(self):
        """Тест извлечения объёма из данных."""
        data = {"volume": 100.0}
        assert self.service._extract_volume(data) == 100.0
        
        data = {"quantity": 50.0}
        assert self.service._extract_volume(data) == 50.0
        
        data = {"amount": 75.0}
        assert self.service._extract_volume(data) == 75.0

    def test_parse_time(self):
        """Тест парсинга времени."""
        assert self.service._parse_time("8:30") == 8.5
        assert self.service._parse_time("12:00") == 12.0
        assert self.service._parse_time("17:45") == 17.75
        assert self.service._parse_time("8") == 8.0

    def test_calculate_time_efficiency(self):
        """Тест расчёта эффективности по времени."""
        # Идеальное выполнение
        assert self.service._calculate_time_efficiency(8.0, 8.0) == 100.0
        
        # Перерасход времени
        assert self.service._calculate_time_efficiency(8.0, 10.0) < 100.0
        
        # Экономия времени
        assert self.service._calculate_time_efficiency(8.0, 6.0) > 100.0

    def test_calculate_volume_efficiency(self):
        """Тест расчёта эффективности по объёму."""
        # Идеальное выполнение
        assert self.service._calculate_volume_efficiency(100.0, 100.0) == 100.0
        
        # Недовыполнение
        assert self.service._calculate_volume_efficiency(100.0, 80.0) < 100.0
        
        # Перевыполнение
        assert self.service._calculate_volume_efficiency(100.0, 120.0) > 100.0
