from app.db import engine
from sqlalchemy import text
with engine.connect() as c:
    print("=== Проверка таблицы shifts ===")
    for row in c.execute(text("select id,object_id,date,type,status from shifts order by id desc limit 5")):
        print(row)