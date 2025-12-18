import os
import google.generativeai as genai
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart
from database import db

router = Router()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "models/gemini-1.5-flash"

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    bot_info = await bot.get_me()
    
    # Сохраняем (Neon сам разберется с bot_id)
    await db.add_user(user.id, user.username, user.full_name, bot_info.id)
    
    await message.answer("Ну что, пришел за критикой? Я MySkepticBot. Пиши идею, я разнесу её в пух и прах.")

@router.message()
async def handle_message(message: Message):
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
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
        await message.answer("Скучно. Даже нейросеть зевает.")
