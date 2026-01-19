def compute_eff_raw(plan: dict[str, float], fact: dict[str, float]) -> float:
    if not plan:
        return 0.0
    done = 0.0
    total = 0.0
    for k, v in plan.items():
        pv = float(v or 0)
        fv = float(fact.get(k, 0) or 0)
        total += pv
        done += min(fv, pv)
    return round(100.0 * done / total, 1) if total > 0 else 0.0

def blend_eff(raw: float, user_score: float | None) -> float:
    if user_score is None:
        return round(raw, 1)
    us = max(0.0, min(100.0, float(user_score)))
    return round(0.7 * raw + 0.3 * us, 1)