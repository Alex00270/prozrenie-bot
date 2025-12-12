import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting bot initialization...")

bot = Bot(token=TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

class Positioning(StatesGroup):
    waiting_brand_name = State()
    waiting_current_description = State()
    waiting_client_life = State()
    waiting_category = State()
    waiting_wish = State()

def get_start_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пройти диагностику и получить позиционирование", callback_data="start_diagnostic")]
    ])

def get_cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])

@router.message(F.text.in_({"/start", "старт", "привет"}))
async def cmd_start(message: Message):
    await message.answer(
        "<b>Прозрение</b>\n\n"
        "Я помогу тебе за 5 минут увидеть настоящее позиционирование твоего бренда.\n"
        "Никаких логотипов, пока — только смысл, роль и идея.\n\n"
        "Готов?",
        reply_markup=get_start_kb()
    )

# ... (остальной код handlers без изменений, как в предыдущем сообщении)

async def main():
    logger.info("Including router and starting polling...")
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
