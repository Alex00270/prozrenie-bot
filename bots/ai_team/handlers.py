import os
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from .agents import call_agent

router = Router()

# --- ФУНКЦИЯ БЕЗОПАСНОЙ ОТПРАВКИ ---
async def safe_send(message: Message, header: str, content: str, model_name: str):
    """
    Пытается отправить сообщение с Markdown.
    Если падает ошибка (битые символы), отправляет чистый текст.
    """
    # Собираем красивый текст
    full_text_md = f"{header}\n\n{content}\n\n⚙️ _Выполнил: {model_name}_"
    
    try:
        # Попытка 1: Markdown (Красиво)
        await message.answer(full_text_md, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logging.warning(f"Markdown failed: {e}. Fallback to plain text.")
        try:
            # Попытка 2: HTML (Иногда помогает, если Markdown глючит)
            # Экранируем < и > на всякий случай, если это HTML
            safe_content = content.replace("<", "&lt;").replace(">", "&gt;")
            full_text_html = f"{header}\n\n{safe_content}\n\n⚙️ <i>Выполнил: {model_name}</i>"
            await message.answer(full_text_html, parse_mode=ParseMode.HTML)
        except Exception as e2:
            logging.warning(f"HTML failed: {e2}. Fallback to None.")
            # Попытка 3: Чистый текст (Железобетонно)
            # Убираем жирность из хедера для чистого текста
            clean_header = header.replace("*", "")
            plain_text = f"{clean_header}\n\n{content}\n\n⚙️ Выполнил: {model_name}"
            await message.answer(plain_text, parse_mode=None)

# --- ХЕНДЛЕРЫ ---

@router.message(CommandStart())
async def cmd_start(message: Message):
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
        pm_text, pm_model = await call_agent("pm", f"Идея: {user_idea}")
        
        # Используем безопасную отправку
        await safe_send(message, "👷‍♂️ **PM (План):**", pm_text, pm_model)

        # --- КРИТИКА ---
        await message.answer("2️⃣ **Критика...**")
        
        analyst_text, an_model = await call_agent("analyst", f"Критикуй: {user_idea}", previous_context=pm_text)
        await safe_send(message, "🕵️‍♂️ **Аналитик:**", analyst_text, an_model)
        
        marketer_text, mk_model = await call_agent("marketer", f"Где деньги?: {user_idea}", previous_context=pm_text)
        await safe_send(message, "🤑 **Маркетолог:**", marketer_text, mk_model)

        # --- ДОРАБОТКА ---
        await message.answer("3️⃣ **PM исправляет ошибки...**")
        
        pm_v2_text, pm_v2_model = await call_agent("pm", 
            "Исправь план с учетом критики.",
            previous_context=f"План: {pm_text}\nКритика: {analyst_text}\nДеньги: {marketer_text}"
        )
        await safe_send(message, "👷‍♂️ **PM (Финал v2.0):**", pm_v2_text, pm_v2_model)

        # --- ИТОГ ---
        await message.answer("✍️ **Итог...**")
        final_text, ed_model = await call_agent("editor", 
            "Собери отчет.",
            previous_context=f"Финал: {pm_v2_text}"
        )
        await safe_send(message, "📑 **ОТЧЕТ:**", final_text, ed_model)

    except Exception as e:
        await message.answer(f"❌ Критическая ошибка процесса: {str(e)}")

# --- БОЛТАЛКА (Тест модели) ---
@router.message() 
async def handle_any_other_text(message: Message):
    """Отвечает на любые сообщения без 'ребята'"""
    user_text = message.text
    status = await message.answer("🤔 ...")

    try:
        content, model_name = await call_agent("pm", user_text)
        # Тоже через безопасную функцию, но чуть иначе т.к. message уже отправлен
        # Проще отправить новое сообщение, а статус удалить, или просто safe_send
        await status.delete()
        await safe_send(message, "🗣 **Ответ:**", content, model_name)
        
    except Exception as e:
        await status.edit_text(f"❌ Ошибка: {e}")
