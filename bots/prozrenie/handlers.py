import os
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

# --- 1. РЕЗЕРВ (Google Direct) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- 2. ФУНКЦИЯ: УМНЫЙ ЗАПРОС + БЕЗОПАСНАЯ ОТПРАВКА ---
async def generate_and_send(message: Message, prompt: str, user_data: str):
    """
    1. Идет в Шлюз (Dallas).
    2. Если нет - в Google Direct.
    3. Отправляет ответ БЕЗОПАСНО (без ошибок разметки).
    """
    gateway_url = os.getenv("GATEWAY_BASE_URL")
    gateway_key = os.getenv("GATEWAY_API_KEY")
    target_model = os.getenv("MODEL_NAME", "auto")
    
    content = ""
    real_model = "Unknown"
    source = "Unknown"

    # А. Попытка через Шлюз
    if gateway_url and gateway_key:
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(
                    f"{gateway_url}/chat/completions",
                    headers={"Authorization": f"Bearer {gateway_key}"},
                    json={
                        "model": target_model, 
                        "messages": [
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": user_data}
                        ]
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    real_model = data.get("model", target_model)
                    source = "📡 Gateway"
        except Exception as e:
            logging.error(f"Gateway failed: {e}")

    # Б. Резерв (если Шлюз не сработал)
    if not content:
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(f"{prompt}\n\nDATA:\n{user_data}")
            content = response.text
            real_model = "gemini-1.5-flash"
            source = "🔌 Backup"
        except Exception as e:
            content = f"❌ Ошибка генерации: {e}"
            source = "Dead"

    # В. Безопасная отправка (чтобы не было Bad Request)
    header = f"⚙️ **Модель:** `{real_model}` | **Канал:** `{source}`"
    full_text = f"{content}\n\n{header}"

    try:
        # 1. Пробуем Markdown (красиво)
        await message.answer(full_text, parse_mode=ParseMode.MARKDOWN)
    except:
        try:
            # 2. Если упало - пробуем HTML (без Markdown символов)
            # Примитивная замена, чтобы спасти текст
            safe_content = content.replace("<", "&lt;").replace(">", "&gt;")
            safe_header = f"⚙️ <b>Модель:</b> {real_model} | <b>Канал:</b> {source}"
            await message.answer(f"{safe_content}\n\n{safe_header}", parse_mode=ParseMode.HTML)
        except:
            # 3. Если и это упало - просто текст (надежно)
            clean_text = full_text.replace("*", "").replace("`", "")
            await message.answer(clean_text, parse_mode=None)


# --- 3. FSM (ОПРОСНИК) ---
class BrandAnalysis(StatesGroup):
    waiting_for_audience = State()
    waiting_for_problem = State()
    waiting_for_current_pos = State()
    waiting_for_competitors = State()
    waiting_for_rtb = State()
    waiting_for_explanation = State()


# --- 4. ХЕНДЛЕРЫ ---

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    bot_info = await bot.get_me()
    await db.add_user(user.id, user.username, user.full_name, bot_info.id)
    await state.clear()
    
    # Читаем намерение из Render (но не хардкодим имя)
    target = os.getenv("MODEL_NAME", "Auto-Select")
    
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚀 Начать")]], resize_keyboard=True, one_time_keyboard=True)
    
    # ВОТ ЗДЕСЬ БЫЛ ХАРДКОД. ТЕПЕРЬ ЕГО НЕТ.
    await message.answer(
        f"👋 Привет! Я AI-Стратег.\n"
        f"🎯 Цель: <b>{target}</b>\n"
        f"Нажми кнопку, чтобы начать.", 
        reply_markup=kb,
        parse_mode=ParseMode.HTML
    )

@router.message(F.text == "🚀 Начать")
async def start_survey(message: Message, state: FSMContext):
    await message.answer("1. Аудитория?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(BrandAnalysis.waiting_for_audience)

@router.message(BrandAnalysis.waiting_for_audience)
async def step_problem(message: Message, state: FSMContext):
    await state.update_data(audience=message.text)
    await message.answer("2. Проблема?")
    await state.set_state(BrandAnalysis.waiting_for_problem)

@router.message(BrandAnalysis.waiting_for_problem)
async def step_current_pos(message: Message, state: FSMContext):
    await state.update_data(problem=message.text)
    await message.answer("3. Оффер?")
    await state.set_state(BrandAnalysis.waiting_for_current_pos)

@router.message(BrandAnalysis.waiting_for_current_pos)
async def step_competitors(message: Message, state: FSMContext):
    await state.update_data(current_positioning=message.text)
    await message.answer("4. Конкуренты?")
    await state.set_state(BrandAnalysis.waiting_for_competitors)

@router.message(BrandAnalysis.waiting_for_competitors)
async def step_rtb(message: Message, state: FSMContext):
    await state.update_data(competitors=message.text)
    await message.answer("5. Почему верить?")
    await state.set_state(BrandAnalysis.waiting_for_rtb)

@router.message(BrandAnalysis.waiting_for_rtb)
async def step_explanation(message: Message, state: FSMContext):
    await state.update_data(reason_to_believe=message.text)
    await message.answer("6. Как объясняют другу?")
    await state.set_state(BrandAnalysis.waiting_for_explanation)

@router.message(BrandAnalysis.waiting_for_explanation)
async def finish_survey(message: Message, state: FSMContext):
    await state.update_data(explanation_test=message.text)
    data = await state.get_data()
    
    # Удаляем клавиатуру и показываем статус
    msg = await message.answer("⏳ Думаю...", reply_markup=ReplyKeyboardRemove())
    
    prompt = """
    Ты Стратег. Твоя задача — проанализировать ответы и дать краткий, жесткий разбор.
    Формат: Диагноз, Тест 10 секунд, 3 Гипотезы.
    Используй Markdown.
    """
    
    # Генерация + Отправка
    await generate_and_send(msg, prompt, str(data))
    
    await state.clear()
