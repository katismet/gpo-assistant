"""Тест обработчиков W6"""

from app.handlers.w6_handlers import router
from app.telegram.bot import dp

print("Router name:", router.name)
print("Router handlers:", len(router.handlers))

# Проверяем все обработчики
for handler in router.handlers:
    if hasattr(handler, 'callback'):
        print(f"  Handler: {handler.callback.__name__}")
        if hasattr(handler, 'filters'):
            print(f"    Filters: {len(handler.filters)}")

print("\nRouters in dispatcher:")
for r in dp.sub_routers:
    name = getattr(r, 'name', 'unnamed')
    print(f"  - {name}")









