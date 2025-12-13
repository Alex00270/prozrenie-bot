import asyncio
import logging
import os
import sys
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# ВЕБ-СЕРВЕР (ОБЯЗАТЕЛЬНО ДЛЯ RENDER)
from aiohttp import web
import google.generativeai as genai

# --- CONFIG ---
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
TOKEN = os.getenv("TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 8080))

if not TOKEN or not GEMINI_API_KEY:
    sys.exit(1)

try:
    genai.configure(api_key=GEMINI_API_KEY)
except:
    sys.exit(1)

# --- MODEL SELECTION ---
CURRENT_MODEL_NAME = "models/gemini-1.5-flash"
def select_best_model():
    global CURRENT_MODEL_NAME
    try:
        all = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        gemma = [m for m in all if "gemma" in m.lower() and "it" in m.lower()]
        if gemma:
            gemma.sort(key=lambda x: int(re.search(r'(\d+)b', x.lower()).group(1)) if re.search(r'(\d+)b', x.lower()) else 0, reverse=True)
            CURRENT_MODEL_NAME = gemma[0]
            print(f"🏆 FOUND: {CURRENT_MODEL_NAME}", flush=True)
    except:
        pass
select_best_model()

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """
ТЫ — ЭКСПЕРТ ПО ПОЗИЦИОНИРОВАНИЮ И ПРОДАЖАМ (Direct Response Marketing).
Твоя задача — проанализировать ответы пользователя и показать ему, где он теряет деньги.

ФОРМАТ ОТВЕТА (Russian Markdown):
## 🩺 Диагноз
(Честно и прямо. Почему текущее позиционирование слабое.)
## 💎 Где деньги?
(Гипотеза: за что именно этому эксперту готовы платить дорого.)
## 🚀 План
1. **Кто купит:** (Узкий сегмент)
2. **Триггер:** (Боль)
3. **Оффер:** (Суть в одном предложении)
## 💀 Триггер консультации
(Почему без личного разбора он не справится.)
"""

# --- FSM STATES ---
class BrandAnalysis(StatesGroup):
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q5 = State()
    q6 = State()

router = Router()

@router.message(CommandStart())
async def start(msg: Message, state: FSMContext):
    await state.clear()
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔥 Начать разбор")]], resize_keyboard=True, one_time_keyboard=True)
    await msg.answer(f"🧠 <b>AI-Стратег</b> ({CURRENT_MODEL_NAME.split('/')[-1]})\nГотов к честному разбору?", reply_markup=kb)

@router.message(F.text == "🔥 Начать разбор")
async def s1(msg: Message, state: FSMContext):
    await msg.answer("1. Кого ты ХОЧЕШЬ видеть клиентом, но они пока не покупают?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(BrandAnalysis.q1)

@router.message(BrandAnalysis.q1)
async def s2(msg: Message, state: FSMContext):
    await state.update_data(a1=msg.text)
    await msg.answer("2. За решение какой проблемы они готовы платить МНОГО?")
    await state.set_state(BrandAnalysis.q2)

@router.message(BrandAnalysis.q2)
async def s3(msg: Message, state: FSMContext):
    await state.update_data(a2=msg.text)
    await msg.answer("3. Кого они выбирают вместо тебя? (Конкуренты или 'сделаю сам')")
    await state.set_state(BrandAnalysis.q3)

@router.message(BrandAnalysis.q3)
async def s4(msg: Message, state: FSMContext):
    await state.update_data(a3=msg.text)
    await msg.answer("4. В чем твоя 'Магия'? (Факты, кейсы, метод)")
    await state.set_state(BrandAnalysis.q4)

@router.message(BrandAnalysis.q4)
async def s5(msg: Message, state: FSMContext):
    await state.update_data(a4=msg.text)
    await msg.answer("5. Тест бабушки: Объясни продукт одной простой фразой.")
    await state.set_state(BrandAnalysis.q5)

@router.message(BrandAnalysis.q5)
async def s6(msg: Message, state: FSMContext):
    await state.update_data(a5=msg.text)
    await msg.answer("6. Что хочешь продать? (Курс, наставничество, услугу)")
    await state.set_state(BrandAnalysis.q6)

@router.message(BrandAnalysis.q6)
async def finish(msg: Message, state: FSMContext):
    await state.update_data(a6=msg.text)
    data = await state.get_data()
    wait = await msg.answer("⚡ Анализирую...")
    
    txt = f"Audience: {data.get('a1')}\nPain: {data.get('a2')}\nComp: {data.get('a3')}\nMagic: {data.get('a4')}\nSimple: {data.get('a5')}\nGoal: {data.get('a6')}"
    
    try:
        model = genai.GenerativeModel(CURRENT_MODEL_NAME)
        res = await model.generate_content_async(f"{SYSTEM_PROMPT}\n\nINPUT:\n{txt}")
        await msg.answer(res.text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await msg.answer(f"Ошибка: {e}")
    finally:
        await wait.delete()
        await state.clear()

# --- SERVER ---
async def health(r): return web.Response(text="Alive")

async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Server setup
    app = web.Application()
    app.router.add_get('/', health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
