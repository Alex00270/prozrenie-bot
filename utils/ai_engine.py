import os
import logging
import httpx
import json
from aiogram.types import Message
from aiogram.enums import ParseMode

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GATEWAY_URL = os.getenv("GATEWAY_BASE_URL", "http://172.86.90.213:3000/v1/chat/completions")

async def ask_brain(sys_prompt: str, user_text: str, model: str = "auto"):
    """
    Запрос к Шлюзу (Gateway).
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_text}
        ],
        "temperature": 0.7
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(GATEWAY_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            
            content = data['choices'][0]['message']['content']
            model_info = data.get('model', model)
            source = "Gateway"
            return content, model_info, source
    except Exception as e:
        logger.error(f"Gateway error: {e}")
        return f"Ошибка Шлюза: {str(e)}", "error", "none"

async def safe_reply(message: Message, header: str, content: str, model_info: str, reply_markup=None):
    """
    Универсальная отправка.
    - Добавлен reply_markup для поддержки кнопок Незабудки.
    - Режет длинный текст (>4096).
    - Чистит плохие теги.
    - Пробует Markdown -> HTML -> Plain Text.
    """
    
    # 1. Очистка от мусора
    safe_content = content.replace("<br>", "\n").replace("<br/>", "\n")
    
    # Собираем футер
    footer = f"\n\n⚙️ _{model_info}_"
    full_text = f"{header}\n\n{safe_content}{footer}"
    
    # 2. Нарезка на куски (Chunking)
    chunks = []
    temp_text = full_text
    while temp_text:
        if len(temp_text) <= 4096:
            chunks.append(temp_text)
            break
        
        part = temp_text[:4096]
        cut_index = part.rfind('\n')
        if cut_index == -1: cut_index = 4096
        
        chunks.append(temp_text[:cut_index])
        temp_text = temp_text[cut_index:]

    # 3. Отправка каждого куска
    for i, chunk in enumerate(chunks):
        # Кнопки прикрепляем ТОЛЬКО к последнему куску текста
        current_markup = reply_markup if i == len(chunks) - 1 else None
        
        # Попытка А: Markdown
        try:
            await message.answer(chunk, parse_mode=ParseMode.MARKDOWN, reply_markup=current_markup)
            continue 
        except Exception as e:
            logging.warning(f"MD send failed: {e}")
        
        # Попытка Б: HTML
        try:
            # Экранируем спецсимволы, чтобы не ломать HTML
            html_chunk = chunk.replace("<", "&lt;").replace(">", "&gt;")
            # Восстанавливаем жирность и курсив из MD-разметки
            html_chunk = html_chunk.replace("**", "<b>").replace("__", "<i>")
            await message.answer(html_chunk, parse_mode=ParseMode.HTML, reply_markup=current_markup)
            continue
        except Exception as e:
            logging.warning(f"HTML send failed: {e}")
            
        # Попытка В: Plain Text (Сдаемся)
        clean_chunk = chunk.replace("*", "").replace("_", "").replace("`", "")
        await message.answer(clean_chunk, parse_mode=None, reply_markup=current_markup)
