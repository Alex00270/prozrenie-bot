# main.py
import os
import logging
import asyncio
from typing import Any

# try to get TOKEN from config.py first (as you requested), otherwise from env
try:
    import config  # config.py должен содержать строку: TOKEN = os.getenv("TOKEN")
    TOKEN = config.TOKEN
except Exception:
    TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise RuntimeError("TOKEN is not set. Put TOKEN into config.py or set environment variable TOKEN.")

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Bot + Dispatcher
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# FSM states for 5-step survey
class Survey(StatesGroup):
    q1_brand_name = State()
    q2_current_description = State()
    q3_role_in_customer_life = State()
    q4_category = State()
    q5_desired_association = State()

# Keyboard to start survey
start_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Начать 5-шаговый опрос", callback_data="survey_begin")]
])

# /start handler
async def cmd_start(message: types.Message):
    await message.answer(
        "<b>Привет!</b>\nЯ — бот для 5-шаговой диагностики позиционирования бренда.\nНажми кнопку, чтобы начать.",
        reply_markup=start_kb
    )

# Callback to begin survey -> set first state
async def cb_begin(call: types.CallbackQuery):
    await call.answer()  # remove 'loading' on client
    await call.message.answer("Вопрос 1/5 — Название бренда:")
    await dp.storage.set_state(chat=call.message.chat.id, state=Survey.q1_brand_name)
    # or: await Survey.q1_brand_name.set()

# Handlers for each step
async def handle_q1(message: types.Message, state: FSMContext):
    await state.update_data(brand_name=message.text.strip())
    await message.answer("Вопрос 2/5 — Краткое текущее описание бренда:")
    await dp.storage.set_state(chat=message.chat.id, state=Survey.q2_current_description)

async def handle_q2(message: types.Message, state: FSMContext):
    await state.update_data(current_description=message.text.strip())
    await message.answer("Вопрос 3/5 — Какую роль бренд играет в жизни клиента?")
    await dp.storage.set_state(chat=message.chat.id, state=Survey.q3_role_in_customer_life)

async def handle_q3(message: types.Message, state: FSMContext):
    await state.update_data(role_in_life=message.text.strip())
    await message.answer("Вопрос 4/5 — Категория (например: FMCG, SaaS, Retail и т.д.):")
    await dp.storage.set_state(chat=message.chat.id, state=Survey.q4_category)

async def handle_q4(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text.strip())
    await message.answer("Вопрос 5/5 — Какая желаемая ассоциация/эмоция у клиента при упоминании бренда?")
    await dp.storage.set_state(chat=message.chat.id, state=Survey.q5_desired_association)

async def handle_q5(message: types.Message, state: FSMContext):
    await state.update_data(desired_association=message.text.strip())

    data = await state.get_data()
    # build result summary
    summary = (
        f"<b>Результаты 5-шагового опроса</b>\n\n"
        f"<b>1) Название бренда:</b> {data.get('brand_name', '—')}\n"
        f"<b>2) Текущее описание:</b> {data.get('current_description', '—')}\n"
        f"<b>3) Роль в жизни клиента:</b> {data.get('role_in_life', '—')}\n"
        f"<b>4) Категория:</b> {data.get('category', '—')}\n"
        f"<b>5) Желаемая ассоциация:</b> {data.get('desired_association', '—')}\n\n"
        f"Спасибо! Если нужно — могу предложить короткий позиционирующий слоган на основе этих ответов. "
        f"Напиши /start для повторного опроса."
    )

    await message.answer(summary)
    await state.clear()

# Catch-all text handler for when user sends text outside expected states
async def fallback_text(message: types.Message):
    await message.answer("Для запуска опроса отправь /start и нажми кнопку 'Начать 5-шаговый опрос'.")

# Error handler
async def on_error(update: types.Update, error: Exception):
    logger.exception("Произошла ошибка: %s", error)
    # Try to notify admin/chat if needed — be careful with token/IDs in prod.

# Register handlers
def register_handlers():
    dp.message.register(cmd_start, Command(commands=["start", "help"]))
    dp.callback_query.register(cb_begin, lambda c: c.data == "survey_begin")
    dp.message.register(handle_q1, state=Survey.q1_brand_name)
    dp.message.register(handle_q2, state=Survey.q2_current_description)
    dp.message.register(handle_q3, state=Survey.q3_role_in_customer_life)
    dp.message.register(handle_q4, state=Survey.q4_category)
    dp.message.register(handle_q5, state=Survey.q5_desired_association)
    dp.message.register(fallback_text)  # last - fallback

# Startup & shutdown events
async def on_startup():
    logger.info("Бот запускается...")

async def on_shutdown():
    logger.info("Шатдаун: закрываю соединение с ботом...")
    await bot.session.close()

async def main():
    register_handlers()
    try:
        await on_startup()
        # start polling
        await dp.start_polling(bot)
    finally:
        await on_shutdown()

if __name__ == "__main__":
    asyncio.run(main())
