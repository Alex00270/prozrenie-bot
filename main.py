import asyncio
import logging
import os
import sys
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# ВАЖНО: Используем именно эту библиотеку для метода .configure()
import google.generativeai as genai

# --- 1. CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("DEBUG 0. Init: Script started.", flush=True)

if not TOKEN:
    print("CRITICAL: TOKEN is missing!", flush=True)
    sys.exit(1)

if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY is missing!", flush=True)
    sys.exit(1)
else:
    # Здесь используется старый добрый метод configure, который работает
    genai.configure(api_key=GEMINI_API_KEY)

# --- 2. DYNAMIC MODEL SELECTION (GEMMA PRIORITY) ---
CURRENT_MODEL_NAME = "models/gemini-1.5-flash" # Запасной вариант

def select_best_model():
    global CURRENT_MODEL_NAME
    print("🔎 Scanning available Google models...", flush=True)
    try:
        # Получаем список моделей
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 1. Ищем Gemma (открытые веса)
        gemma_candidates = [m for m in all_models if "gemma" in m.lower() and "it" in m.lower()]
        
        if gemma_candidates:
            # Сортируем по размеру (27b > 9b)
            def get_size(name):
                match = re.search(r'(\d+)b', name.lower())
                return int(match.group(1)) if match else 0
            
            gemma_candidates.sort(key=get_size, reverse=True)
            CURRENT_MODEL_NAME = gemma_candidates[0]
            print(f"   🏆 Found Gemma: {CURRENT_MODEL_NAME}", flush=True)
            
        else:
            # 2. Если Gemma нет, ищем Gemini Pro/Flash
            print("   ⚠️ Gemma not found. Looking for Gemini...", flush=True)
            gemini_models = [m for m in all_models if "gemini" in m.lower()]
            
            pro = next((m for m in gemini_models if "1.5-pro" in m), None)
            flash = next((m for m in gemini_models if "1.5-flash" in m), None)
            
            if pro:
                CURRENT_MODEL_NAME = pro
            elif flash:
                CURRENT_MODEL_NAME = flash
            elif gemini_models:
                CURRENT_MODEL_NAME = gemini_models[0]
                
            print(f"   ℹ️ Selected: {CURRENT_MODEL_NAME}", flush=True)

    except Exception as e:
        print(f"   ❌ Model Scan Failed: {e}", flush=True)

# Запускаем выбор модели сразу
select_best_model()

# --- 3. SYSTEM PROMPT ---
SYSTEM_PROMPT = """
You are a senior brand positioning strategist.
Your task is NOT to create marketing copy.
Your task is to identify strategic gaps, diagnose anti-positioning patterns, and propose hypotheses.

OUTPUT STRUCTURE (Russian language, Markdown):
1. **Диагноз** (Role clarity, Anti-positioning)
2. **Тест 10 секунд** (Can it be explained simply?)
3. **Гипотезы** (3 distinct strategic angles)
4. **Триггер** (Why they need a consultation)
"""

# --- 4. STATES (FSM) ---
class BrandAnalysis(StatesGroup):
    waiting_for_audience = State()
    waiting_for_problem = State()
    waiting_for_current_pos = State()
    waiting_for_competitors = State()
    waiting_for_rtb = State()
    waiting_for_explanation = State()

# --- 5. HANDLERS ---
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    model_short = CURRENT_MODEL_NAME.split('/')[-1]
    
    welcome_text = (
        f"👋 <b>AI-Стратег на связи.</b>\n"
        f"🧠 Мозг: {model_short}\n\n"
        "Я помогу найти слабые места в позиционировании.\n"
        "Нажми кнопку ниже."
    )
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Начать диагностику")]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await message.answer(welcome_text, reply_markup=kb)

@router.message(F.text == "🚀 Начать диагностику")
async def start_survey(message: Message, state: FSMContext):
    await message.answer("1. Кто твоя целевая аудитория? (Психотип, ситуация)", reply_markup=ReplyKeyboardRemove())
    await state.set_state(BrandAnalysis.waiting_for_audience)

@router.message(BrandAnalysis.waiting_for_audience)
async def step_2(message: Message, state: FSMContext):
    await state.update_data(audience=message.text)
    await message.answer("2. Какую главную проблему ты решаешь?")
    await state.set_state(BrandAnalysis.waiting_for_problem)

@router.message(BrandAnalysis.waiting_for_problem)
async def step_3(message: Message, state: FSMContext):
    await state.update_data(problem=message.text)
    await message.answer("3. Твоё текущее описание (био, оффер)?")
    await state.set_state(BrandAnalysis.waiting_for_current_pos)

@router.message(BrandAnalysis.waiting_for_current_pos)
async def step_4(message: Message, state: FSMContext):
    await state.update_data(current_positioning=message.text)
    await message.answer("4. Кто твои конкуренты? С кем сравнивают?")
    await state.set_state(BrandAnalysis.waiting_for_competitors)

@router.message(BrandAnalysis.waiting_for_competitors)
async def step_5(message: Message, state: FSMContext):
    await state.update_data(competitors=message.text)
    await message.answer("5. Reason to Believe: Почему тебе верят? (Факты)")
    await state.set_state(BrandAnalysis.waiting_for_rtb)

@router.message(BrandAnalysis.waiting_for_rtb)
async def step_6(message: Message, state: FSMContext):
    await state.update_data(reason_to_believe=message.text)
    await message.answer("6. Как клиент объясняет другу, чем ты занимаешься?")
    await state.set_state(BrandAnalysis.waiting_for_explanation)

@router.message(BrandAnalysis.waiting_for_explanation)
async def finish(message: Message, state: FSMContext):
    await state.update_data(explanation_test=message.text)
    data = await state.get_data()
    
    wait_msg = await message.answer(f"⏳ <b>Анализирую стратегию...</b>\nМодель: {CURRENT_MODEL_NAME}")
    
    # Формируем единый промпт (лучше всего для Gemma/Gemini)
    full_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "INPUT DATA:\n"
        f"Audience: {data.get('audience')}\n"
        f"Problem: {data.get('problem')}\n"
        f"Current Pos: {data.get('current_positioning')}\n"
        f"Competitors: {data.get('competitors')}\n"
        f"RTB: {data.get('reason_to_believe')}\n"
        f"Explanation: {data.get('explanation_test')}"
    )

    try:
        model = genai.GenerativeModel(CURRENT_MODEL_NAME)
        # Асинхронная генерация
        response = await model.generate_content_async(full_prompt)
        await message.answer(response.text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"AI Error: {e}")
        await message.answer("⚠️ Ошибка нейросети. Попробуй позже.")
    finally:
        await wait_msg.delete()
        await state.clear()

async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("DEBUG. Polling started...", flush=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
