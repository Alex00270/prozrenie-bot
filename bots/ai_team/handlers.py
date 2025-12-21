import os
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from .agents import call_agent

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    # Показываем, что сейчас настроено в Render
    target_model = os.getenv("MODEL_NAME", "auto (на усмотрение шлюза)")
    
    await message.answer(
        f"👋 **AI Team Lead на связи!**\n"
        f"🎯 Целевая модель: `{target_model}`\n\n"
        "Я отправлю твой запрос в Шлюз, а он выберет исполнителя.\n"
        "Напиши задачу со словом **'ребята'**."
    )

@router.message(F.text.lower().contains("ребята"))
async def start_consilium(message: Message):
    user_idea = message.text
    
    await message.answer(f"🚀 **Задача принята.**\n_{user_idea}_\n\nСозываю консилиум...")

    try:
        # --- PM ---
        await message.answer("1️⃣ **PM** готовит план...")
        # Получаем текст и ФАКТИЧЕСКУЮ модель
        pm_text, pm_model = await call_agent("pm", f"Идея: {user_idea}")
        
        await message.answer(
            f"👷‍♂️ **PM (План):**\n\n{pm_text}\n\n"
            f"⚙️ _Выполнил: {pm_model}_" 
        )

        # --- КРИТИКА ---
        await message.answer("2️⃣ **Критика...**")
        
        analyst_text, an_model = await call_agent("analyst", f"Критикуй: {user_idea}", previous_context=pm_text)
        await message.answer(f"🕵️‍♂️ **Аналитик:**\n\n{analyst_text}\n\n⚙️ _{an_model}_")
        
        marketer_text, mk_model = await call_agent("marketer", f"Где деньги?: {user_idea}", previous_context=pm_text)
        await message.answer(f"🤑 **Маркетолог:**\n\n{marketer_text}\n\n⚙️ _{mk_model}_")

        # --- ДОРАБОТКА ---
        await message.answer("3️⃣ **PM исправляет ошибки...**")
        
        pm_v2_text, pm_v2_model = await call_agent("pm", 
            "Исправь план с учетом критики.",
            previous_context=f"План: {pm_text}\nКритика: {analyst_text}\nДеньги: {marketer_text}"
        )
        await message.answer(
            f"👷‍♂️ **PM (Финал v2.0):**\n\n{pm_v2_text}\n\n"
            f"⚙️ _Выполнил: {pm_v2_model}_"
        )

        # --- ИТОГ ---
        await message.answer("✍️ **Итог...**")
        final_text, ed_model = await call_agent("editor", 
            "Собери отчет.",
            previous_context=f"Финал: {pm_v2_text}"
        )
        
        await message.answer(final_text, parse_mode="Markdown")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
