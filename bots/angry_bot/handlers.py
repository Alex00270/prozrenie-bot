import os
import logging
import httpx
import google.generativeai as genai
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode

router = Router()

# --- 1. РЕЗЕРВ (Google Direct) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- 2. УМНАЯ ФУНКЦИЯ (Gateway + Backup + Safe Send) ---
async def roast_and_send(message: Message, user_text: str):
    gateway_url = os.getenv("GATEWAY_BASE_URL")
    gateway_key = os.getenv("GATEWAY_API_KEY")
    target_model = os.getenv("MODEL_NAME", "auto")
    
    # Промпт Скептика
    system_prompt = (
        "Ты циничный, саркастичный критик. Твоя задача — найти слабые места в идее. "
        "Не стесняйся в выражениях, используй черный юмор. Разнеси идею в пух и прах. "
        "Но будь краток."
    )

    content = ""
    real_model = "Unknown"
    source = "Unknown"

    # А. Попытка через Шлюз
    if gateway_url and gateway_key:
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
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
                    source = "📡 Gateway"
        except Exception as e:
            logging.error(f"Skeptic Gateway failed: {e}")

    # Б. Резерв (Backup)
    if not content:
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            # Для Скептика добавляем промпт прямо в текст, т.к. flash простая
            full_prompt = f"{system_prompt}\n\nВОТ ИДЕЯ ЖЕРТВЫ:\n{user_text}"
            response = model.generate_content(full_prompt)
            content = response.text
            real_model = "gemini-1.5-flash"
            source = "🔌 Backup"
        except Exception as e:
            content = f"Ой, я сломался от тупости этой идеи. (Ошибка: {e})"
            source = "Dead"

    # В. Безопасная отправка
    header = f"💀 **Душнила:** `{real_model}` | **Канал:** `{source}`"
    full_text = f"{content}\n\n{header}"

    try:
        # Markdown
        await message.answer(full_text, parse_mode=ParseMode.MARKDOWN)
    except:
        try:
            # HTML
            safe_content = content.replace("<", "&lt;").replace(">", "&gt;")
            safe_header = f"💀 <b>Душнила:</b> {real_model} | <b>Канал:</b> {source}"
            await message.answer(f"{safe_content}\n\n{safe_header}", parse_mode=ParseMode.HTML)
        except:
            # Plain text
            clean_text = full_text.replace("*", "").replace("`", "")
            await message.answer(clean_text, parse_mode=None)

# --- 3. ХЕНДЛЕРЫ ---

@router.message(CommandStart())
async def cmd_start(message: Message):
    # Читаем из Render. Если переменной нет - пишем "Auto"
    target = os.getenv("MODEL_NAME", "Auto-Mode")
    
    await message.answer(
        f"🤨 **Ну что, пришел за правдой?** Я MySkepticBot.\n"
        f"🧠 Цель: `{target}`\n\n" # <--- ТЕПЕРЬ ТУТ БУДЕТ ПРАВДА
        "Пиши свою 'гениальную' идею, я разнесу её."
    )

@router.message()
async def handle_text(message: Message):
    user_text = message.text
    msg = await message.answer("🤨 Ищу к чему доебаться...")
    
    # Запускаем генерацию
    await roast_and_send(message, user_text)
    
    # Удаляем сообщение "Ищу..."
    try:
        await msg.delete()
    except:
        pass
