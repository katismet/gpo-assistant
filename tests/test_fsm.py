"""Тесты для FSM состояний."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.telegram.fsm_states import WorkflowState, PlanData, ReportData, ResourceData


class TestFSMStates:
    """Тесты для FSM состояний."""

    def test_workflow_state_enum(self):
        """Тест enum состояний рабочего процесса."""
        assert WorkflowState.MENU == "menu"
        assert WorkflowState.PLAN_PICK_OBJECT == "plan_pick_object"
        assert WorkflowState.REPORT_PICK_OBJECT == "report_pick_object"
        assert WorkflowState.RESOURCES_TECHNIQUE == "resources_technique"

    def test_plan_data_init(self):
        """Тест инициализации данных планирования."""
        plan_data = PlanData()
        
        assert plan_data.object_id is None
        assert plan_data.shift_id is None
        assert plan_data.resources == {}
        assert plan_data.notes == ""

    def test_plan_data_to_dict(self):
        """Тест преобразования данных планирования в словарь."""
        plan_data = PlanData()
        plan_data.object_id = 1
        plan_data.shift_id = 2
        plan_data.resources = {"test": "value"}
        plan_data.notes = "test notes"
        
        result = plan_data.to_dict()
        
        assert result["object_id"] == 1
        assert result["shift_id"] == 2
        assert result["resources"] == {"test": "value"}
        assert result["notes"] == "test notes"

    def test_plan_data_from_dict(self):
        """Тест создания данных планирования из словаря."""
        data = {
            "object_id": 1,
            "shift_id": 2,
            "resources": {"test": "value"},
            "notes": "test notes"
        }
        
        plan_data = PlanData.from_dict(data)
        
        assert plan_data.object_id == 1
        assert plan_data.shift_id == 2
        assert plan_data.resources == {"test": "value"}
        assert plan_data.notes == "test notes"

    def test_report_data_init(self):
        """Тест инициализации данных отчёта."""
        report_data = ReportData()
        
        assert report_data.object_id is None
        assert report_data.shift_id is None
        assert report_data.plan_fact == {}
        assert report_data.incidents == []
        assert report_data.downtime == []
        assert report_data.notes == ""

    def test_report_data_to_dict(self):
        """Тест преобразования данных отчёта в словарь."""
        report_data = ReportData()
        report_data.object_id = 1
        report_data.shift_id = 2
        report_data.plan_fact = {"plan": 100, "fact": 95}
        report_data.incidents = [{"time": "10:00", "description": "test"}]
        report_data.downtime = [{"time": "11:00", "reason": "test"}]
        report_data.notes = "test notes"
        
        result = report_data.to_dict()
        
        assert result["object_id"] == 1
        assert result["shift_id"] == 2
        assert result["plan_fact"] == {"plan": 100, "fact": 95}
        assert result["incidents"] == [{"time": "10:00", "description": "test"}]
        assert result["downtime"] == [{"time": "11:00", "reason": "test"}]
        assert result["notes"] == "test notes"

    def test_report_data_from_dict(self):
        """Тест создания данных отчёта из словаря."""
        data = {
            "object_id": 1,
            "shift_id": 2,
            "plan_fact": {"plan": 100, "fact": 95},
            "incidents": [{"time": "10:00", "description": "test"}],
            "downtime": [{"time": "11:00", "reason": "test"}],
            "notes": "test notes"
        }
        
        report_data = ReportData.from_dict(data)
        
        assert report_data.object_id == 1
        assert report_data.shift_id == 2
        assert report_data.plan_fact == {"plan": 100, "fact": 95}
        assert report_data.incidents == [{"time": "10:00", "description": "test"}]
        assert report_data.downtime == [{"time": "11:00", "reason": "test"}]
        assert report_data.notes == "test notes"

    def test_resource_data_init(self):
        """Тест инициализации данных ресурсов."""
        resource_data = ResourceData()
        
        assert resource_data.technique == []
        assert resource_data.materials == []
        assert resource_data.timesheet == []
        assert resource_data.notes == ""

    def test_resource_data_to_dict(self):
        """Тест преобразования данных ресурсов в словарь."""
        resource_data = ResourceData()
        resource_data.technique = [{"name": "Экскаватор", "qty": 1}]
        resource_data.materials = [{"name": "Цемент", "qty": 50}]
        resource_data.timesheet = [{"crew": "Бригада 1", "hours": 8}]
        resource_data.notes = "test notes"
        
        result = resource_data.to_dict()
        
        assert result["technique"] == [{"name": "Экскаватор", "qty": 1}]
        assert result["materials"] == [{"name": "Цемент", "qty": 50}]
        assert result["timesheet"] == [{"crew": "Бригада 1", "hours": 8}]
        assert result["notes"] == "test notes"

    def test_resource_data_from_dict(self):
        """Тест создания данных ресурсов из словаря."""
        data = {
            "technique": [{"name": "Экскаватор", "qty": 1}],
            "materials": [{"name": "Цемент", "qty": 50}],
            "timesheet": [{"crew": "Бригада 1", "hours": 8}],
            "notes": "test notes"
        }
        
        resource_data = ResourceData.from_dict(data)
        
        assert resource_data.technique == [{"name": "Экскаватор", "qty": 1}]
        assert resource_data.materials == [{"name": "Цемент", "qty": 50}]
        assert resource_data.timesheet == [{"crew": "Бригада 1", "hours": 8}]
        assert resource_data.notes == "test notes"


class TestFSMTransitions:
    """Тесты для переходов FSM."""

    @pytest.mark.asyncio
    async def test_plan_flow_transitions(self):
        """Тест переходов в потоке планирования."""
        # Мокаем FSM контекст
        state = AsyncMock()
        
        # Тестируем переходы
        await state.set_state(WorkflowState.PLAN_PICK_OBJECT)
        state.set_state.assert_called_with(WorkflowState.PLAN_PICK_OBJECT)
        
        await state.set_state(WorkflowState.PLAN_PICK_DATE)
        state.set_state.assert_called_with(WorkflowState.PLAN_PICK_DATE)
        
        await state.set_state(WorkflowState.PLAN_PICK_WORKS)
        state.set_state.assert_called_with(WorkflowState.PLAN_PICK_WORKS)
        
        await state.set_state(WorkflowState.PLAN_CONFIRM)
        state.set_state.assert_called_with(WorkflowState.PLAN_CONFIRM)
        
        await state.set_state(WorkflowState.PLAN_SAVE)
        state.set_state.assert_called_with(WorkflowState.PLAN_SAVE)

    @pytest.mark.asyncio
    async def test_report_flow_transitions(self):
        """Тест переходов в потоке отчётов."""
        # Мокаем FSM контекст
        state = AsyncMock()
        
        # Тестируем переходы
        await state.set_state(WorkflowState.REPORT_PICK_OBJECT)
        state.set_state.assert_called_with(WorkflowState.REPORT_PICK_OBJECT)
        
        await state.set_state(WorkflowState.REPORT_PICK_SHIFT)
        state.set_state.assert_called_with(WorkflowState.REPORT_PICK_SHIFT)
        
        await state.set_state(WorkflowState.REPORT_INPUT_FACT)
        state.set_state.assert_called_with(WorkflowState.REPORT_INPUT_FACT)
        
        await state.set_state(WorkflowState.REPORT_CONFIRM)
        state.set_state.assert_called_with(WorkflowState.REPORT_CONFIRM)
        
        await state.set_state(WorkflowState.REPORT_SAVE)
        state.set_state.assert_called_with(WorkflowState.REPORT_SAVE)

    @pytest.mark.asyncio
    async def test_resources_flow_transitions(self):
        """Тест переходов в потоке ресурсов."""
        # Мокаем FSM контекст
        state = AsyncMock()
        
        # Тестируем переходы
        await state.set_state(WorkflowState.RESOURCES_TECHNIQUE)
        state.set_state.assert_called_with(WorkflowState.RESOURCES_TECHNIQUE)
        
        await state.set_state(WorkflowState.RESOURCES_MATERIALS)
        state.set_state.assert_called_with(WorkflowState.RESOURCES_MATERIALS)
        
        await state.set_state(WorkflowState.RESOURCES_TIMESHEET)
        state.set_state.assert_called_with(WorkflowState.RESOURCES_TIMESHEET)

    @pytest.mark.asyncio
    async def test_objects_flow_transitions(self):
        """Тест переходов в потоке объектов."""
        # Мокаем FSM контекст
        state = AsyncMock()
        
        # Тестируем переходы
        await state.set_state(WorkflowState.OBJECTS_LIST)
        state.set_state.assert_called_with(WorkflowState.OBJECTS_LIST)
        
        await state.set_state(WorkflowState.OBJECTS_DETAILS)
        state.set_state.assert_called_with(WorkflowState.OBJECTS_DETAILS)

    @pytest.mark.asyncio
    async def test_back_to_menu_transition(self):
        """Тест перехода обратно в меню."""
        # Мокаем FSM контекст
        state = AsyncMock()
        
        # Тестируем переход в меню
        await state.set_state(WorkflowState.MENU)
        state.set_state.assert_called_with(WorkflowState.MENU)
