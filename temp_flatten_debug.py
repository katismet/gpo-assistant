import asyncio
from app.services.lpa_data import collect_lpa_data
from app.services.lpa_pdf import _flatten_for_template

async def main():
    ctx, photos = await collect_lpa_data(501)
    flat = _flatten_for_template(ctx)
    for key in ('object_name', 'section', 'plan_total', 'task1_name', 'worker1_name'):
        print(key, ':', flat.get(key))

asyncio.run(main())
