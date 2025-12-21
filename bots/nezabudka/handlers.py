import logging
import json
import html
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command

# Импорт нашего движка и базы
from utils.ai_engine import ask_brain, safe_reply
from database import db

router = Router()

# --- ЛОГИКА АНАЛИЗА ---
async def process_input(message: Message, text: str):
    # 1. Формируем промпт для Шлюза
    sys_prompt = (
        "Ты — AI-секретарь. Проанализируй текст и верни строго JSON.\n"
        "Поля: type (задача/идея/заметка), action (суть), tag (#тег), deadline (строка или 'нет')."
    )
    
    # 2. Стучимся в Шлюз
    content, model_info, source = await ask_brain(sys_prompt, text)
    
    # 3. Парсим ответ
    try:
        start = content.find('{')
        end = content.rfind('}')
        json_str = content[start:end+1]
        data = json.loads(json_str)
    except:
        data = {"type": "заметка", "action": text, "tag": "#inbox", "deadline": "нет"}

    # 4. Сохраняем в Монго
    task_doc = {
        "user_id": message.from_user.id,
        "created_at": datetime.utcnow(),
        "status": "pending",
        **data
    }
    await db.add_task(task_doc)

    # 5. Отвечаем
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Разбить на этапы", callback_data=f"decomp_")]
    ])
    
    header = f"✅ <b>{data.get('type', 'ЗАДАЧА').upper()}</b>"
    body = f"▫️ {html.escape(data.get('action', ''))}\n🏷 {html.escape(data.get('tag', ''))} | 📅 {data.get('deadline')}"
    
    await safe_reply(message, header, body, f"{model_info} | {source}", reply_markup=kb)


# --- ХЕНДЛЕРЫ ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("👋 <b>Незабудка AI</b> (Gateway Version).\nПиши задачу.", parse_mode="HTML")

@router.message(F.text)
async def handle_text(message: Message):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    await process_input(message, message.text)

@router.callback_query(F.data.startswith("decomp_"))
async def handle_decompose(callback: CallbackQuery):
    await callback.answer("Думаю...")
    task_text = callback.message.text 
    
    sys_prompt = "Ты PM. Разбей задачу на шаги. Верни список."
    content, model, src = await ask_brain(sys_prompt, f"Декомпозируй: {task_text}")
    
    await safe_reply(callback.message, "🔨 <b>План:</b>", content, f"{model} | {src}")
