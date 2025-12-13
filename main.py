import asyncio
import logging
import os
import sys
import re  # Нужно для поиска цифр (27b, 9b)

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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
    genai.configure(api_key=GEMINI_API_KEY)

# --- 2. DYNAMIC MODEL SELECTION (GEMMA LOGIC) ---
CURRENT_MODEL_NAME = "models/gemini-1.5-flash" # Fallback на всякий случай

def select_best_model():
    global CURRENT_MODEL_NAME
    print("🔎 Scanning available Google models...", flush=True)
    try:
        # Получаем список
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Фильтруем: ищем gemma + it (instruction tuned)
        gemma_candidates = [m for m in all_models if "gemma" in m.lower() and "it" in m.lower()]
        
        if gemma_candidates:
            # Сортировка: вытаскиваем число перед 'b' (9b, 27b) и сортируем по убыванию
            # Пример имени: models/gemma-2-27b-it
            def get_size(name):
                match = re.search(r'(\d+)b', name.lower())
                return int(match.group(1)) if match else 0
            
            gemma_candidates.sort(key=get_size, reverse=True)
            
            CURRENT_MODEL_NAME = gemma_candidates[0]
            print(f"   🏆 Found Powerful Gemma: {CURRENT_MODEL_NAME} (Size matters!)", flush=True)
            print(f"   ℹ️ Full list sorted: {gemma_candidates}", flush=True)
        else:
            # Если Gemma не найдена, ищем Gemini
            print("   ⚠️ Gemma models not found. Looking for Gemini...", flush=True)
            gemini_models = [m for m in all_models if "gemini" in m.lower()]
            if gemini_models:
                # Пытаемся найти Pro, иначе Flash
                pro = next((m for m in gemini_models if "1.5-pro" in m), None)
                flash = next((m for m in gemini_models if "1.5-flash" in m), None)
                CURRENT_MODEL_NAME = pro or flash or gemini_models[0]
                print(f"   ⚠️ Fallback to Gemini: {CURRENT_MODEL_NAME}", flush=True)
            else:
                print("   ❌ No models found at all!", flush=True)

    except Exception as e:
        print(f"   ❌ Model Scan Failed: {e}", flush=True)

# Запускаем поиск
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
    print(f"DEBUG 1. Start: User {message.from_user.id}", flush=True)
    await state.clear()
    
    # Показываем юзеру, какой мозг сейчас подключен
    model_label = CURRENT_MODEL_NAME.split('/')[-1]
    
    welcome_text = (
        f"👋 <b>Привет! Я AI-стратег.</b>\n"
        f"⚙️ <i>Движок: {model_label}</i>\n\n"
        "Я найду ошибки в позиционировании и предложу гипотезы.\n"
        "Пройдем 6 шагов."
    )
    
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Начать")]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await message.answer(welcome_text, reply_markup=kb)

@router.message(F.text == "🚀 Начать")
async def start_survey(message: Message, state: FSMContext):
    await message.answer("<b>1. Аудитория:</b> Кто твой клиент? (Психотип/Ситуация)", reply_markup=ReplyKeyboardRemove())
    await state.set_state(BrandAnalysis.waiting_for_audience)

@router.message(BrandAnalysis.waiting_for_audience)
async def step_problem(message: Message, state: FSMContext):
    await state.update_data(audience=message.text)
    await message.answer("<b>2. Проблема:</b> Что у них болит перед покупкой?")
    await state.set_state(BrandAnalysis.waiting_for_problem)

@router.message(BrandAnalysis.waiting_for_problem)
async def step_current_pos(message: Message, state: FSMContext):
    await state.update_data(problem=message.text)
    await message.answer("<b>3. Описание:</b> Твой текущий оффер/шапка профиля.")
    await state.set_state(BrandAnalysis.waiting_for_current_pos)

@router.message(BrandAnalysis.waiting_for_current_pos)
async def step_competitors(message: Message, state: FSMContext):
    await state.update_data(current_positioning=message.text)
    await message.answer("<b>4. Конкуренты:</b> С кем тебя сравнивают?")
    await state.set_state(BrandAnalysis.waiting_for_competitors)

@router.message(BrandAnalysis.waiting_for_competitors)
async def step_rtb(message: Message, state: FSMContext):
    await state.update_data(competitors=message.text)
    await message.answer("<b>5. RTB:</b> Почему тебе можно верить? (Факты/Кейсы)")
    await state.set_state(BrandAnalysis.waiting_for_rtb)

@router.message(BrandAnalysis.waiting_for_rtb)
async def step_explanation(message: Message, state: FSMContext):
    await state.update_data(reason_to_believe=message.text)
    await message.answer("<b>6. Тест:</b> Как клиент объясняет другу, чем ты занимаешься?")
    await state.set_state(BrandAnalysis.waiting_for_explanation)

@router.message(BrandAnalysis.waiting_for_explanation)
async def finish_survey(message: Message, state: FSMContext):
    await state.update_data(explanation_test=message.text)
    
    user_data = await state.get_data()
    print(f"DEBUG. Generative Step using {CURRENT_MODEL_NAME}...", flush=True)
    
    processing_msg = await message.answer(f"⏳ <b>Анализирую ({CURRENT_MODEL_NAME.split('/')[-1]})...</b>")
    
    user_input_block = (
        f"Target Audience: {user_data.get('audience')}\n"
        f"Problem Solved: {user_data.get('problem')}\n"
        f"Current Description: {user_data.get('current_positioning')}\n"
        f"Competitors: {user_data.get('competitors')}\n"
        f"Reason to Believe: {user_data.get('reason_to_believe')}\n"
        f"Customer Explanation: {user_data.get('explanation_test')}\n"
    )

    try:
        # Gemma на Google API требует чуть другой конфиг, но этот базовый должен работать.
        # System instructions иногда не поддерживаются в явном виде для Gemma через этот SDK,
        # поэтому я дублирую промпт в тело сообщения для надежности.
        
        full_prompt = f"{SYSTEM_PROMPT}\n\nINPUT DATA:\n{user_input_block}"
        
        model = genai.GenerativeModel(CURRENT_MODEL_NAME)
        response = await model.generate_content_async(full_prompt)
        
        await message.answer(response.text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        print(f"CRITICAL AI ERROR: {e}", flush=True)
        await message.answer("⚠️ Ошибка нейросети. Попробуй позже.")
    
    finally:
        await processing_msg.delete()
        await state.clear()

# --- 6. MAIN ---
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
