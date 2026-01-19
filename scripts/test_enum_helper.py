"""Тест BitrixEnumHelper."""
import asyncio
from app.services.bitrix_enums import get_resource_type_enum, get_shift_type_enum, get_shift_status_enum

async def main():
    print("=== Тест BitrixEnumHelper ===\n")
    
    # Тест 1: Ресурс - тип ресурса
    print("1. Тест resource_type_enum:")
    try:
        resource_enum = get_resource_type_enum()
        await resource_enum.load()
        print(f"   Загружено значений: {len(resource_enum._label_to_id)}")
        print(f"   Label -> ID: {resource_enum._label_to_id}")
        print(f"   ID -> Label: {resource_enum._id_to_label}")
        
        # Тест получения ID
        mat_id = await resource_enum.get_id("Материал")
        equip_id = await resource_enum.get_id("Техника")
        print(f"   'Материал' -> ID: {mat_id}")
        print(f"   'Техника' -> ID: {equip_id}")
        
        # Тест получения label
        if mat_id:
            label = await resource_enum.get_label(mat_id)
            print(f"   ID {mat_id} -> Label: {label}")
    except Exception as e:
        print(f"   Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Тест 2: Смена - тип смены
    print("2. Тест shift_type_enum:")
    try:
        shift_type_enum = get_shift_type_enum()
        await shift_type_enum.load()
        print(f"   Загружено значений: {len(shift_type_enum._label_to_id)}")
        print(f"   Label -> ID: {shift_type_enum._label_to_id}")
        print(f"   ID -> Label: {shift_type_enum._id_to_label}")
        
        # Тест получения ID
        day_id = await shift_type_enum.get_id("Дневная")
        print(f"   'Дневная' -> ID: {day_id}")
    except Exception as e:
        print(f"   Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Тест 3: Смена - статус
    print("3. Тест shift_status_enum:")
    try:
        shift_status_enum = get_shift_status_enum()
        await shift_status_enum.load()
        print(f"   Загружено значений: {len(shift_status_enum._label_to_id)}")
        print(f"   Label -> ID: {shift_status_enum._label_to_id}")
        print(f"   ID -> Label: {shift_status_enum._id_to_label}")
        
        # Тест получения ID
        closed_id = await shift_status_enum.get_id("Закрыта")
        print(f"   'Закрыта' -> ID: {closed_id}")
    except Exception as e:
        print(f"   Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())



