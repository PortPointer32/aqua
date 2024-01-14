import asyncio
from aiogram import Bot, Dispatcher, executor
import sys
import nest_asyncio
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from handlers import register_handlers, periodic_crypto_update

async def run_bot(token):
    bot = Bot(token=token)
    dp = Dispatcher(bot, storage=MemoryStorage())

    asyncio.create_task(periodic_crypto_update())

    await register_handlers(dp, bot_token=token)

    executor.start_polling(dp, skip_updates=True)

if __name__ == "__main__":
    token = sys.argv[1]
    nest_asyncio.apply()
    asyncio.run(run_bot(token))
