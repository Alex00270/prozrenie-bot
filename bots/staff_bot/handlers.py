import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Router, F, Bot
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
# Импортируем наш мозг для вопросов "не по теме"
from utils.ai_engine import ask_brain, safe_reply

router = Router()

# --- 1. НАСТРОЙКИ ТАБЛИЦЫ ---
SPREADSHEET_ID = '11jjRhELvWcrFV9TKHDV47cvDAkmR5hMDoLTn8C4G_kA' 

if os.path.exists('/etc/secrets/credentials.json'):
    JSON_KEYFILE = '/etc/secrets/credentials.json'
else:
    JSON_KEYFILE = 'credentials.json'

# Списки меню
OBJECTS = ["🎟 Билеты", "☕️ Кафе Шлюз", "🍔 Кафе 2", "🍕 Кафе 3"]
STAFF_NAMES = ["Бабаев", "Смирнов", "Гоголев"]

# Цены
PRICE_ADULT = 160
PRICE_DISCOUNT = 100

# --- 2. РАБОТА С GOOGLE SHEETS ---
def add_to_sheet(row_data):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        if not os.path.exists(JSON_KEYFILE):
            print(f"DEBUG ERROR: Файл {JSON_KEYFILE} не найден!", flush=True)
            return False

        with open(JSON_KEYFILE, 'r') as f:
            creds_dict = json.load(f)
        
        if 'private_key' in creds_dict:
            creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')

        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.get_worksheet(0) 
        
        sheet.append_row(row_data)
        return True
    except Exception as e:
        print(f"🚨 GOOGLE SHEET ERROR: {e}", flush=True)
        return False

# --- 3. СЦЕНАРИЙ ОТЧЕТА (FSM) ---
class Report(StatesGroup):
    choosing_object = State()
    choosing_name = State()
    tickets_adult = State()
    tickets_discount = State()
    cafe_revenue = State()
    comment = State()

# --- 4. ХЕНДЛЕРЫ ОТЧЕТНОСТИ (БИЗНЕС-ЛОГИКА) ---

@router.message(Command("start", "report"))
async def cmd_start(message: Message, state: FSMContext):
    # Генерация кнопок
    buttons = []
    row = []
    for obj in OBJECTS:
        row.append(KeyboardButton(text=obj))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    
    kb = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("👋 Привет! Выберите объект для отчета:", reply_markup=kb)
    await state.set_state(Report.choosing_object)

@router.message(Report.choosing_object)
async def step_object(message: Message, state: FSMContext):
    if message.text not in OBJECTS:
        await message.answer("Пожалуйста, нажмите на кнопку.")
        return
    await state.update_data(selected_object=message.text)
    
    # Кнопки сотрудников
    buttons = [[KeyboardButton(text=name)] for name in STAFF_NAMES]
    kb = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)
    
    await message.answer(f"Объект: {message.text}.\nКто сдает смену?", reply_markup=kb)
    await state.set_state(Report.choosing_name)

@router.message(Report.choosing_name)
async def step_name(message: Message, state: FSMContext):
    if message.text not in STAFF_NAMES:
        await message.answer("Выберите имя из списка.")
        return
    await state.update_data(staff_name=message.text)
    
    data = await state.get_data()
    obj = data['selected_object']
    
    if "Билеты" in obj:
        await message.answer("Сколько **ВЗРОСЛЫХ** билетов?", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
        await state.set_state(Report.tickets_adult)
    else:
        await message.answer(f"Какая ВЫРУЧКА на {obj}?", reply_markup=ReplyKeyboardRemove())
        await state.set_state(Report.cafe_revenue)

@router.message(Report.tickets_adult)
async def step_tickets_adult(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пишите число.")
        return
    await state.update_data(adults=int(message.text))
    await message.answer("Сколько **ЛЬГОТНЫХ** билетов?")
    await state.set_state(Report.tickets_discount)

@router.message(Report.tickets_discount)
async def step_tickets_discount(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пишите число.")
        return
    discount = int(message.text)
    data = await state.get_data()
    revenue = (data['adults'] * PRICE_ADULT) + (discount * PRICE_DISCOUNT)
    
    await state.update_data(discount=discount, revenue=revenue)
    await message.answer(f"Авто-расчет: {revenue} руб.\nЕсть комментарий? (или напиши 'нет')")
    await state.set_state(Report.comment)

@router.message(Report.cafe_revenue)
async def step_cafe_revenue(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пишите число (выручку).")
        return
    await state.update_data(revenue=int(message.text), adults=0, discount=0)
    await message.answer("Есть комментарий? (или напиши 'нет')")
    await state.set_state(Report.comment)

@router.message(Report.comment)
async def step_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    today = datetime.now().strftime("%d.%m.%Y")
    comment_text = "" if message.text.lower() == "нет" else message.text
    
    row = [
        today,
        data['selected_object'],
        data['staff_name'],
        data['adults'],
        data['discount'],
        data['revenue'],
        comment_text
    ]
    
    msg = await message.answer("⏳ Пишу в таблицу...")
    if add_to_sheet(row):
        await msg.edit_text(f"✅ Записано!\n{data['selected_object']} | {data['revenue']} р.")
    else:
        await msg.edit_text("❌ Ошибка Google Таблицы.")
    
    await state.clear()

# --- 5. ЛОВУШКА ДЛЯ ВСЕГО ОСТАЛЬНОГО (AI) ---
# Если пользователь НЕ нажимает кнопки и НЕ в процессе отчета,
# он попадает сюда. Здесь мы спрашиваем AI.
@router.message()
async def handle_general_questions(message: Message):
    # Показываем, что думаем
    msg = await message.answer("📁 Ищу информацию...")
    
    # Системный промпт для HR-бота
    sys_prompt = (
        "Ты полезный офисный помощник (HR и Администратор). "
        "Твоя задача - помогать сотрудникам с вопросами по работе, расписанию или инструкциям."
    )
    
    # Спрашиваем единый мозг
    text, model, src = await ask_brain(sys_prompt, message.text)
    
    await msg.delete()
    # Безопасная отправка
    await safe_reply(message, "📄 **Справка:**", text, f"{model} | {src}")
