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

# --- ВАЖНЫЕ НАСТРОЙКИ ---
# 1. Файл ключа должен лежать рядом с main.py
JSON_KEYFILE = 'credentials.json' 

# 2. Имя таблицы (ТОЧНО как в Google, слева сверху)
# Если вы не меняли, она может называться "Новая таблица" или как вы написали.
# Впишите сюда точное название:
SPREADSHEET_NAME = 'Кассовая книга Декабрь 2025' 

# Цены из журнала (примерные, потом поправите)
PRICE_ADULT_VAL = 160 # 10 билетов = 1600
PRICE_DISCOUNT_VAL = 100 

# --- ФУНКЦИЯ ЗАПИСИ ---
def add_to_sheet(row_data):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEYFILE, scope)
        client = gspread.authorize(creds)
        # Открываем первую вкладку (Sheet1)
        sheet = client.open(SPREADSHEET_NAME).sheet1
        sheet.append_row(row_data)
        return True
    except Exception as e:
        print(f"CRITICAL GOOGLE ERROR: {e}")
        return False

# --- FSM (Диалог) ---
class KassaReport(StatesGroup):
    waiting_for_name = State()
    waiting_for_adults = State()
    waiting_for_discount = State()
    waiting_for_revenue = State()

# --- ОБРАБОТЧИКИ ---

@router.message(Command("report"))
async def cmd_report(message: Message, state: FSMContext):
    # Клавиатура с именами из журнала
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Бабаев"), KeyboardButton(text="Смирнов")],
        [KeyboardButton(text="Гоголев")]
    ], resize_keyboard=True, one_time_keyboard=True)
    
    await message.answer("👋 Привет! Принимаю смену. Кто вы?", reply_markup=kb)
    await state.set_state(KassaReport.waiting_for_name)

@router.message(KassaReport.waiting_for_name)
async def step_adults(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Сколько **ВЗРОСЛЫХ** билетов?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(KassaReport.waiting_for_adults)

@router.message(KassaReport.waiting_for_adults)
async def step_discount(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Нужно число.")
        return
    await state.update_data(adults=message.text)
    await message.answer("Сколько **ЛЬГОТНЫХ** билетов? (если нет - 0)")
    await state.set_state(KassaReport.waiting_for_discount)

@router.message(KassaReport.waiting_for_discount)
async def step_revenue(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Нужно число.")
        return
    await state.update_data(discount=message.text)
    await message.answer("Напиши **ИТОГОВУЮ ВЫРУЧКУ** за день (как в тетради):")
    await state.set_state(KassaReport.waiting_for_revenue)

@router.message(KassaReport.waiting_for_revenue)
async def finish(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Выручка должна быть числом.")
        return
        
    data = await state.get_data()
    revenue = message.text
    today = datetime.now().strftime("%d.%m.%Y")
    
    # Формируем строку как в журнале
    row = [
        today,              # Дата
        data['name'],       # ФИО
        data['adults'],     # Взрослых
        data['discount'],   # Льготных
        revenue,            # Выручка
        "",                 # Касса (пока пусто)
        "Через бота"        # Примечание
    ]
    
    msg = await message.answer("⏳ Записываю в Google Таблицу...")
    
    if add_to_sheet(row):
        await msg.edit_text(f"✅ **Записано!**\nСотрудник: {data['name']}\nВыручка: {revenue} р.")
    else:
        await msg.edit_text("❌ Ошибка доступа к таблице. Проверь название и права.")
        
    await state.clear()
