"""Проверка маппинга полей"""

from app.bitrix_field_map import resolve_code, LOGICAL_TO_LABEL, _load_map

field_map = _load_map()
uf = field_map.get("Смена", {}).get("userfields", {})

print("Лейбл из LOGICAL_TO_LABEL:", repr(LOGICAL_TO_LABEL.get("UF_PLAN_TOTAL")))
print("\nЛейблы из Bitrix для PLAN:")
for k, v in uf.items():
    if "PLAN" in k:
        print(f"  {k}: {repr(v.get('label', ''))}")

print("\nСравнение:")
label = LOGICAL_TO_LABEL.get("UF_PLAN_TOTAL")
for k, v in uf.items():
    if "PLAN" in k:
        bitrix_label = v.get("label", "").strip()
        match = bitrix_label == label
        print(f"  {k}: {repr(bitrix_label)} == {repr(label)} = {match}")

print("\nПроверка resolve_code:")
print("UF_PLAN_TOTAL:", resolve_code("Смена", "UF_PLAN_TOTAL"))









