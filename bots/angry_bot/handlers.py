import os
import re
import google.generativeai as genai
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart
from database import db

router = Router()

# КЛЮЧ: Пытается взять ВТОРОЙ, если нет — берет первый
api_key = os.getenv("GEMINI_API_KEY_2") or os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# --- ЛОГИКА ПОИСКА (Та же самая) ---
def select_best_model():
    print("🔍 SKEPTIC: Сканирую модели...", flush=True)
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

# --- ЛИЧНОСТЬ: СКЕПТИК ---

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    bot_info = await bot.get_me()
    await db.add_user(user.id, user.username, user.full_name, bot_info.id)
    
    # ПРИВЕТСТВИЕ СКЕПТИКА
    text = (
        f"🤨 Ну что, пришел за правдой? Я <b>MySkepticBot</b>.\n"
        f"🧠 Мозги: <b>{CURRENT_MODEL_NAME.replace('models/', '')}</b>\n\n"
        f"Пиши свою 'гениальную' идею, я разнесу её в пух и прах."
    )
    await message.answer(text)

@router.message()
async def handle_message(message: Message):
    try:
        model = genai.GenerativeModel(CURRENT_MODEL_NAME)
        
        # ВОТ ГДЕ РОЖДАЕТСЯ ХАРАКТЕР
        system_prompt = (
            "Ты — циничный критик и скептик. "
            "Твоя цель — найти слабые места в идее пользователя. "
            "Используй сарказм, сленг, будь жестким, но аргументированным. "
            "Отвечай коротко. Вводные данные: "
        )
        
        # Склеиваем роль + сообщение пользователя
        full_text = system_prompt + message.text
        
        response = model.generate_content(full_text)
        await message.answer(response.text)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")
