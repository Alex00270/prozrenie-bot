import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# --- 1. CONFIGURATION & LOGGING ---
# Настройка логирования для Render
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
TOKEN = os.getenv("TOKEN")

print("DEBUG 0. Init: Script started. Checking token...", flush=True)

if not TOKEN:
    print("CRITICAL: TOKEN is missing! Check Environment Variables.", flush=True)
    sys.exit(1)

# --- 2. STATES (FSM) ---
class BrandPositioning(StatesGroup):
    waiting_for_name = State()        # 1. Название бренда
    waiting_for_description = State() # 2. Текущее описание
    waiting_for_role = State()        # 3. Роль в жизни клиента
    waiting_for_category = State()    # 4. Категория
    waiting_for_association = State() # 5. Желаемая ассоциация

# --- 3. HANDLERS ---
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    print(f"DEBUG 1. Handler: /start received from {message.from_user.id}", flush=True)
    
    await state.clear()
    
    welcome_text = (
        "Привет! Я бот для распаковки позиционирования бренда.\n"
        "Мы пройдем 5 шагов, чтобы сформулировать суть твоего проекта.\n\n"
        "Готов начать?"
    )
    
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Начать распаковку")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(welcome_text, reply_markup=kb)

@router.message(F.text == "🚀 Начать распаковку")
async def start_survey(message: Message, state: FSMContext):
    print(f"DEBUG 2. Step 1: Asking for Brand Name", flush=True)
    await message.answer(
        "<b>Шаг 1/5.</b>\nНапиши название твоего бренда или проекта.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(BrandPositioning.waiting_for_name)

# Шаг 1 -> Шаг 2
@router.message(BrandPositioning.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    answer = message.text
    print(f"DEBUG 3. Received Name: {answer}", flush=True)
    
    await state.update_data(brand_name=answer)
    
    await message.answer(
        "<b>Шаг 2/5.</b>\nКак ты сейчас описываешь свой продукт в одном предложении? (Текущее описание)"
    )
    await state.set_state(BrandPositioning.waiting_for_description)

# Шаг 2 -> Шаг 3
@router.message(BrandPositioning.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    print(f"DEBUG 4. Received Description", flush=True)
    await state.update_data(description=message.text)
    
    await message.answer(
        "<b>Шаг 3/5.</b>\nКакую роль твой продукт играет в жизни клиента? (Например: спасатель, наставник, инструмент, друг)"
    )
    await state.set_state(BrandPositioning.waiting_for_role)

# Шаг 3 -> Шаг 4
@router.message(BrandPositioning.waiting_for_role)
async def process_role(message: Message, state: FSMContext):
    print(f"DEBUG 5. Received Role", flush=True)
    await state.update_data(role=message.text)
    
    await message.answer(
        "<b>Шаг 4/5.</b>\nВ какой рыночной категории ты работаешь? (Например: онлайн-образование, кофейня, консалтинг)"
    )
    await state.set_state(BrandPositioning.waiting_for_category)

# Шаг 4 -> Шаг 5
@router.message(BrandPositioning.waiting_for_category)
async def process_category(message: Message, state: FSMContext):
    print(f"DEBUG 6. Received Category", flush=True)
    await state.update_data(category=message.text)
    
    await message.answer(
        "<b>Шаг 5/5.</b>\nС каким словом или эмоцией ты хочешь ассоциироваться у клиента в первую очередь?"
    )
    await state.set_state(BrandPositioning.waiting_for_association)

# Финал
@router.message(BrandPositioning.waiting_for_association)
async def process_association(message: Message, state: FSMContext):
    print(f"DEBUG 7. Finishing survey", flush=True)
    await state.update_data(association=message.text)
    
    data = await state.get_data()
    
    summary = (
        "✅ <b>Распаковка завершена!</b>\n\n"
        f"1. <b>Бренд:</b> {data.get('brand_name')}\n"
        f"2. <b>Суть:</b> {data.get('description')}\n"
        f"3. <b>Роль:</b> {data.get('role')}\n"
        f"4. <b>Ниша:</b> {data.get('category')}\n"
        f"5. <b>Ассоциация:</b> {data.get('association')}\n\n"
        "<i>(Здесь в будущем подключим AI для генерации стратегии)</i>"
    )
    
    await message.answer(summary)
    await state.clear()

# --- 4. BOT SETUP & ENTRY POINT ---
async def main():
    print("DEBUG 8. Setup: Initializing Bot and Dispatcher...", flush=True)
    
    # Инициализация бота с новым синтаксисом (aiogram 3.7+)
    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    # Удаляем вебхуки, чтобы не было конфликтов при поллинге
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("DEBUG 9. Start: Polling started...", flush=True)
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"CRITICAL ERROR during polling: {e}", flush=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped manually", flush=True)
    except Exception as e:
        print(f"CRITICAL SYSTEM ERROR: {e}", flush=True)
