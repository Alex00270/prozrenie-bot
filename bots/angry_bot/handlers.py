import os
import google.generativeai as genai
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart
from database import db

router = Router()

# Настройка API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- УМНЫЙ ПОИСК МОДЕЛИ (Точно такой же, как у первого бота) ---
def select_best_model():
    try:
        # 1. Получаем список всех моделей
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 2. Ищем Gemma (сортируем, чтобы взять самую свежую, например Gemma 3)
        gemma = [m for m in all_models if "gemma" in m.lower() and "it" in m.lower()]
        if gemma:
            gemma.sort(key=lambda x: x, reverse=True) 
            return gemma[0] # <-- Вот тут он сам возьмет gemma-3-27b-it
            
        # 3. Если Gemma нет, ищем любую Gemini
        gemini = [m for m in all_models if "gemini" in m.lower()]
        if gemini:
            return gemini[0]
            
    except Exception as e:
        print(f"DEBUG SKEPTIC. Model select error: {e}", flush=True)
    
    return "gemini-1.5-flash"

# Запускаем выбор
CURRENT_MODEL_NAME = select_best_model()
print(f"DEBUG SKEPTIC. Selected model: {CURRENT_MODEL_NAME}", flush=True)

# --- ОБРАБОТЧИКИ ---

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    bot_info = await bot.get_me()
    
    await db.add_user(user.id, user.username, user.full_name, bot_info.id)
    
    # Формируем приветствие с указанием модели
    text = (
        f"Ну что, пришел за критикой? Я MySkepticBot.\n"
        f"🧠 Мои текущие мозги: <b>{CURRENT_MODEL_NAME}</b>\n\n"
        f"Пиши свою идею, я разнесу её в пух и прах."
    )
    
    await message.answer(text)

@router.message()
async def handle_message(message: Message):
    try:
        model = genai.GenerativeModel(CURRENT_MODEL_NAME)
        
        # ХАРАКТЕР БОТА
        system_prompt = (
            "Ты — 'Злой Скептик'. Твоя задача — находить изъяны, логические ошибки и наивность "
            "в любых сообщениях пользователя. Будь саркастичным, используй черный юмор, мат и сленг (умеренно). "
            "Твоя цель — спустить пользователя с небес на землю. "
            "Отвечай коротко (2-3 предложения). Сообщение для разбора: "
        )
        
        response = model.generate_content(system_prompt + message.text)
        await message.answer(response.text)
    except Exception as e:
        print(f"DEBUG SKEPTIC. Error: {e}", flush=True)
        await message.answer(f"⚠️ Ошибка нейросети: {e}")
