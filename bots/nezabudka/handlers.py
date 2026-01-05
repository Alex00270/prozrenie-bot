import logging
import json
import html
import os
import re
from datetime import datetime

import speech_recognition as sr
from pydub import AudioSegment

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, BotCommand
from aiogram.filters import Command, CommandObject

from utils.ai_engine import ask_brain, safe_reply
from database import db

router = Router()

# Версия, соответствующая функционалу
VERSION = "2.2 (Gateway + Restore)"

# --- СЛУЖЕБНЫЕ ФУНКЦИИ ---
async def track_and_auth(message: Message):
    """Трекинг активности пользователя"""
    await db.track_activity(message.from_user)

# --- ХЕНДЛЕРЫ ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    await track_and_auth(message)
    await message.answer(
        f"👋 <b>Незабудка AI</b> {VERSION}\n\n"
        "Я восстановлена и работаю с вашей старой базой!\n"
        "🎤 Голосовой ввод работает.\n"
        "📋 /list — список задач\n"
        "✅ /done N — выполнить задачу №N\n"
        "📊 /stats — статистика\n"
        "❓ /help — справка",
        parse_mode="HTML"
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await track_and_auth(message)
    text = (
        "🤖 <b>Помощь:</b>\n"
        "1. Просто напиши текст или запиши голосовое — я создам задачу.\n"
        "2. Жми [⚡ Декомпозиция] если задача сложная.\n"
        "3. <b>/list</b> — посмотреть список.\n"
        "4. <b>/done 1</b> — завершить задачу номер 1 из списка."
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    await track_and_auth(message)
    s = await db.get_global_stats()
    if not s:
        await message.answer("Статистика недоступна (ошибка БД).")
        return

    text = (
        "📊 <b>Статистика Nezabudka AI</b>\n\n"
        "👥 <b>Пользователи:</b>\n"
        f"• Всего: {s.get('u_total', 0)}\n"
        f"• Активные (24ч): {s.get('u_24h', 0)}\n"
        f"• Активные (7д): {s.get('u_7d', 0)}\n\n"
        "📝 <b>Задачи:</b>\n"
        f"• Всего: {s.get('t_total', 0)}\n"
        f"• В работе: {s.get('t_pending', 0)}"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("list"))
async def cmd_list(message: Message):
    await track_and_auth(message)
    tasks = await db.get_active_tasks(message.from_user.id, limit=30)
    
    if not tasks:
        await message.answer("📭 Список задач пуст.")
        return

    # Формируем список как в Dallas
    text = "📋 <b>Ваши активные задачи:</b>\n\n"
    for i, t in enumerate(tasks, 1):
        # Иконка родителя/обычной задачи
        icon = "🔹" if t.get('is_parent') else "🔸"
        action = html.escape(t.get('action', '...'))
        tag = html.escape(t.get('tag', ''))
        deadline = t.get('deadline', 'нет')
        
        text += f"<b>{i}.</b> {icon} {action} ({tag} | 📅 {deadline})\n"

    await message.answer(text, parse_mode="HTML")

@router.message(Command("done"))
async def cmd_done(message: Message, command: CommandObject):
    await track_and_auth(message)
    if not command.args:
        await message.answer("⚠️ Используйте: <code>/done 1</code> (номер задачи из списка)")
        return
    
    try:
        index = int(command.args)
        task_title = await db.mark_done_by_index(message.from_user.id, index)
        
        if task_title:
            await message.answer(f"✅ Выполнено: <b>{html.escape(task_title)}</b>", parse_mode="HTML")
        else:
            await message.answer("❌ Задача с таким номером не найдена (проверьте /list).")
    except ValueError:
        await message.answer("⚠️ Номер должен быть числом.")

@router.message(Command("version"))
async def cmd_version(message: Message):
    await message.answer(f"ℹ️ <b>System:</b>\nVer: {VERSION}\nDB: nezabudka_ai (Legacy Connected)")

# === ГОЛОСОВОЙ ВВОД (Voice Fix) ===
@router.message(F.voice)
async def handle_voice(message: Message):
    await track_and_auth(message)
    # Log
    print(f"DEBUG: Voice from {message.from_user.id}", flush=True)
    msg = await message.reply("🎧 Слушаю...")

    user_id = message.from_user.id
    ogg_filename = f"voice_{user_id}.ogg"
    wav_filename = f"voice_{user_id}.wav"

    try:
        file_info = await message.bot.get_file(message.voice.file_id)
        await message.bot.download_file(file_info.file_path, ogg_filename)
        
        # Convert
        AudioSegment.from_file(ogg_filename, format="ogg").export(wav_filename, format="wav")
        
        # Recognize
        r = sr.Recognizer()
        with sr.AudioFile(wav_filename) as source:
            audio_data = r.record(source)
            text = r.recognize_google(audio_data, language="ru-RU")
        
        await msg.edit_text(f"🗣 <i>{html.escape(text)}</i>", parse_mode="HTML")
        # Send to processing
        await process_input(message, text)

    except Exception as e:
        print(f"Voice Error: {e}", flush=True)
        await msg.edit_text("🤷‍♂️ Не расслышал.")
    finally:
        if os.path.exists(ogg_filename): os.remove(ogg_filename)
        if os.path.exists(wav_filename): os.remove(wav_filename)

# === ТЕКСТОВАЯ ОБРАБОТКА И AI ===
async def process_input(message: Message, text: str):
    # Промпт в стиле старого бота, но через Gateway
    sys_prompt = (
        "Ты — AI-секретарь. Проанализируй текст. Верни JSON.\n"
        "Поля: type (задача/идея), action (суть), tag (#тег), deadline (строка)."
    )
    content, model_info, _ = await ask_brain(sys_prompt, text)
    
    # Парсинг JSON
    try:
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            json_str = content[start:end+1]
            data = json.loads(json_str)
        else:
            raise ValueError("No JSON")
    except:
        # Fallback как в старом боте
        data = {"type": "Заметка", "action": text, "tag": "#inbox", "deadline": "нет"}

    # Сохранение
    task_doc = {
        "user_id": message.from_user.id,
        "type": data.get('type'),
        "action": data.get('action'),
        "tag": data.get('tag'),
        "deadline": data.get('deadline'),
        "status": "pending",
        "created_at": datetime.utcnow(),
        "is_parent": False
    }
    task_id = await db.add_task(task_doc)

    # Ответ пользователю
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Разбить на этапы", callback_data=f"decomp_{task_id}")]
    ])
    
    header = f"✅ <b>{data.get('type', 'ЗАДАЧА').upper()}</b>"
    body = f"▫️ {html.escape(data.get('action', ''))}\n🏷 {html.escape(data.get('tag', ''))} | 📅 {data.get('deadline')}"
    
    await safe_reply(message, header, body, f"{model_info}", reply_markup=kb)

@router.message(F.text)
async def handle_text(message: Message):
    await track_and_auth(message)
    await process_input(message, message.text)

@router.callback_query(F.data.startswith("decomp_"))
async def handle_decompose(callback: CallbackQuery):
    await callback.answer("Анализирую...")
    # Тут можно добавить логику декомпозиции, если нужно.
    # Пока просто заглушка, чтобы не падало, или реализация через Gateway
    task_id = callback.data.split("_")[1]
    
    # Можно запросить текст задачи из базы по ID, но пока упростим
    sys_prompt = "Ты PM. Разбей задачу на шаги. JSON: {subtasks: [{title}]}"
    content, _, _ = await ask_brain(sys_prompt, "Декомпозируй задачу")
    
    await safe_reply(callback.message, "🔨 <b>План:</b>", content, "AI")
