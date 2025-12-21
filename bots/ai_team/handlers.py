from aiogram import Router, F
from aiogram.types import Message
from .agents import call_agent

router = Router()

@router.message(F.text.lower().contains("ребята"))
async def start_consilium(message: Message):
    user_idea = message.text
    
    # Отбивка пользователю
    status = await message.answer(f"🚀 **Принято:**\n_{user_idea}_\n\nСобираю команду...")

    try:
        # ЭТАП 1: PM (Структура)
        await status.edit_text("⏳ **PM** составляет план работ...")
        pm_response = await call_agent("pm", f"Идея проекта: {user_idea}")

        # ЭТАП 2: Аналитик (Критика)
        await status.edit_text("⏳ **Аналитик** ищет уязвимости...")
        analyst_response = await call_agent("analyst", f"Идея: {user_idea}\n\nПлан PM: {pm_response}\n\nКритикуй жестко.")

        # ЭТАП 3: Маркетолог (Деньги)
        await status.edit_text("⏳ **Маркетолог** считает бюджет...")
        marketer_response = await call_agent("marketer", f"Идея: {user_idea}. Как заработать?")

        # ЭТАП 4: Сборка отчета
        await status.edit_text("✍️ **Редактор** верстает итог...")
        final_report = await call_agent("editor", 
            f"Собери финальный отчет для владельца.\n\nPM: {pm_response}\n\nAnalyst: {analyst_response}\n\nMarketer: {marketer_response}"
        )

        # Финал
        await status.delete()
        await message.answer(final_report, parse_mode="Markdown")

    except Exception as e:
        await status.edit_text(f"❌ **Сбой консилиума:** {str(e)}")
