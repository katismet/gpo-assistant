#!/usr/bin/env python3
"""Проверка связи смены с объектом в локальной БД."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import session_scope
from app.models import Shift, Object


def check_shift_object(bitrix_shift_id: int):
    """Проверить связь смены с объектом в локальной БД."""
    print(f"📋 Проверка смены {bitrix_shift_id} в локальной БД...")
    print()
    
    try:
        with session_scope() as s:
            # Ищем смену по bitrix_id
            shift = s.query(Shift).filter(Shift.bitrix_id == bitrix_shift_id).first()
            
            if not shift:
                print(f"❌ Смена {bitrix_shift_id} не найдена в локальной БД")
                return
            
            print(f"✅ Смена найдена:")
            print(f"   ID: {shift.id}")
            print(f"   Bitrix ID: {shift.bitrix_id}")
            print(f"   Object ID: {shift.object_id}")
            print()
            
            if shift.object_id:
                obj = s.query(Object).filter(Object.id == shift.object_id).first()
                if obj:
                    print(f"✅ Объект найден:")
                    print(f"   ID: {obj.id}")
                    print(f"   Name: {obj.name}")
                    print(f"   Bitrix ID: {obj.bitrix_id}")
                else:
                    print(f"❌ Объект с ID {shift.object_id} не найден")
            else:
                print(f"⚠️  У смены нет привязки к объекту (object_id=None)")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python scripts/check_shift_local_db.py <BITRIX_SHIFT_ID>")
        print()
        print("Пример:")
        print("  python scripts/check_shift_local_db.py 297")
        sys.exit(1)
    
    try:
        bitrix_shift_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный ID смены: {sys.argv[1]}")
        sys.exit(1)
    
    check_shift_object(bitrix_shift_id)





