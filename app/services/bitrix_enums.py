"""Хелперы для работы с перечислениями Bitrix24 через числовые ID."""

from __future__ import annotations

from typing import Dict, Optional, Callable, Any
import logging

log = logging.getLogger("gpo.bitrix_enums")


class BitrixEnumHelper:
    """Helper для работы с enum-полями Bitrix24 через числовые ID."""
    
    def __init__(
        self,
        client: Callable,
        entity_type_id: int,
        uf_code: str,
        field_label: str | None = None,
    ):
        """
        Args:
            client: Функция для вызова Bitrix REST API (например, bx из http_client)
            entity_type_id: ID смарт-процесса (SHIFT_ETID, RESOURCE_ETID и т.п.)
            uf_code: Код поля в camelCase (например, 'ufCrm9UfResourceType')
            field_label: Опциональное описание поля для логирования
        """
        self.client = client
        self.entity_type_id = entity_type_id
        self.uf_code = uf_code
        self.field_label = field_label or uf_code
        self._label_to_id: Dict[str, int] = {}
        self._id_to_label: Dict[int, str] = {}
        self._loaded: bool = False

    async def load(self, force: bool = False) -> None:
        """Загружает список вариантов enum из Bitrix через существующие записи."""
        if self._loaded and not force:
            return
        
        try:
            # Для смарт-процессов Bitrix не предоставляет прямой API для получения enum значений
            # Используем статический маппинг и дополняем его через существующие записи
            
            # Начинаем со статического маппинга
            label_to_id: Dict[str, int] = {}
            id_to_label: Dict[int, str] = {}
            processed_count = 0
            items: list[Dict[str, Any]] = []
            
            # Загружаем статический маппинг для известных полей
            static_mapping = self._get_static_mapping()
            if static_mapping:
                label_to_id.update(static_mapping)
                id_to_label.update({v: k for k, v in static_mapping.items()})
            
            # Пытаемся дополнить через существующие записи
            # Получаем несколько записей и анализируем их enum значения
            try:
                # Для разных полей нужны разные дополнительные поля для определения label
                select_fields = ['id', self.uf_code]
                
                # Для ресурсов добавляем поля для определения типа
                if 'ufCrm9UfResourceType' in self.uf_code or 'UF_CRM_9_UF_RESOURCE_TYPE' in self.uf_code:
                    select_fields.extend(['ufCrm9UfMatType', 'ufCrm9UfEquipType'])
                
                # Для смен добавляем plan_json для определения типа смены
                if 'ufCrm7UfCrmShiftType' in self.uf_code or 'UF_CRM_7_UF_CRM_SHIFT_TYPE' in self.uf_code:
                    select_fields.append('ufCrm7UfPlanJson')
                # Для статуса добавляем PDF файл для определения закрытия
                if 'ufCrm7UfCrmStatus' in self.uf_code or 'UF_CRM_7_UF_CRM_STATUS' in self.uf_code:
                    select_fields.append('ufCrm7UfCrmPdfFile')
                
                # Для разных полей используем разные методы получения записей
                if 'ufCrm7UfCrmShiftType' in self.uf_code or 'UF_CRM_7_UF_CRM_SHIFT_TYPE' in self.uf_code:
                    # Для типа смены получаем конкретную смену 491 через crm.item.get
                    try:
                        shift_resp = await self.client('crm.item.get', {
                            'entityTypeId': self.entity_type_id,
                            'id': 491,
                            'select': select_fields,
                        })
                        items = [shift_resp.get('item', shift_resp)]
                    except Exception as e:
                        log.debug(f"[ENUM] Failed to get shift for shift_type: {e}")
                        items = []
                elif 'ufCrm7UfCrmStatus' in self.uf_code or 'UF_CRM_7_UF_CRM_STATUS' in self.uf_code:
                    # Для статуса получаем конкретную смену 491 через crm.item.get
                    try:
                        shift_resp = await self.client('crm.item.get', {
                            'entityTypeId': self.entity_type_id,
                            'id': 491,
                            'select': select_fields,
                        })
                        items = [shift_resp.get('item', shift_resp)]
                    except Exception as e:
                        log.debug(f"[ENUM] Failed to get shift for status: {e}")
                        items = []
                else:
                    # Для ресурсов и других полей используем crm.item.list
                    filter_params = {}
                    if 'ufCrm9UfResourceType' in self.uf_code or 'UF_CRM_9_UF_RESOURCE_TYPE' in self.uf_code:
                        # Для ресурсов берем записи со смены 491 (там есть и материалы, и техника)
                        filter_params = {'ufCrm9UfShiftId': 491}
                    
                    items_resp = await self.client('crm.item.list', {
                        'entityTypeId': self.entity_type_id,
                        'filter': filter_params if filter_params else {},
                        'select': select_fields,
                        'limit': 100,  # Берем достаточно записей для анализа
                    })
                    items = items_resp.get('items', [])
                    log.debug(f"[ENUM] Got {len(items)} items from crm.item.list for {self.field_label}")
                
                seen_ids = set()
                
                log.debug(f"[ENUM] Processing {len(items)} items for {self.field_label}")
                for item in items:
                    enum_value = item.get(self.uf_code)
                    if enum_value is None:
                        log.debug(f"[ENUM] Item {item.get('id')} has no enum value for {self.uf_code}")
                        continue
                    
                    # Если это числовой ID, запоминаем его
                    if isinstance(enum_value, int):
                        enum_id = enum_value
                        # Игнорируем ID=0 (обычно это дефолтное/пустое значение)
                        if enum_id > 0:
                            # Пытаемся определить label по контексту записи
                            label = await self._infer_label_from_item(item, enum_id)
                            log.debug(f"[ENUM] Item {item.get('id')}: enum_id={enum_id}, inferred_label={label}")
                            if label:
                                processed_count += 1
                                # Для ресурсов может быть несколько label для одного ID
                                # (если в Bitrix настроен только один вариант enum)
                                # В таком случае создаем маппинг для каждого label
                                label_to_id[label] = enum_id
                                # Для id_to_label используем первый найденный label
                                # (при чтении будем определять тип по контексту)
                                if enum_id not in id_to_label:
                                    id_to_label[enum_id] = label
                                # Для ресурсов не используем seen_ids, чтобы обрабатывать все записи
                                # и находить разные label для одного ID
                                if 'ufCrm9UfResourceType' not in self.uf_code:
                                    seen_ids.add(enum_id)
                                log.debug(f"[ENUM] Mapped {self.field_label}: ID {enum_id} -> '{label}'")
                    elif isinstance(enum_value, dict):
                        # Если это dict с value и id
                        enum_id = int(enum_value.get('ID') or enum_value.get('id') or 0)
                        label = str(enum_value.get('VALUE') or enum_value.get('value') or '').strip()
                        if enum_id > 0 and label:
                            label_to_id[label] = enum_id
                            id_to_label[enum_id] = label
                            seen_ids.add(enum_id)
                            
            except Exception as e:
                log.debug(f"[ENUM] Could not load enum values from existing items: {e}")
            
            self._label_to_id = label_to_id
            self._id_to_label = id_to_label
            self._loaded = True
            
            if label_to_id:
                log.info(
                    f"[ENUM] Loaded {len(label_to_id)} enum values for {self.field_label}: {list(label_to_id.keys())} (processed {processed_count} items)"
                )
            else:
                items_count = len(items) if items else 0
                log.warning(
                    f"[ENUM] No enum values loaded for {self.field_label} "
                    f"(processed {processed_count} items from {items_count} total)"
                )
            
        except Exception as e:
            log.error(
                f"[ENUM] Failed to load enum values for {self.field_label}: {e}",
                exc_info=True
            )
            self._label_to_id = {}
            self._id_to_label = {}
            self._loaded = True
    
    def _get_static_mapping(self) -> Dict[str, int] | None:
        """Возвращает статический маппинг label -> ID для известных полей."""
        try:
            from app.config.enum_mappings import ENUM_MAPPINGS
            entity_mapping = ENUM_MAPPINGS.get(self.entity_type_id, {})
            field_mapping = entity_mapping.get(self.uf_code, {})
            if field_mapping:
                # Инвертируем маппинг: {id: label} -> {label: id}
                return {label: enum_id for enum_id, label in field_mapping.items()}
        except ImportError:
            pass
        return None
    
    async def _infer_label_from_item(self, item: Dict[str, Any], enum_id: int) -> str | None:
        """Пытается определить label enum-значения по контексту записи."""
        # Для разных полей логика может быть разной
        
        if 'ufCrm9UfResourceType' in self.uf_code or 'UF_CRM_9_UF_RESOURCE_TYPE' in self.uf_code:
            # Для типа ресурса определяем по наличию material/equipment
            mat_type = item.get('ufCrm9UfMatType') or item.get('UF_CRM_9_UF_MAT_TYPE')
            equip_type = item.get('ufCrm9UfEquipType') or item.get('UF_CRM_9_UF_EQUIP_TYPE')
            
            if equip_type and not mat_type:
                return "Техника"
            elif mat_type:
                return "Материал"
        
        elif 'ufCrm7UfCrmShiftType' in self.uf_code or 'UF_CRM_7_UF_CRM_SHIFT_TYPE' in self.uf_code:
            # Для типа смены определяем из plan_json
            plan_json_raw = item.get('ufCrm7UfPlanJson') or item.get('UF_CRM_7_UF_PLAN_JSON')
            if plan_json_raw:
                try:
                    import json
                    if isinstance(plan_json_raw, str):
                        plan_json = json.loads(plan_json_raw)
                    elif isinstance(plan_json_raw, list):
                        # Если plan_json - это list, берем первый элемент
                        plan_json = plan_json_raw[0] if plan_json_raw else {}
                    else:
                        plan_json = plan_json_raw
                    
                    # Проверяем, что plan_json - это dict
                    if isinstance(plan_json, dict):
                        meta = plan_json.get('meta', {})
                        shift_type_code = meta.get('shift_type')
                        if shift_type_code:
                            from app.services.shift_meta import shift_type_bitrix_label
                            label = shift_type_bitrix_label(shift_type_code)
                            if label:
                                return label
                except Exception as e:
                    log.debug(f"[ENUM] Failed to parse plan_json for shift_type: {e}")
                    pass
            
            # Fallback: если enum_id=1 и нет plan_json, используем значение по умолчанию
            if enum_id == 1:
                # Обычно ID=1 соответствует "Дневная" смена
                return "Дневная"
        
        elif 'ufCrm7UfCrmStatus' in self.uf_code or 'UF_CRM_7_UF_CRM_STATUS' in self.uf_code:
            # Для статуса смены определяем по наличию ЛПА или других признаков закрытия
            # Если enum_id > 0 и смена закрыта, это обычно "Закрыта"
            if enum_id > 0:
                # Проверяем наличие PDF файла или других признаков закрытия
                pdf_file = item.get('ufCrm7UfCrmPdfFile') or item.get('UF_CRM_7_UF_CRM_PDF_FILE')
                if pdf_file:
                    return "Закрыта"
                # Если enum_id=1 и есть признаки закрытия, это обычно "Закрыта"
                if enum_id == 1:
                    return "Закрыта"
        
        return None

    async def get_id(self, label: str, auto_create: bool = False) -> Optional[int]:
        """
        Получает ID enum-значения по его label.
        
        Args:
            label: Человекочитаемое значение (например, "Материал", "Техника")
            auto_create: Если True, пытается создать новое значение, если не найдено (не рекомендуется для смарт-процессов)
            
        Returns:
            ID enum-значения или None если не найдено
        """
        await self.load()
        
        label_clean = str(label).strip()
        
        # Прямой поиск в загруженных значениях
        if label_clean in self._label_to_id:
            return self._label_to_id[label_clean]
        
        # Попытка найти с учетом регистра
        for stored_label, enum_id in self._label_to_id.items():
            if stored_label.lower() == label_clean.lower():
                return enum_id
        
        # Если не найдено и включено авто-создание (не рекомендуется)
        if auto_create:
            log.warning(f"[ENUM] Auto-create not supported for smart processes. Please configure enum values in Bitrix manually.")
            # new_id = await self._create_enum_value(label_clean)
            # if new_id is not None:
            #     self._label_to_id[label_clean] = new_id
            #     self._id_to_label[new_id] = label_clean
            #     return new_id
        
        log.warning(
            f"[ENUM] Enum value '{label_clean}' not found for {self.field_label}. "
            f"Available values: {list(self._label_to_id.keys())}"
        )
        return None

    async def get_label(self, enum_id: int) -> Optional[str]:
        """
        Получает label enum-значения по его ID.
        
        Args:
            enum_id: ID enum-значения
            
        Returns:
            Человекочитаемое значение или None если не найдено
        """
        await self.load()
        return self._id_to_label.get(int(enum_id))

    async def _create_enum_value(self, label: str) -> Optional[int]:
        """
        Создает новое enum-значение в Bitrix.
        
        Внимание: Эта функция изменяет настройки поля в Bitrix!
        Используйте только если уверены, что это необходимо.
        """
        try:
            # Получаем текущее описание поля
            resp = await self.client('crm.item.userfield.get', {
                'entityTypeId': self.entity_type_id,
                'fieldName': self.uf_code,
            })
            
            uf = resp.get('result') or resp
            if not uf:
                log.error(f"[ENUM] Cannot get field {self.field_label} for creating enum value")
                return None
            
            enum_list = list(uf.get('LIST') or [])
            
            # Находим максимальный ID
            max_id = 0
            for item in enum_list:
                try:
                    item_id = int(item.get('ID') or item.get('id') or 0)
                    if item_id > max_id:
                        max_id = item_id
                except (TypeError, ValueError):
                    pass
            
            # Создаем новое значение
            new_id = max_id + 1
            enum_list.append({
                'ID': new_id,
                'VALUE': label,
                'DEF': 'N',
                'SORT': len(enum_list) + 1,
            })
            
            # Обновляем поле
            await self.client('crm.item.userfield.update', {
                'entityTypeId': self.entity_type_id,
                'fieldName': self.uf_code,
                'fields': {
                    'LIST': enum_list,
                },
            })
            
            log.info(f"[ENUM] Created new enum value '{label}' with ID {new_id} for {self.field_label}")
            
            # Перезагружаем кэш
            self._loaded = False
            await self.load(force=True)
            
            return self._label_to_id.get(label)
            
        except Exception as e:
            log.error(
                f"[ENUM] Failed to create enum value '{label}' for {self.field_label}: {e}",
                exc_info=True
            )
            return None


# Глобальные экземпляры helpers (инициализируются при первом использовании)
_resource_type_enum: Optional[BitrixEnumHelper] = None
_shift_type_enum: Optional[BitrixEnumHelper] = None
_shift_status_enum: Optional[BitrixEnumHelper] = None


def get_resource_type_enum() -> BitrixEnumHelper:
    """Получить helper для UF_RESOURCE_TYPE."""
    global _resource_type_enum
    if _resource_type_enum is None:
        from app.services.http_client import bx
        from app.services.bitrix_ids import RESOURCE_ETID
        _resource_type_enum = BitrixEnumHelper(
            bx,
            RESOURCE_ETID,
            'ufCrm9UfResourceType',
            'UF_RESOURCE_TYPE (Ресурс)'
        )
    return _resource_type_enum


def get_shift_type_enum() -> BitrixEnumHelper:
    """Получить helper для UF_SHIFT_TYPE."""
    global _shift_type_enum
    if _shift_type_enum is None:
        from app.services.http_client import bx
        from app.services.bitrix_ids import SHIFT_ETID
        _shift_type_enum = BitrixEnumHelper(
            bx,
            SHIFT_ETID,
            'ufCrm7UfCrmShiftType',
            'UF_SHIFT_TYPE (Смена)'
        )
    return _shift_type_enum


def get_shift_status_enum() -> BitrixEnumHelper:
    """Получить helper для UF_STATUS."""
    global _shift_status_enum
    if _shift_status_enum is None:
        from app.services.http_client import bx
        from app.services.bitrix_ids import SHIFT_ETID
        _shift_status_enum = BitrixEnumHelper(
            bx,
            SHIFT_ETID,
            'ufCrm7UfCrmStatus',
            'UF_STATUS (Смена)'
        )
    return _shift_status_enum
