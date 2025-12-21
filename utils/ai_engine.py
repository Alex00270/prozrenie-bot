import os
import logging
import httpx
from aiogram.types import Message
from aiogram.enums import ParseMode

logger = logging.getLogger(__name__)

# Полный путь к эндпоинту Шлюза
GATEWAY_URL = os.getenv("GATEWAY_BASE_URL", "http://172.86.90.213:3000/v1/chat/completions")

async def ask_brain(sys_prompt: str, user_text: str, model: str = "auto"):
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
            # Исправляем URL, если он обрезан
            url = GATEWAY_URL if "/chat/completions" in GATEWAY_URL else f"{GATEWAY_URL.rstrip('/')}/chat/completions"
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            content = data['choices'][0]['message']['content']
            model_info = data.get('model', model)
            return content, model_info, "Gateway"
    except Exception as e:
        logger.error(f"Gateway error: {e}")
        return f"Ошибка Шлюза: {str(e)}", "error", "none"

async def safe_reply(message: Message, header: str, content: str, model_info: str, reply_markup=None):
    """
    Универсальная отправка с нарезкой текста и поддержкой кнопок.
    """
    safe_content = content.replace("<br>", "\n").replace("<br/>", "\n")
    footer = f"\n\n⚙️ _{model_info}_"
    full_text = f"{header}\n\n{safe_content}{footer}"
    
    # Нарезка
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

    # Отправка
    for i, chunk in enumerate(chunks):
        current_markup = reply_markup if i == len(chunks) - 1 else None
        try:
            await message.answer(chunk, parse_mode=ParseMode.MARKDOWN, reply_markup=current_markup)
        except Exception:
            try:
                html_chunk = chunk.replace("<", "&lt;").replace(">", "&gt;").replace("**", "<b>").replace("__", "<i>")
                await message.answer(html_chunk, parse_mode=ParseMode.HTML, reply_markup=current_markup)
            except Exception:
                await message.answer(chunk.replace("*", ""), reply_markup=current_markup)
