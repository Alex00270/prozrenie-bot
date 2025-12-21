from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
# Импортируем наш единый мозг
from utils.ai_engine import ask_brain, safe_reply

router = Router()

class BrandAnalysis(StatesGroup):
    waiting_for_audience = State()
    waiting_for_problem = State()
    waiting_for_current_pos = State()
    waiting_for_competitors = State()
    waiting_for_rtb = State()
    waiting_for_explanation = State()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot):
    user = message.from_user
    bot_info = await bot.get_me()
    await db.add_user(user.id, user.username, user.full_name, bot_info.id)
    await state.clear()
    
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚀 Начать")]], resize_keyboard=True)
    
    # Заголовка модели тут нет, потому что мы еще не спрашивали движок
    await message.answer(
        "👋 Привет! Я AI-Стратег.\nЖми кнопку, чтобы начать разбор.", 
        reply_markup=kb
    )

@router.message(F.text == "🚀 Начать")
async def start_survey(message: Message, state: FSMContext):
    await message.answer("1. Кто твоя аудитория?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(BrandAnalysis.waiting_for_audience)

@router.message(BrandAnalysis.waiting_for_audience)
async def step_problem(message: Message, state: FSMContext):
    await state.update_data(audience=message.text)
    await message.answer("2. Какая у них проблема?")
    await state.set_state(BrandAnalysis.waiting_for_problem)

@router.message(BrandAnalysis.waiting_for_problem)
async def step_current_pos(message: Message, state: FSMContext):
    await state.update_data(problem=message.text)
    await message.answer("3. Твой оффер (решение)?")
    await state.set_state(BrandAnalysis.waiting_for_current_pos)

@router.message(BrandAnalysis.waiting_for_current_pos)
async def step_competitors(message: Message, state: FSMContext):
    await state.update_data(current_positioning=message.text)
    await message.answer("4. Кто конкуренты?")
    await state.set_state(BrandAnalysis.waiting_for_competitors)

@router.message(BrandAnalysis.waiting_for_competitors)
async def step_rtb(message: Message, state: FSMContext):
    await state.update_data(competitors=message.text)
    await message.answer("5. Почему тебе нужно верить (факты)?")
    await state.set_state(BrandAnalysis.waiting_for_rtb)

@router.message(BrandAnalysis.waiting_for_rtb)
async def step_explanation(message: Message, state: FSMContext):
    await state.update_data(reason_to_believe=message.text)
    await message.answer("6. Как клиент объяснит другу, чем ты занимаешься?")
    await state.set_state(BrandAnalysis.waiting_for_explanation)

@router.message(BrandAnalysis.waiting_for_explanation)
async def finish_survey(message: Message, state: FSMContext):
    await state.update_data(explanation_test=message.text)
    data = await state.get_data()
    
    status = await message.answer("⏳ Анализирую...", reply_markup=ReplyKeyboardRemove())
    
    prompt = """
    Ты опытный Стратег. Твоя задача — проанализировать ответы и дать краткий, жесткий разбор.
    Формат ответа (используй Markdown):
    1. **Диагноз**
    2. **Тест 10 секунд**
    3. **3 Гипотезы роста**
    """
    
    # 1. Запрос в Центр
    text, model, src = await ask_brain(prompt, str(data))
    
    # 2. Удаляем статус
    await status.delete()
    
    # 3. Безопасная отправка
    await safe_reply(message, "📊 **Стратегия:**", text, f"{model} | {src}")
    
    await state.clear()
