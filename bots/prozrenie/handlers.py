import os
import re
import logging
import httpx
import google.generativeai as genai
from aiogram import Router, Bot, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from database import db

router = Router()

# --- 1. НАСТРОЙКА РЕЗЕРВА (DIRECT GOOGLE) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- 2. ФУНКЦИЯ: ЕДИНАЯ ТОЧКА ГЕНЕРАЦИИ (ГИБРИД) ---
async def generate_smart_response(system_prompt, user_data_text):
    """
    Пытается получить ответ от Шлюза (Приоритет).
    Если не вышло — падает в Direct Google API (Резерв).
    Возвращает: (текст_ответа, имя_модели, источник)
    """
    
    # ----------------------------------------
    # ПОПЫТКА 1: GATEWAY (Сильные модели)
    # ----------------------------------------
    gateway_url = os.getenv("GATEWAY_BASE_URL")
    gateway_key = os.getenv("GATEWAY_API_KEY")
    
    # Если в Render задана конкретная модель, просим её. Если нет — auto.
    target_model = os.getenv("MODEL_NAME", "auto")

    if gateway_url and gateway_key:
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(
                    f"{gateway_url}/chat/completions",
                    headers={"Authorization": f"Bearer {gateway_key}"},
                    json={
                        "model": target_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_data_text}
                        ]
                    }
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    real_model = data.get("model", target_model)
                    return content, real_model, "📡 Gateway (Dallas)"
                else:
                    logging.warning(f"Gateway Error: {resp.status_code}. Switching to backup.")
        except Exception as e:
            logging.warning(f"Gateway failed: {e}. Switching to backup.")

    # ----------------------------------------
    # ПОПЫТКА 2: DIRECT GOOGLE (Резерв)
    # ----------------------------------------
    try:
        # Умный выбор модели из доступных по ключу
        def select_backup_model():
            try:
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                # Простая эвристика: ищем gemini-1.5 или pro
                priority = [m for m in models if 'gemini-1.5-pro' in m]
                if priority: return priority[0]
                return models[0] if models else "models/gemini-pro"
            except:
                return "models/gemini-1.5-flash"

        backup_model_name = select_backup_model()
        model = genai.GenerativeModel(backup_model_name)
        
        # Склеиваем промпт вручную, так как либа Google простая
        full_prompt = f"{system_prompt}\n\nINPUT DATA:\n{user_data_text}"
        response = model.generate_content(full_prompt)
        
        clean_name = backup_model_name.replace("models/", "")
        return response.text, clean_name, "🔌 Direct API (Backup)"

    except Exception as e:
        return f"❌ Полный отказ систем. Ошибка: {e}", "None", "Dead"


# --- 3. МАШИНА СОСТОЯНИЙ ---
class BrandAnalysis(StatesGroup):
    waiting_for_audience = State()
    waiting_for_problem = State()
    waiting_for_current_pos = State()
    waiting_for_competitors = State()
    waiting_for_rtb = State()
    waiting_for_explanation = State()

# --- 4. ПРИВЕТСТВИЕ ---

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    bot_info = await bot.get_me()
    await db.add_user(user.id, user.username, user.full_name, bot_info.id)
    await state.clear()
    
    # Показываем, что система гибридная
    target = os.getenv("MODEL_NAME", "auto")
    
    text = (
        f"👋 Привет! Я <b>AI-Стратег</b>.\n"
        f"🎯 Цель: <b>{target}</b> (через Шлюз)\n"
        f"🛡️ Резерв: <b>Google Direct</b>\n\n"
        f"Нажми кнопку, чтобы начать анализ."
    )
    
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Начать")]],
        resize_keyboard=True, 
        one_time_keyboard=True
    )
    
    await message.answer(text, reply_markup=kb)

# --- 5. ЛОГИКА ОПРОСА (Без изменений) ---

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

# --- 6. ФИНАЛ: ВЫЗОВ ГИБРИДНОЙ ФУНКЦИИ ---

@router.message(BrandAnalysis.waiting_for_explanation)
async def finish_survey(message: Message, state: FSMContext):
    await state.update_data(explanation_test=message.text)
    user_data = await state.get_data()
    
    waiting_msg = await message.answer(f"⏳ <b>Анализирую стратегию...</b>\n(Подключаюсь к Шлюзу...)")
    
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

    # --- ВЫЗЫВАЕМ УМНУЮ ГЕНЕРАЦИЮ ---
    content, model_name, source = await generate_smart_response(SYSTEM_PROMPT, input_data)
    
    await waiting_msg.delete()
    
    # Красивый футер с технической инфой
    footer = f"\n\n⚙️ <b>Модель:</b> {model_name}\n🔌 <b>Канал:</b> {source}"
    
    await message.answer(content + footer, parse_mode=ParseMode.HTML) # HTML чтобы работали bold теги из промпта если будут
    await state.clear()
