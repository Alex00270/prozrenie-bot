import os
import re
import google.generativeai as genai
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart
from database import db

router = Router()

# КЛЮЧ: Использует основной
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- ЛОГИКА ПОИСКА (Одинаковая для всех) ---
def select_best_model():
    print("🔍 PROZRENIE: Сканирую модели...", flush=True)
    try:
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        def get_score(name):
            score = 0
            name = name.lower()
            if "gemma" in name:
                score += 1000
                size = re.search(r'(\d+)b', name)
                if size: score += int(size.group(1)) * 10
                if "gemma-3" in name: score += 50
            return score

        all_models.sort(key=get_score, reverse=True)
        if all_models: return all_models[0]
    except: pass
    return "models/gemini-1.5-pro"

CURRENT_MODEL_NAME = select_best_model()

# --- ЛИЧНОСТЬ: СТРАТЕГ ---

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    bot_info = await bot.get_me()
    await db.add_user(user.id, user.username, user.full_name, bot_info.id)
    
    # ПРИВЕТСТВИЕ СТРАТЕГА
    text = (
        f"👋 Привет! Я <b>AI-Стратег</b> (Бот Прозрение).\n"
        f"🧠 Мощность: <b>{CURRENT_MODEL_NAME.replace('models/', '')}</b>\n\n"
        f"Я готов помочь с анализом, идеями и стратегией. Пиши свой вопрос."
    )
    await message.answer(text)

@router.message()
async def handle_message(message: Message):
    try:
        model = genai.GenerativeModel(CURRENT_MODEL_NAME)
        # ПРОСТО ОТВЕТ (Без злого промпта)
        response = model.generate_content(message.text)
        await message.answer(response.text)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")
