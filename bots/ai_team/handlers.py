import os
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
# Импортируем наш Универсальный Движок
from utils.ai_engine import ask_brain, safe_reply

router = Router()

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ АГЕНТОВ ---
async def run_agent(role: str, prompt: str):
    """
    1. Читает профиль агента (PM, Analyst и т.д.)
    2. Отправляет задачу в Центральный Двигатель.
    3. Возвращает текст и подпись модели.
    """
    current_dir = os.path.dirname(__file__)
    profile_path = os.path.join(current_dir, "profiles", f"{role}.txt")
    
    # Пытаемся прочитать профиль
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    except:
        system_prompt = "Ты полезный AI-ассистент в составе команды разработки."

    # ЗАПРОС К МОЗГУ (через ai_engine)
    content, model, source = await ask_brain(system_prompt, prompt)
    
    # Формируем красивую подпись для футера
    model_info = f"{model} | {source}"
    return content, model_info


# --- ХЕНДЛЕРЫ ---

@router.message(CommandStart())
async def cmd_start(message: Message):
    # Просто показываем намерение
    target = os.getenv("MODEL_NAME", "auto")
    await message.answer(
        f"👋 **AI Team Lead на связи!**\n"
        f"🎯 Цель: `{target}`\n\n"
        "Напиши задачу со словом **'ребята'**, и я соберу консилиум."
    )

@router.message(F.text.lower().contains("ребята"))
async def start_consilium(message: Message):
    user_idea = message.text
    
    # Визуальный старт
    await message.answer(f"🚀 **Задача принята:**\n_{user_idea}_\n\nСозываю команду...")

    try:
        # 1. PM (План v1)
        await message.answer("1️⃣ **PM** строит архитектуру...")
        pm_text, pm_info = await run_agent("pm", f"Задача клиента: {user_idea}")
        await safe_reply(message, "👷‍♂️ **PM (План):**", pm_text, pm_info)

        # 2. Аналитик (Критика)
        await message.answer("2️⃣ **Аналитик** ищет риски...")
        an_text, an_info = await run_agent("analyst", f"Задача: {user_idea}\n\nПлан PM: {pm_text}\n\nКритикуй жестко.")
        await safe_reply(message, "🕵️‍♂️ **Аналитик:**", an_text, an_info)

        # 3. Маркетолог (Деньги)
        mark_text, mark_info = await run_agent("marketer", f"Задача: {user_idea}\n\nПлан PM: {pm_text}\n\nКак на этом заработать?")
        await safe_reply(message, "🤑 **Маркетолог:**", mark_text, mark_info)

        # 4. PM (План v2 - Финал)
        await message.answer("3️⃣ **PM** исправляет ошибки...")
        fin_text, fin_info = await run_agent("pm", 
            f"Перепиши план с учетом критики.\nСтарый план: {pm_text}\nКритика Аналитика: {an_text}\nИдеи Маркетолога: {mark_text}"
        )
        await safe_reply(message, "🏁 **Итог (v2.0):**", fin_text, fin_info)
        
        # 5. Редактор (Отчет)
        await message.answer("✍️ **Редактор** формирует документ...")
        report, report_info = await run_agent("editor", f"Собери итоговое саммари:\n{fin_text}")
        await safe_reply(message, "📑 **ОТЧЕТ:**", report, report_info)

    except Exception as e:
        await message.answer(f"❌ Сбой консилиума: {e}")

# --- БОЛТАЛКА (Для тестов без слова 'ребята') ---
@router.message() 
async def handle_any_other_text(message: Message):
    status = await message.answer("🤔 ...")
    try:
        # Используем роль PM как собеседника по умолчанию
        text, info = await run_agent("pm", message.text)
        await status.delete()
        await safe_reply(message, "🗣 **Ответ:**", text, info)
    except Exception as e:
        await status.edit_text(f"❌ Ошибка: {e}")
