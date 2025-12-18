import os
import google.generativeai as genai
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart
from database import db

router = Router()

# 1. Настройка API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# 2. Умный выбор модели (Взяли у первого бота)
def select_best_model():
    try:
        # Получаем список всех доступных моделей
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Ищем модели семейства gemma или gemini
        # Приоритет: Gemini 1.5 Flash -> Gemini Pro -> Любая другая
        for m in all_models:
            if "gemini-1.5-flash" in m:
                return m
            if "gemini-pro" in m:
                return m
                
        # Если ничего не нашли, берем первую попавшуюся
        if all_models:
            return all_models[0]
            
    except Exception as e:
        print(f"DEBUG SKEPTIC. Model select error: {e}", flush=True)
    
    # Совсем запасной вариант (без приставки models/)
    return "gemini-1.5-flash"

# Определяем модель при запуске
CURRENT_MODEL_NAME = select_best_model()
print(f"DEBUG SKEPTIC. Selected model: {CURRENT_MODEL_NAME}", flush=True)

# --- ОБРАБОТЧИКИ ---

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    bot_info = await bot.get_me()
    
    await db.add_user(user.id, user.username, user.full_name, bot_info.id)
    await message.answer("Ну что, пришел за критикой? Я MySkepticBot. Пиши идею, я разнесу её в пух и прах.")

@router.message()
async def handle_message(message: Message):
    try:
        # Используем динамически выбранную модель
        model = genai.GenerativeModel(CURRENT_MODEL_NAME)
        
        system_prompt = (
            "Ты — 'Злой Скептик'. Твоя задача — находить изъяны, логические ошибки и наивность "
            "в любых сообщениях пользователя. Будь саркастичным, используй черный юмор. "
            "Не хами открыто, но будь язвительным интеллектуалом. "
            "Отвечай коротко (2-3 предложения). Сообщение для разбора: "
        )
        
        response = model.generate_content(system_prompt + message.text)
        await message.answer(response.text)
    except Exception as e:
        print(f"DEBUG SKEPTIC. Error: {e}", flush=True)
        # Если ошибка, пробуем ответить заглушкой, но информативной
        await message.answer(f"Что-то пошло не так. Моя нейросеть подавилась ошибкой: {e}")
