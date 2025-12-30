import os
import logging
import io
import docx
import difflib
import aiohttp # Для отправки на сайт

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile

from utils.ai_engine import ask_brain, safe_reply

router = Router()
logger = logging.getLogger(__name__)

# --- КОНФИГ САЙТА ---
# Лучше брать из os.getenv, но для наглядности можно и тут (если осторожно)
UPLOAD_URL = os.getenv("REPORT_UPLOAD_URL")
UPLOAD_KEY = os.getenv("REPORT_UPLOAD_KEY")

if not UPLOAD_URL or not UPLOAD_KEY:
    logger.warning("⚠️ Не заданы настройки загрузки на сайт (REPORT_UPLOAD_URL/KEY). Отчеты работать не будут.")

class FileStates(StatesGroup):
    waiting_for_choice = State()

PROMPT_CLEAN = """
Ты — специалист по DLP. Твоя задача — жестко обезличить документ и поправить стиль.
1. 🛡️ УДАЛЕНИЕ ДАННЫХ: ФИО->[ФИО], Компании->[Компания], Суммы->[Сумма], Адреса->[Адрес], Даты->[Дата].
2. СТИЛЬ: Исправь канцеляризмы, сделай текст легким.
Верни ТОЛЬКО готовый текст.
"""

PROMPT_KEEP = """
Ты — редактор. Улучши стиль, НЕ МЕНЯЯ фактические данные.
1. СТИЛЬ: Исправь орфографию, убери воду.
2. ЗАПРЕТЫ: НЕ меняй ФИО, цифры, названия.
Верни ТОЛЬКО готовый текст.
"""

# --- ГЕНЕРАТОР DIFF ---
def generate_html_diff(original: str, modified: str) -> str:
    d = difflib.HtmlDiff()
    html_content = d.make_file(
        original.splitlines(), 
        modified.splitlines(), 
        fromdesc='Оригинал', 
        todesc='Результат AI',
        context=True, 
        numlines=2
    )
    # Добавляем немного стилей для красоты
    html_content = html_content.replace('<head>', '''<head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: sans-serif; padding: 20px; }
            table.diff { width: 100%; font-size: 14px; }
            .diff_header { background-color: #e0e0e0; }
            .diff_next { display: none; }
        </style>
    ''')
    return html_content

# --- ЗАГРУЗЧИК НА САЙТ ---
async def upload_html_to_site(html_content: str) -> str:
    async with aiohttp.ClientSession() as session:
        headers = {"X-Auth-Key": UPLOAD_KEY}
        try:
            async with session.post(UPLOAD_URL, data=html_content.encode('utf-8'), headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("url")
                else:
                    logger.error(f"Upload failed: {resp.status} {await resp.text()}")
                    return None
        except Exception as e:
            logger.error(f"Upload connection error: {e}")
            return None

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>Привет! Я — ZiFiles.</b>\n"
        "Пришли .docx/.pdf/.txt\n"
        "Я исправлю текст и дам <b>ссылку на визуальное сравнение</b>.",
        parse_mode="HTML"
    )

@router.message(F.document)
async def handle_document(message: types.Message, state: FSMContext):
    file_id = message.document.file_id
    file_name = message.document.file_name
    file_ext = os.path.splitext(file_name)[1].lower()

    if file_ext not in ['.docx', '.pdf', '.txt']:
        await message.reply("⚠️ Только .docx, .pdf и .txt")
        return

    await state.update_data(file_id=file_id, file_ext=file_ext)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛡 Обезличить", callback_data="mode_clean"),
         InlineKeyboardButton(text="✍️ Только стиль", callback_data="mode_keep")]
    ])
    await message.answer(f"📄 <b>{file_name}</b>. Выбери режим:", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(FileStates.waiting_for_choice)

@router.callback_query(FileStates.waiting_for_choice)
async def process_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    mode = callback.data
    prompt = PROMPT_CLEAN if mode == "mode_clean" else PROMPT_KEEP
    label = "🛡 DLP" if mode == "mode_clean" else "✍️ Редактор"

    await callback.message.edit_text(f"{label}: Обрабатываю и генерирую ссылку...", parse_mode="HTML")
    
    try:
        # Скачиваем файл
        bot = callback.message.bot
        file = await bot.get_file(data["file_id"])
        file_content = io.BytesIO()
        await bot.download_file(file.file_path, file_content)
        
        original_text = ""
        # (Упрощенная логика чтения для краткости, вставь полный блок из прошлого кода если нужно)
        if data["file_ext"] == '.docx':
            doc = docx.Document(file_content)
            original_text = '\n'.join([p.text for p in doc.paragraphs])
        elif data["file_ext"] == '.txt':
            original_text = file_content.read().decode('utf-8')
        
        # Обрезаем
        short_text = original_text[:15000]

        # AI
        modified_text, model, source = await ask_brain(prompt, short_text)

        # Отправляем текст в чат
        await safe_reply(callback.message, "✅ <b>Результат:</b>", modified_text, model)

        # Генерируем HTML
        html_report = generate_html_diff(short_text, modified_text)

        # Загружаем на сайт
        report_url = await upload_html_to_site(html_report)

        if report_url:
            await callback.message.answer(
                f"📊 <b>Подробный отчет изменений:</b>\n"
                f"🔗 <a href='{report_url}'>Нажмите, чтобы открыть в браузере</a>\n\n"
                f"<i>⚠️ Ссылка активна 24 часа.</i>",
                parse_mode="HTML",
                disable_web_page_preview=False 
            )
        else:
            # Если сайт лежит, кидаем файлом как раньше
            input_file = BufferedInputFile(html_report.encode('utf-8'), filename="report.html")
            await callback.message.answer_document(input_file, caption="⚠️ Не удалось загрузить на сайт, держи файлом.")

    except Exception as e:
        logger.error(f"Error: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    
    finally:
        await state.clear()
