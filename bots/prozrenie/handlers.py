import os
import logging
import google.generativeai as genai
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart
from database import db

router = Router()

# --- НАСТРОЙКИ GEMINI ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Выбор модели
def select_best_model():
    try:
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        gemma = [m for m in all_models if "gemma" in m.lower() and "it" in m.lower()]
        if gemma:
            gemma.sort(key=lambda x: x, reverse=True) 
            return gemma[0]
    except Exception as e:
        print(f"DEBUG PROZRENIE. Model error: {e}", flush=True)
    return "models/gemini-1.5-flash"

CURRENT_MODEL_NAME = select_best_model()

# --- ОБРАБОТЧИКИ ---

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    bot_info = await bot.get_me()
    
    # Сохраняем в БД с bot_id
    await db.add_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
        bot_id=bot_info.id
    )
    
    await message.answer("Привет! Я переехал в новую структуру папок. Задай мне вопрос!")

@router.message()
async def handle_message(message: Message):
    try:
        model = genai.GenerativeModel(CURRENT_MODEL_NAME)
        response = model.generate_content(message.text)
        await message.answer(response.text)
    except Exception as e:
        print(f"DEBUG PROZRENIE. Error: {e}", flush=True)
        await message.answer("Ошибка нейросети.")
