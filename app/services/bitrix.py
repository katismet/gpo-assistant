import os, asyncio, logging, httpx
from app.config import get_settings

log = logging.getLogger("bx")
settings = get_settings()
BASE = str(settings.BITRIX_BASE) if settings.BITRIX_BASE else None
TOK = settings.BITRIX_TOKEN

log.debug("Bitrix config: BASE=%s, TOK=%s", BASE, TOK)

async def _try(http_call, url, **kw):
    for i in range(5):
        try:
            r = await http_call(url, **kw)
            r.raise_for_status()
            return r.json()
        except Exception:
            if i == 4:
                raise
            await asyncio.sleep(0.7 * (2**i))

async def bx_get(method: str, **params):
    if not BASE or not TOK:
        raise ValueError("BITRIX_BASE and BITRIX_TOKEN must be configured")
    async with httpx.AsyncClient(timeout=60) as x:
        log.debug("GET %s %s", method, params)
        url = f"{BASE.rstrip('/')}/rest/{TOK}/{method}.json"
        return await _try(x.get, url, params=params)

async def bx_post(method: str, payload: dict):
    if not BASE or not TOK:
        raise ValueError("BITRIX_BASE and BITRIX_TOKEN must be configured")
    async with httpx.AsyncClient(timeout=60) as x:
        log.debug("POST %s keys=%s", method, list(payload.keys()))
        url = f"{BASE.rstrip('/')}/rest/{TOK}/{method}.json"
        return await _try(x.post, url, json=payload)
