def kv_pairs(s: str) -> dict[str, float]:
    """Парсинг строки в формате 'ключ=значение, ключ2=значение2'"""
    out = {}
    for raw in s.split(","):
        if not raw.strip():
            continue
        if "=" not in raw:
            raise ValueError(f"нет '=' в «{raw}»")
        k, v = raw.split("=", 1)
        k = k.strip().lower()
        v = v.strip().replace(",", ".")
        out[k] = float(v)
    return out