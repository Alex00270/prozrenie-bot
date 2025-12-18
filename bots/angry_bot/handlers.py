import os
import re
import google.generativeai as genai
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart
from database import db

router = Router()

# --- 1. НАСТРОЙКА КЛЮЧА ---
# (Для angry_bot раскомментируйте вторую строку)
# api_key = os.getenv("GEMINI_API_KEY_2") or os.getenv("GEMINI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- 2. УМНЫЙ ВЫБОР (Как в вашем тестере + Математика) ---
def select_best_model():
    print("🔍 СКАНЕР МОДЕЛЕЙ (Запуск...)", flush=True)
    try:
        # Получаем список (как в вашем скрипте)
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Функция оценки крутости модели
        def get_model_score(name):
            score = 0
            name = name.lower()
            
            # --- GEMMA (Любимая) ---
            if "gemma" in name:
                score += 1000 # База для Gemma
                
                # Ищем размер (27b, 9b, 2b)
                # re.search найдет цифру перед 'b'. 27b даст 27.
                size = re.search(r'(\d+)b', name)
                if size:
                    score += int(size.group(1)) * 10  # 27b -> +270 очков
                
                # Ищем версию (gemma-2, gemma-3)
                ver = re.search(r'gemma-(\d)', name)
                if ver:
                    score += int(ver.group(1)) * 50   # v3 -> +150 очков

            # --- GEMINI (Запасная) ---
            elif "gemini" in name:
                score += 500
                if "pro" in name: score += 100
                if "1.5" in name: score += 50
            
            return score

        # Сортируем список: у кого больше очков — тот первый
        available_models.sort(key=get_model_score, reverse=True)
        
        if available_models:
            best = available_models[0]
            print(f"🏆 ИТОГ: Выбрана {best} (Очков: {get_model_score(best)})", flush=True)
            return best
            
    except Exception as e:
        print(f"❌ Ошибка сканера: {e}", flush=True)

    # Если вообще всё упало (интернета нет, ключ сгорел), только тогда возвращаем строку
    return "models/gemini-1.5-pro"

# Запускаем выбор
CURRENT_MODEL_NAME = select_best_model()

# --- 3. ОБРАБОТЧИКИ ---

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    bot_info = await bot.get_me()
    await db.add_user(user.id, user.username, user.full_name, bot_info.id)
    
    # Красивое имя модели для вывода (убираем models/)
    model_display = CURRENT_MODEL_NAME.replace("models/", "")
    
    text = (
        f"Привет! Это бот {bot_info.first_name}.\n"
        f"🧠 Мозг: <b>{model_display}</b>\n\n"
        f"Пиши, я готов."
    )
    await message.answer(text)

@router.message()
async def handle_message(message: Message):
    try:
        model = genai.GenerativeModel(CURRENT_MODEL_NAME)
        # ВАЖНО: Для Скептика тут нужно добавить system_prompt перед message.text
        # Для Прозрения — просто message.text
        response = model.generate_content(message.text) 
        await message.answer(response.text)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка модели: {e}")
