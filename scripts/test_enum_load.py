"""Тест загрузки enum значений."""
import asyncio
from app.services.bitrix_enums import get_resource_type_enum

async def main():
    resource_enum = get_resource_type_enum()
    
    print("Загружаем enum значения...")
    await resource_enum.load(force=True)
    
    print(f"\nРезультат:")
    print(f"  label_to_id: {resource_enum._label_to_id}")
    print(f"  id_to_label: {resource_enum._id_to_label}")
    print(f"  _loaded: {resource_enum._loaded}")

if __name__ == "__main__":
    asyncio.run(main())



