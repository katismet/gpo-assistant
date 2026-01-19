#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Быстрая проверка LPA данных по shift_id без Telegram."""

import asyncio
import json
import sys
from app.services.lpa_data import collect_lpa_data

async def main():
    if len(sys.argv) > 1:
        shift_id = int(sys.argv[1])
    else:
        shift_id = int(input("shift_id: "))
    
    print(f"\n[LPA] Загружаем данные для shift_id={shift_id}...\n")
    
    data, photos = await collect_lpa_data(
        shift_bitrix_id=shift_id,
        fallback_plan=None,
        fallback_fact=None,
        meta=None,
        efficiency=None,
        status=None
    )
    
    result = {
        "total_plan": data.get("total_plan", 0),
        "total_fact": data.get("total_fact", 0),
        "tasks_count": data.get("tasks_count", 0),
    }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # Проверка
    if result["total_plan"] > 0 and result["tasks_count"] >= 1:
        print("\n✅ OK: total_plan > 0, tasks_count >= 1")
    else:
        print(f"\n❌ FAIL: total_plan={result['total_plan']}, tasks_count={result['tasks_count']}")

if __name__ == "__main__":
    asyncio.run(main())





