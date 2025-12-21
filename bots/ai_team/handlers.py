import os
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from utils.ai_engine import ask_brain, safe_reply

router = Router()

# Состояния диалога
class ProjectBriefing(StatesGroup):
    waiting_for_clarification = State() # Ждем ответа на уточняющие вопросы
    ready_to_launch = State()         # Готовы запускать консилиум

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def run_agent(role: str, prompt: str):
    current_dir = os.path.dirname(__file__)
    try:
        with open(os.path.join(current_dir, "profiles", f"{role}.txt"), "r") as f:
            system_prompt = f.read()
    except:
        system_prompt = "Ты эксперт."
    content, model, source = await ask_brain(system_prompt, prompt)
    return content, f"{model} | {source}"

async def analyze_input(user_text: str):
    """
    PM проверяет, понятна ли задача.
    Возвращает: (is_good: bool, reason: str)
    """
    system_prompt = (
        "Ты Senior PM. Твоя задача — проверить входящий запрос на адекватность.\n"
        "1. Проверь на критические опечатки (например 'к руб' вместо цифры).\n"
        "2. Хватает ли данных для стратегии?\n"
        "Если запрос плохой или непонятный, задай 2-3 уточняющих вопроса.\n"
        "Если запрос хороший, ответь одним словом: APPROVED."
    )
    content, _, _ = await ask_brain(system_prompt, user_text)
    
    if "APPROVED" in content:
        return True, ""
    else:
        return False, content

# --- ХЕНДЛЕРЫ ---

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    target = os.getenv("MODEL_NAME", "auto")
    await message.answer(
        f"👋 **AI Team Lead.** Цель: `{target}`\n\n"
        "Напиши идею. Я сначала проверю её, задам вопросы, и только потом позовем команду."
    )

# 1. ПЕРВИЧНЫЙ АНАЛИЗ
@router.message(F.text & ~F.text.startswith("/"))
async def initial_check(message: Message, state: FSMContext):
    # Проверяем текущее состояние
    current_state = await state.get_state()
    
    # Если мы уже в процессе обсуждения, передаем дальше (в handle_clarification)
    if current_state == ProjectBriefing.waiting_for_clarification:
        await handle_clarification(message, state)
        return

    user_idea = message.text
    msg = await message.answer("🧐 PM читает ТЗ...")

    # PM анализирует ввод
    is_good, response = await analyze_input(user_idea)
    
    await msg.delete()

    if is_good:
        # Если всё ок сразу — запускаем
        await start_consilium_logic(message, user_idea)
    else:
        # Если есть вопросы — спрашиваем
        await state.update_data(original_idea=user_idea)
        await state.set_state(ProjectBriefing.waiting_for_clarification)
        await safe_reply(message, "✋ **Нужны уточнения:**", response, "PM Gatekeeper")

# 2. ОБРАБОТКА ОТВЕТА ПОЛЬЗОВАТЕЛЯ
async def handle_clarification(message: Message, state: FSMContext):
    data = await state.get_data()
    original_idea = data.get("original_idea", "")
    clarification = message.text
    
    # Объединяем старое и новое
    full_context = f"Изначальная идея: {original_idea}\nУточнение пользователя: {clarification}"
    
    msg = await message.answer("ok, теперь понятно. Зову команду...")
    
    # Сбрасываем стейт и запускаем
    await state.clear()
    await start_consilium_logic(message, full_context)


# 3. ЛОГИКА КОНСИЛИУМА (То, что было раньше)
async def start_consilium_logic(message: Message, full_task: str):
    try:
        # 1. PM (План)
        pm_msg = await message.answer("1️⃣ **PM** строит структуру...")
        pm_text, pm_info = await run_agent("pm", f"Задача: {full_task}")
        await pm_msg.delete()
        await safe_reply(message, "👷‍♂️ **PM (План):**", pm_text, pm_info)

        # 2. Аналитик
        an_msg = await message.answer("2️⃣ **Аналитик** ищет риски...")
        an_text, an_info = await run_agent("analyst", f"Задача: {full_task}\n\nПлан PM: {pm_text}")
        await an_msg.delete()
        await safe_reply(message, "🕵️‍♂️ **Аналитик:**", an_text, an_info)

        # 3. Маркетолог
        mark_msg = await message.answer("🤑 **Маркетолог** считает...")
        mark_text, mark_info = await run_agent("marketer", f"Задача: {full_task}\n\nКонтекст: {pm_text}")
        await mark_msg.delete()
        await safe_reply(message, "🤑 **Маркетолог:**", mark_text, mark_info)

        # 4. Финал (PM v2)
        fin_msg = await message.answer("🏁 **PM** подводит итог...")
        fin_text, fin_info = await run_agent("pm", 
            f"Финальный план.\nЗадача: {full_task}\nКритика: {an_text}\nМаркетинг: {mark_text}"
        )
        await fin_msg.delete()
        await safe_reply(message, "🚀 **Roadmap:**", fin_text, fin_info)

    except Exception as e:
        await message.answer(f"❌ Сбой: {e}")
