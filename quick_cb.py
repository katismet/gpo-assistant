import asyncio, logging, os, platform
from aiogram import Bot, Dispatcher, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level="DEBUG")
if platform.system()=="Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BOT_TOKEN = os.getenv("BOT_TOKEN")
assert BOT_TOKEN, "Нет BOT_TOKEN"
bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp  = Dispatcher()

def kb():
    b=InlineKeyboardBuilder()
    b.button(text="Тест", callback_data="act:test")
    return b.as_markup()

@dp.message()
async def any_msg(m: types.Message):
    await m.answer("Кликни:", reply_markup=kb())

@dp.callback_query(F.data.startswith("act:"))
async def on_cb(cq: types.CallbackQuery):
    await cq.answer()
    await cq.message.edit_text(f"OK {cq.data}", reply_markup=kb())

async def main(): 
    await dp.start_polling(bot, allowed_updates=["message","callback_query"])

asyncio.run(main())
