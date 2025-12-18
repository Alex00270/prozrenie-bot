import os
import re
import google.generativeai as genai
from aiogram import Router, Bot, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from database import db

router = Router()

# --- 1. НАСТРОЙКА API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- 2. УМНЫЙ ВЫБОР МОДЕЛИ (Ваша новая логика) ---
def select_best_model():
    try:
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        def get_model_score(name):
            score = 0
            name = name.lower()
            if "gemma" in name:
                score += 1000
                size = re.search(r'(\d+)b', name)
                if size: score += int(size.group(1)) * 10
                ver = re.search(r'gemma-(\d)', name)
                if ver: score += int(ver.group(1)) * 50
            elif "gemini" in name:
                score += 500
                if "pro" in name: score += 100
            return score

        all_models.sort(key=get_model_score, reverse=True)
        if all_models: return all_models[0]
    except: pass
    return "models/gemini-1.5-pro"

CURRENT_MODEL_NAME = select_best_model()

# --- 3. МАШИНА СОСТОЯНИЙ (FSM) ДЛЯ ОПРОСА ---
class BrandAnalysis(StatesGroup):
    waiting_for_audience = State()
    waiting_for_problem = State()
    waiting_for_current_pos = State()
    waiting_for_competitors = State()
    waiting_for_rtb = State()
    waiting_for_explanation = State()

# --- 4. ПРИВЕТСТВИЕ И КНОПКА ---

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    bot_info = await bot.get_me()
    await db.add_user(user.id, user.username, user.full_name, bot_info.id)
    await state.clear() # Сбрасываем старые диалоги
    
    model_name = CURRENT_MODEL_NAME.replace("models/", "")
    
    text = (
        f"👋 Привет! Я <b>AI-Стратег</b> (Бот Прозрение).\n"
        f"🧠 Двигатель: <b>{model_name}</b>\n\n"
        f"Я помогу найти ошибки в позиционировании и предложу гипотезы.\n"
        f"Нажми кнопку, чтобы начать сессию."
    )
    
    # ТА САМАЯ КНОПКА
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Начать")]],
        resize_keyboard=True, 
        one_time_keyboard=True
    )
    
    await message.answer(text, reply_markup=kb)

# --- 5. ЛОГИКА ОПРОСА ---

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

# --- 6. ФИНАЛ И ГЕНЕРАЦИЯ ---

@router.message(BrandAnalysis.waiting_for_explanation)
async def finish_survey(message: Message, state: FSMContext):
    await state.update_data(explanation_test=message.text)
    user_data = await state.get_data()
    
    waiting_msg = await message.answer(f"⏳ <b>Анализирую стратегию...</b>\n(Модель: {CURRENT_MODEL_NAME.replace('models/','')})")
    
    # Формируем промпт из ответов
    input_data = (
        f"1. Audience: {user_data.get('audience')}\n"
        f"2. Problem: {user_data.get('problem')}\n"
        f"3. Current Offer: {user_data.get('current_positioning')}\n"
        f"4. Competitors: {user_data.get('competitors')}\n"
        f"5. Trust/RTB: {user_data.get('reason_to_believe')}\n"
        f"6. Client's words: {user_data.get('explanation_test')}\n"
    )

    SYSTEM_PROMPT = """
    You are a senior brand strategist. Identify strategic gaps and propose hypotheses.
    OUTPUT FORMAT (Russian, Markdown):
    1. **Диагноз** (Role clarity, Anti-positioning)
    2. **Тест 10 секунд** (Can it be explained simply?)
    3. **Гипотезы** (3 distinct strategic angles)
    4. **Триггер** (Why they need a consultation)
    """

    try:
        model = genai.GenerativeModel(CURRENT_MODEL_NAME)
        # Склеиваем промпт, чтобы Gemma точно поняла задачу
        full_prompt = f"{SYSTEM_PROMPT}\n\nINPUT DATA:\n{input_data}"
        
        response = model.generate_content(full_prompt)
        
        await waiting_msg.delete()
        await message.answer(response.text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        await waiting_msg.delete()
        await message.answer(f"⚠️ Ошибка стратега: {e}")
    
    await state.clear()

# Если юзер пишет что-то вне сценария
@router.message()
async def handle_any_message(message: Message):
    await message.answer("Нажми /start, чтобы начать стратегическую сессию.")
