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

# --- ВАЖНО: ПРАВИЛЬНЫЙ ИМПОРТ ДЛЯ ТВОЕГО REQUIREMENTS.TXT ---
import google.generativeai as genai

# --- 1. CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("DEBUG 0. Init: Script started.", flush=True)

# Проверка ключей
if not TOKEN:
    print("CRITICAL: TOKEN is missing!", flush=True)
    sys.exit(1)

if not GEMINI_API_KEY:
    print("CRITICAL: GEMINI_API_KEY is missing!", flush=True)
    sys.exit(1)
else:
    # Инициализация (работает только с google-generativeai)
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        print("DEBUG 0.1. Google AI configured successfully.", flush=True)
    except Exception as e:
        print(f"CRITICAL: Google AI Configure Failed: {e}", flush=True)
        sys.exit(1)

# --- 2. DYNAMIC MODEL SELECTION ---
CURRENT_MODEL_NAME = "models/gemini-1.5-flash"

def select_best_model():
    global CURRENT_MODEL_NAME
    print("🔎 Scanning available Google models...", flush=True)
    try:
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Ищем Gemma (она крутая и бесплатная в рамках лимитов)
        gemma_candidates = [m for m in all_models if "gemma" in m.lower() and "it" in m.lower()]
        
        if gemma_candidates:
            # Сортировка по размеру (27b > 9b)
            gemma_candidates.sort(key=lambda x: int(re.search(r'(\d+)b', x.lower()).group(1)) if re.search(r'(\d+)b', x.lower()) else 0, reverse=True)
            CURRENT_MODEL_NAME = gemma_candidates[0]
            print(f"   🏆 Found Gemma: {CURRENT_MODEL_NAME}", flush=True)
        else:
            # Если нет, берем Gemini
            print("   ⚠️ Gemma not found. Looking for Gemini...", flush=True)
            if any("1.5-pro" in m for m in all_models):
                CURRENT_MODEL_NAME = next(m for m in all_models if "1.5-pro" in m)
            elif any("1.5-flash" in m for m in all_models):
                CURRENT_MODEL_NAME = next(m for m in all_models if "1.5-flash" in m)
            print(f"   ℹ️ Selected: {CURRENT_MODEL_NAME}", flush=True)

    except Exception as e:
        print(f"   ❌ Model Scan Failed: {e}", flush=True)

select_best_model()

# --- 3. PROMPT ---
SYSTEM_PROMPT = """
You are a senior brand positioning strategist.
Output in Russian Markdown:
1. Diagnosis (Role clarity, Anti-patterns)
2. 10-second Test (Explainability)
3. 3 Hypotheses (Role, Category Reframing, Core Idea)
4. Trigger for consultation
"""

# --- 4. FSM ---
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
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚀 Начать")]], resize_keyboard=True, one_time_keyboard=True)
    await message.answer(f"👋 <b>AI-Стратег</b>\nМозг: {CURRENT_MODEL_NAME.split('/')[-1]}\nЖми кнопку!", reply_markup=kb)

@router.message(F.text == "🚀 Начать")
async def start_survey(message: Message, state: FSMContext):
    await message.answer("1. Кто твоя аудитория? (Психотип, ситуация)", reply_markup=ReplyKeyboardRemove())
    await state.set_state(BrandAnalysis.waiting_for_audience)

@router.message(BrandAnalysis.waiting_for_audience)
async def step_2(message: Message, state: FSMContext):
    await state.update_data(audience=message.text)
    await message.answer("2. Какую проблему решаешь?")
    await state.set_state(BrandAnalysis.waiting_for_problem)

@router.message(BrandAnalysis.waiting_for_problem)
async def step_3(message: Message, state: FSMContext):
    await state.update_data(problem=message.text)
    await message.answer("3. Текущее описание (био, оффер)?")
    await state.set_state(BrandAnalysis.waiting_for_current_pos)

@router.message(BrandAnalysis.waiting_for_current_pos)
async def step_4(message: Message, state: FSMContext):
    await state.update_data(current_positioning=message.text)
    await message.answer("4. Конкуренты?")
    await state.set_state(BrandAnalysis.waiting_for_competitors)

@router.message(BrandAnalysis.waiting_for_competitors)
async def step_5(message: Message, state: FSMContext):
    await state.update_data(competitors=message.text)
    await message.answer("5. Почему тебе верят (RTB)?")
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
    
    wait_msg = await message.answer("⏳ Анализирую...")
    
    full_prompt = (f"{SYSTEM_PROMPT}\n\nDATA:\n"
                   f"Audience: {data.get('audience')}\nProblem: {data.get('problem')}\n"
                   f"Current: {data.get('current_positioning')}\nCompetitors: {data.get('competitors')}\n"
                   f"RTB: {data.get('reason_to_believe')}\nExplanation: {data.get('explanation_test')}")

    try:
        model = genai.GenerativeModel(CURRENT_MODEL_NAME)
        response = await model.generate_content_async(full_prompt)
        await message.answer(response.text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await message.answer(f"Ошибка AI: {e}")
    finally:
        await wait_msg.delete()
        await state.clear()

async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
