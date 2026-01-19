#!/usr/bin/env python3
"""Проверка объектов в локальной БД."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import session_scope
from app.models import Object


def list_objects():
    """Список всех объектов в локальной БД."""
    print("📋 Объекты в локальной БД:")
    print()
    
    try:
        with session_scope() as s:
            objects = s.query(Object).all()
            
            if not objects:
                print("❌ Объекты не найдены")
                return
            
            print(f"✅ Найдено объектов: {len(objects)}")
            print()
            print("Список объектов:")
            print("-" * 60)
            for obj in objects:
                print(f"ID: {obj.id:3d} | Name: {obj.name or 'N/A':30s} | Bitrix ID: {obj.bitrix_id or 'N/A'}")
            print("-" * 60)
            
            # Проверяем объект с ID 7
            obj7 = s.query(Object).filter(Object.id == 7).first()
            if obj7:
                print()
                print(f"✅ Объект с ID 7 найден:")
                print(f"   Name: {obj7.name}")
                print(f"   Bitrix ID: {obj7.bitrix_id}")
            else:
                print()
                print(f"❌ Объект с ID 7 не найден")
                
            # Проверяем объект с bitrix_id=51
            obj51 = s.query(Object).filter(Object.bitrix_id == 51).first()
            if obj51:
                print()
                print(f"✅ Объект с Bitrix ID 51 найден:")
                print(f"   ID: {obj51.id}")
                print(f"   Name: {obj51.name}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    list_objects()





