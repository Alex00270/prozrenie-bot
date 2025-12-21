from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from .agents import call_agent

router = Router()

# ВОТ ЭТОГО НЕ ХВАТАЛО:
@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 **AI Team Lead на связи!**\n\n"
        "Мои профили загружены. Чтобы начать мозговой штурм, напиши фразу со словом **'ребята'**.\n"
        "Например: *'Ребята, оцените идею продавать снег зимой'*."
    )

@router.message(F.text.lower().contains("ребята"))
async def start_consilium(message: Message):
    user_idea = message.text
    status = await message.answer(f"🚀 **Принято:**\n_{user_idea}_\n\nСобираю команду...")

    try:
        # PM
        await status.edit_text("⏳ **PM** составляет план...")
        pm_response = await call_agent("pm", f"Идея: {user_idea}")

        # Аналитик
        await status.edit_text("⏳ **Аналитик** ищет риски...")
        analyst_response = await call_agent("analyst", f"Идея: {user_idea}\nПлан: {pm_response}")

        # Маркетолог
        await status.edit_text("⏳ **Маркетолог** считает бюджет...")
        marketer_response = await call_agent("marketer", f"Идея: {user_idea}")

        # Редактор
        await status.edit_text("✍️ **Редактор** формирует отчет...")
        final_report = await call_agent("editor", 
            f"Итог:\nPM: {pm_response}\nAnalyst: {analyst_response}\nMarketer: {marketer_response}"
        )

        await status.delete()
        await message.answer(final_report, parse_mode="Markdown")

    except Exception as e:
        await status.edit_text(f"❌ Ошибка: {str(e)}")
