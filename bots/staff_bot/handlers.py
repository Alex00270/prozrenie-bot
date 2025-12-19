import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Router, F, Bot
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

router = Router()

# --- 1. НАСТРОЙКИ ---

# Ищем ключ (на сервере или локально)
if os.path.exists('/etc/secrets/credentials.json'):
    JSON_KEYFILE = '/etc/secrets/credentials.json'
else:
    JSON_KEYFILE = 'credentials.json'

SPREADSHEET_NAME = 'Кассовая книга Декабрь 2025' # <--- Проверьте название таблицы!

# Список ваших объектов (добавляйте новые сюда)
OBJECTS = ["🎟 Билеты", "☕️ Кафе Шлюз", "🍔 Кафе 2", "🍕 Кафе 3"]

# Сотрудники (можно тоже менять)
STAFF_NAMES = ["Бабаев", "Смирнов", "Гоголев"]

# Цены для билетов (чтобы бот сам считал)
PRICE_ADULT = 160
PRICE_DISCOUNT = 100

# --- 2. РАБОТА С ТАБЛИЦЕЙ ---
def add_to_sheet(row_data):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEYFILE, scope)
        client = gspread.authorize(creds)
        
        # Открываем таблицу и первый лист
        sheet = client.open(SPREADSHEET_NAME).sheet1
        sheet.append_row(row_data)
        return True
    except Exception as e:
        print(f"GOOGLE SHEET ERROR: {e}")
        return False

# --- 3. СЦЕНАРИЙ ДИАЛОГА (FSM) ---
class Report(StatesGroup):
    choosing_object = State()   # Выбор точки
    choosing_name = State()     # Кто сдает
    
    # Ветка для Билетов
    tickets_adult = State()
    tickets_discount = State()
    
    # Ветка для Кафе (просто выручка)
    cafe_revenue = State()
    
    # Финал
    comment = State()

# --- 4. ОБРАБОТЧИКИ (HANDLERS) ---

# Шаг 1: Старт и выбор объекта
@router.message(Command("start", "report"))
async def cmd_start(message: Message, state: FSMContext):
    # Генерация клавиатуры из списка OBJECTS
    # Делаем по 2 кнопки в ряд
    buttons = []
    row = []
    for obj in OBJECTS:
        row.append(KeyboardButton(text=obj))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row: buttons.append(row) # Добавляем остаток
    
    kb = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    
    await message.answer("👋 Привет! Выберите объект для отчета:", reply_markup=kb)
    await state.set_state(Report.choosing_object)

# Шаг 2: Выбор имени
@router.message(Report.choosing_object)
async def step_object(message: Message, state: FSMContext):
    if message.text not in OBJECTS:
        await message.answer("Пожалуйста, выберите объект кнопкой.")
        return
    
    await state.update_data(selected_object=message.text)
    
    # Клавиатура с именами
    buttons = [[KeyboardButton(text=name)] for name in STAFF_NAMES]
    kb = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    
    await message.answer(f"Отчет по: <b>{message.text}</b>.\nКто сдает смену?", reply_markup=kb)
    await state.set_state(Report.choosing_name)

# Шаг 3: Развилка (Билеты или Кафе?)
@router.message(Report.choosing_name)
async def step_name(message: Message, state: FSMContext):
    if message.text not in STAFF_NAMES:
        await message.answer("Выберите имя из списка.")
        return

    await state.update_data(staff_name=message.text)
    data = await state.get_data()
    obj = data['selected_object']

    # ЛОГИКА РАЗВИЛКИ
    if "Билеты" in obj:
        # Если это билеты - спрашиваем детали
        await message.answer("Сколько **ВЗРОСЛЫХ** билетов?", reply_markup=ReplyKeyboardRemove())
        await state.set_state(Report.tickets_adult)
    else:
        # Если это Кафе - сразу спрашиваем выручку
        await message.answer(f"Введите **ВЫРУЧКУ** для {obj} (одним числом):", reply_markup=ReplyKeyboardRemove())
        await state.set_state(Report.cafe_revenue)

# --- ВЕТКА БИЛЕТОВ ---
@router.message(Report.tickets_adult)
async def step_tickets_adult(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число.")
        return
    await state.update_data(adults=int(message.text))
    await message.answer("Сколько **ЛЬГОТНЫХ** билетов?")
    await state.set_state(Report.tickets_discount)

@router.message(Report.tickets_discount)
async def step_tickets_discount(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число.")
        return
    
    discount = int(message.text)
    data = await state.get_data()
    adults = data['adults']
    
    # Считаем сами
    revenue = (adults * PRICE_ADULT) + (discount * PRICE_DISCOUNT)
    
    await state.update_data(discount=discount, revenue=revenue)
    await message.answer(f"Авто-расчет: {revenue} руб.\nЕсть комментарий? (или напиши 'нет')")
    await state.set_state(Report.comment)

# --- ВЕТКА КАФЕ ---
@router.message(Report.cafe_revenue)
async def step_cafe_revenue(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число (выручку).")
        return
    
    # Для кафе ставим билеты по нулям, пишем только деньги
    await state.update_data(revenue=int(message.text), adults=0, discount=0)
    await message.answer("Комментарий? (расходы, проблемы, или 'нет')")
    await state.set_state(Report.comment)

# --- ФИНАЛ ---
@router.message(Report.comment)
async def step_finish(message: Message, state: FSMContext):
    comment = message.text
    data = await state.get_data()
    today = datetime.now().strftime("%d.%m.%Y")
    
    # Формируем строку для Google Sheets
    # [Дата, Объект, Сотрудник, Взр, Льгот, Выручка, Коммент]
    row = [
        today,
        data['selected_object'],
        data['staff_name'],
        data['adults'],
        data['discount'],
        data['revenue'],
        comment
    ]
    
    msg = await message.answer("⏳ Сохраняю...")
    
    if add_to_sheet(row):
        await msg.edit_text(
            f"✅ **ПРИНЯТО!**\n"
            f"📍 {data['selected_object']}\n"
            f"💰 Выручка: {data['revenue']} руб.\n"
            f"👤 {data['staff_name']}"
        )
    else:
        await msg.edit_text("❌ Ошибка связи с Google Таблицей.")
    
    await state.clear()
