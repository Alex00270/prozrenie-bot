import os
import logging
import json
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import Command

# Библиотеки для файлов
import docx
from pypdf import PdfReader

# Импорт из корня
from utils.ai_engine import ask_brain, safe_reply
# Импорт промптов из ТЕКУЩЕЙ папки
from bots.zi_files.prompts import SYSTEM_CORRECTOR, SYSTEM_STYLIST

logger = logging.getLogger(__name__)
router = Router()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def extract_text_from_file(bot: Bot, file_id: str, file_name: str) -> str:
    """Скачивает файл и вытаскивает текст"""
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path
    
    # Временная папка в корне проекта
    temp_dir = Path("temp_files")
    temp_dir.mkdir(exist_ok=True)
    local_path = temp_dir / file_name

    await bot.download_file(file_path, local_path)
    
    text = ""
    try:
        lower_name = file_name.lower()
        if lower_name.endswith('.docx'):
            doc = docx.Document(local_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            
        elif lower_name.endswith('.pdf'):
            reader = PdfReader(local_path)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        
        elif lower_name.endswith('.txt'):
            with open(local_path, 'r', encoding='utf-8') as f:
                text = f.read()
                
    except Exception as e:
        logger.error(f"File read error: {e}")
        text = "ERROR_READING_FILE"
    finally:
        if local_path.exists():
            os.remove(local_path)
            
    return text

# --- БИЗНЕС-ЛОГИКА ---

async def process_editor_pipeline(message: Message, original_text: str):
    if not original_text or len(original_text.strip()) < 5:
        await message.answer("Файл пустой или текста слишком мало.")
        return

    await message.answer("🧹 <b>Этап 1:</b> Обезличивание и проверка орфографии...")

    # Шаг 1: Корректор
    corrected_text, model1, _ = await ask_brain(SYSTEM_CORRECTOR, original_text)

    await message.answer("✨ <b>Этап 2:</b> Улучшение стиля...")

    # Шаг 2: Стилист
    stylist_input = f"ИСПРАВЛЕННЫЙ ТЕКСТ:\n{corrected_text}"
    json_response, model2, source = await ask_brain(SYSTEM_STYLIST, stylist_input)

    try:
        start = json_response.find('{')
        end = json_response.rfind('}')
        data = json.loads(json_response[start:end+1])
        
        critique = data.get('critique', 'Без комментариев')
        final_ver = data.get('final_text', corrected_text)
    except:
        critique = "Модель вернула сырой текст"
        final_ver = json_response

    report = (
        f"🧐 <b>Что поправили:</b>\n<i>{critique}</i>\n\n"
        f"📄 <b>РЕЗУЛЬТАТ:</b>\n"
        f"<code>{final_ver}</code>"
    )
    
    await safe_reply(message, "✅ Документ готов!", report, f"{model1} + {model2}")

# --- ХЕНДЛЕРЫ ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я — <b>ZiFiles</b>.\n"
        "Пришли мне черновик текста или файл (DOCX, PDF).\n"
        "Я исправлю ошибки, уберу лишнее и приведу документ в порядок."
    )

@router.message(F.document)
async def handle_doc(message: Message):
    doc = message.document
    fname = doc.file_name
    
    if fname.lower().endswith(('.docx', '.pdf', '.txt')):
        await message.bot.send_chat_action(message.chat.id, "upload_document")
        text = await extract_text_from_file(message.bot, doc.file_id, fname)
        
        if text == "ERROR_READING_FILE":
            await message.answer("⚠️ Ошибка чтения файла.")
        else:
            await process_editor_pipeline(message, text)
    else:
        await message.answer("Я понимаю только .docx, .pdf и .txt")

@router.message(F.text)
async def handle_text(message: Message):
    await message.bot.send_chat_action(message.chat.id, "typing")
    await process_editor_pipeline(message, message.text)
