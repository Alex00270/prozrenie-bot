from aiogram import Router, F
from aiogram.types import Message
from .agents import call_agent

router = Router()

@router.message(F.text.lower().contains("ребята"))
async def start_consilium(message: Message):
    # 1. Выделяем идею
    user_idea = message.text
    status = await message.answer(f"🚀 **Команда услышала:**\n_{user_idea}_\n\nСобираем консилиум...")

    # 2. PM создает структуру
    await status.edit_text("⏳ **Проджект-менеджер** пишет roadmap...")
    pm_response = await call_agent("pm", f"Идея проекта: {user_idea}")

    # 3. Аналитик критикует PM
    await status.edit_text("⏳ **Аналитик** ищет уязвимости...")
    analyst_response = await call_agent("analyst", f"Идея: {user_idea}\n\nПлан PM: {pm_response}\n\nНайди риски.")

    # 4. Маркетолог ищет деньги
    await status.edit_text("⏳ **Маркетолог** считает бюджет...")
    marketer_response = await call_agent("marketer", f"Идея: {user_idea}. Как на этом заработать?")

    # 5. Редактор собирает итог
    await status.edit_text("✍️ **Главред** верстает отчет...")
    final_report = await call_agent("editor", 
        f"Собери финальный отчет.\n\nPM: {pm_response}\n\nAnalyst: {analyst_response}\n\nMarketer: {marketer_response}"
    )

    # 6. Публикация
    await status.delete() # Удаляем статус "печатает"
    await message.answer(final_report, parse_mode="Markdown")
