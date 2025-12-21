import os
import logging
import httpx
import google.generativeai as genai
from aiogram.types import Message
from aiogram.enums import ParseMode

# --- НАСТРОЙКА РЕЗЕРВА ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def ask_brain(system_prompt: str, user_text: str, model_hint: str = "auto") -> tuple[str, str, str]:
    """
    Универсальная функция запроса к интеллекту.
    Возвращает: (Текст ответа, Имя модели, Источник)
    """
    
    # 1. Приоритет: Настройка из Render (глобальная)
    target_model = os.getenv("MODEL_NAME", model_hint)
    
    gateway_url = os.getenv("GATEWAY_BASE_URL")
    gateway_key = os.getenv("GATEWAY_API_KEY")
    
    print(f"DEBUG: Asking Brain via Gateway. Model request: {target_model}", flush=True)

    # --- ПОПЫТКА 1: ШЛЮЗ (DALLAS) ---
    if gateway_url and gateway_key:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{gateway_url}/chat/completions",
                    headers={"Authorization": f"Bearer {gateway_key}"},
                    json={
                        "model": target_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_text}
                        ]
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    real_model = data.get("model", target_model)
                    return content, real_model, "📡 Gateway"
                else:
                    logging.error(f"Gateway Error: {resp.status_code} | {resp.text}")
        except Exception as e:
            logging.error(f"Gateway Network Error: {e}")

    # --- ПОПЫТКА 2: РЕЗЕРВ (GOOGLE DIRECT) ---
    print("DEBUG: Switching to Backup (Direct Google)", flush=True)
    try:
        # Пытаемся взять модель попроще для резерва
        model = genai.GenerativeModel("gemini-1.5-flash")
        full_prompt = f"{system_prompt}\n\nUSER INPUT:\n{user_text}"
        response = model.generate_content(full_prompt)
        return response.text, "gemini-1.5-flash", "🔌 Backup"
    except Exception as e:
        return f"❌ Полный отказ систем. Ошибка: {e}", "Dead", "None"

async def safe_reply(message: Message, header: str, content: str, model_info: str):
    """
    Универсальная отправка.
    - Режет длинный текст (>4096).
    - Чистит плохие теги (<br>, <user>).
    - Пробует Markdown -> HTML -> Plain Text.
    """
    
    # 1. Очистка от мусора, который ломает Телеграм
    # Меняем угловые скобки на безопасные, чтобы не считались тегами
    # Но оставляем базовое форматирование Markdown, если оно есть
    safe_content = content.replace("<br>", "\n").replace("<br/>", "\n")
    
    # Собираем футер
    footer = f"\n\n⚙️ _{model_info}_"
    full_text = f"{header}\n\n{safe_content}{footer}"
    
    # 2. Нарезка на куски (Chunking)
    chunks = []
    while full_text:
        if len(full_text) <= 4096:
            chunks.append(full_text)
            break
        
        # Режем по переносу строки ближе к концу лимита
        part = full_text[:4096]
        cut_index = part.rfind('\n')
        if cut_index == -1: cut_index = 4096
        
        chunks.append(full_text[:cut_index])
        full_text = full_text[cut_index:]

    # 3. Отправка каждого куска
    for chunk in chunks:
        # Попытка А: Markdown
        try:
            await message.answer(chunk, parse_mode=ParseMode.MARKDOWN)
            continue 
        except Exception as e:
            logging.warning(f"MD send failed: {e}")
        
        # Попытка Б: HTML (надо экранировать < и >)
        try:
            html_chunk = chunk.replace("<", "&lt;").replace(">", "&gt;")
            # Восстанавливаем жирность (примитивно, но лучше чем ничего)
            html_chunk = html_chunk.replace("**", "<b>").replace("__", "<i>")
            await message.answer(html_chunk, parse_mode=ParseMode.HTML)
            continue
        except Exception as e:
            logging.warning(f"HTML send failed: {e}")
            
        # Попытка В: Plain Text (Сдаемся)
        clean_chunk = chunk.replace("*", "").replace("_", "").replace("`", "")
        await message.answer(clean_chunk, parse_mode=None)
