import asyncio, logging, os
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.DEBUG)
bot = Bot(os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

@dp.message(F.text == "/ping")
async def ping(m: types.Message): await m.answer("pong")

@dp.message(F.text == "/kb")
async def kb(m: types.Message):
    k = InlineKeyboardBuilder(); k.button(text="Тест", callback_data="cb:test")
    await m.answer("Кнопка:", reply_markup=k.as_markup())

@dp.callback_query(F.data == "cb:test")
async def cb(cq: types.CallbackQuery):
    await cq.answer("ok"); await cq.message.answer("callback ok")

async def main():
    await dp.start_polling(bot, allowed_updates=["message","callback_query"])
if __name__=="__main__": asyncio.run(main())
