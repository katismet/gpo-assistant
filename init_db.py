"""Инициализация базы данных.

ВНИМАНИЕ: Демо-данные отключены для продакшена.
Для создания тестовых данных используйте отдельные скрипты.
"""
from app.db import Base, engine, SessionLocal
from app.models import Object
import os

Base.metadata.create_all(engine)

# Демо-данные создаются только если явно указано в переменной окружения
CREATE_DEMO_DATA = os.getenv("CREATE_DEMO_DATA", "false").lower() == "true"

if CREATE_DEMO_DATA:
    with SessionLocal() as s:
        if not s.query(Object).count():
            s.add_all([Object(id=1,name="ЖК «Север»"), Object(id=2,name="ДС «Восток»")])
            s.commit()
            print("Демо-данные созданы (CREATE_DEMO_DATA=true)")
else:
    print("Демо-данные пропущены (CREATE_DEMO_DATA=false или не установлено)")
