import os
import asyncio
import httpx

BASE = os.getenv("BITRIX_BASE")
TOK = os.getenv("BITRIX_TOKEN_PATH")
ETID = 5  # смарт-процесс "Объект"

NAMES = [
    "ЖК «Юг-1»", "ЖК «Юг-2»", "ЖК «Олимп»", "ЖК «Платформа»", "ЖК «Горизонт»",
    "ЖК «Академический»", "Квартал 7", "Квартал 8", "КП «Речной»", "КП «Лесной»",
    "Цех №1", "Цех №2", "ЛОТ 5 Склад", "ТПУ «Центральный»", "ДС «Запад»",
    "ДС «Южный»", "ДС «Северный»", "ЖК «Атлант»", "ЖК «Север»", "ДС «Восток»"
]

async def main():
    async with httpx.AsyncClient(timeout=30) as x:
        for t in NAMES:
            r = await x.post(f"{BASE}/rest/{TOK}/crm.item.add.json",
                             json={"entityTypeId": ETID, "fields": {"title": t}})
            r.raise_for_status()
            print(t, "→ id", r.json()["result"]["item"]["id"])

if __name__ == "__main__":
    asyncio.run(main())