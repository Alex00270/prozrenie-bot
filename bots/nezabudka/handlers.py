import logging
import json
import html
import os
from datetime import datetime

# --- ВНЕДРЕНИЕ: Библиотеки для голоса ---
import speech_recognition as sr
from pydub import AudioSegment
# ----------------------------------------

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command

# Импорт твоего движка и базы
from utils.ai_engine import ask_brain, safe_reply
from database import db

router = Router()

# --- ЛОГИКА АНАЛИЗА (ТВОЙ КОД) ---
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
    await message.answer("👋 <b>Незабудка AI</b> (Gateway Version).\nПиши задачу или отправь голосовое.", parse_mode="HTML")

# === ВНЕДРЕНИЕ: Обработчик голоса (LEGACY FIX) ===
@router.message(F.voice)
async def handle_voice(message: Message):
    # Логирование для отладки на Render
    print(f"DEBUG: Voice received from {message.from_user.id}", flush=True)
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    user_id = message.from_user.id
    ogg_filename = f"voice_{user_id}.ogg"
    wav_filename = f"voice_{user_id}.wav"

    try:
        # 1. Скачиваем
        file_info = await message.bot.get_file(message.voice.file_id)
        await message.bot.download_file(file_info.file_path, ogg_filename)
        
        # 2. Конвертируем (нужен ffmpeg)
        print("DEBUG: Converting OGG -> WAV", flush=True)
        audio = AudioSegment.from_file(ogg_filename, format="ogg")
        audio.export(wav_filename, format="wav")
        
        # 3. Распознаем
        print("DEBUG: Sending to Google", flush=True)
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_filename) as source:
            audio_data = recognizer.record(source)
            # Ставим русский язык жестко, так как бот русскоязычный
            text = recognizer.recognize_google(audio_data, language="ru-RU")
        
        print(f"DEBUG: Recognized: {text}", flush=True)

        # 4. Передаем в ТВОЮ функцию process_input
        await message.reply(f"🎤 <i>{text}</i>", parse_mode="HTML")
        await process_input(message, text)

    except Exception as e:
        print(f"CRITICAL VOICE ERROR: {e}", flush=True)
        await message.answer("❌ Ошибка обработки голоса. Проверьте логи.")
    finally:
        # Чистим файлы
        if os.path.exists(ogg_filename):
            os.remove(ogg_filename)
        if os.path.exists(wav_filename):
            os.remove(wav_filename)
# =================================================

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
