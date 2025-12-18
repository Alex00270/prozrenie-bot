import os
import re
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
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 1. Ищем модели семейства Gemma
        gemma_candidates = [m for m in all_models if "gemma" in m.lower() and "it" in m.lower()]
        
        if gemma_candidates:
            # Функция для извлечения "мощности" (числа перед 'b', например 27 из '27b')
            def get_model_power(name):
                # Ищем конструкцию типа "9b", "27b"
                match = re.search(r'(\d+)b', name.lower())
                if match:
                    return int(match.group(1))
                return 0 # Если размер не указан, считаем слабой
            
            # Сортируем: сначала по мощности (27 > 9), потом по новизне (reverse=True)
            gemma_candidates.sort(key=lambda x: (get_model_power(x), x), reverse=True)
            
            return gemma_candidates[0] # Вернет самую мощную (например, gemma-2-27b-it)

        # 2. Если Gemma нет, ищем Gemini (Pro лучше Flash)
        gemini = [m for m in all_models if "gemini" in m.lower()]
        if gemini:
            # Тут простая эвристика: Pro > Flash
            gemini.sort(key=lambda x: 1 if "pro" in x.lower() else 0, reverse=True)
            return gemini[0]
            
    except Exception as e:
        print(f"DEBUG MODEL SELECTOR. Error: {e}", flush=True)
    
    # Запасной вариант
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
