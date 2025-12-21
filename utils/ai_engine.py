# utils/ai_engine.py
import os
import logging
import httpx
from aiogram.types import Message
from aiogram.enums import ParseMode

logger = logging.getLogger(__name__)

# ВАЖНО: Должен быть полный путь к эндпоинту
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
            # Убеждаемся, что URL заканчивается на /chat/completions
            url = GATEWAY_URL if GATEWAY_URL.endswith("/completions") else f"{GATEWAY_URL.rstrip('/')}/chat/completions"
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            content = data['choices'][0]['message']['content']
            model_info = data.get('model', model)
            return content, model_info, "Gateway"
    except Exception as e:
        logger.error(f"Gateway error: {e}")
        return f"Ошибка Шлюза: {str(e)}", "error", "none"

# Функция safe_reply остается без изменений, если ты её уже обновил (с аргументом reply_markup=None)
