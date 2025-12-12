# main.py
from aiogram import Bot, Dispatcher, Router, types
from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import html
import asyncio
import logging

from config import TOKEN

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# === Состояния диалога ===
class Positioning(StatesGroup):
    waiting_brand_name = State()
    waiting_current_description = State()
    waiting_client_life = State()
    waiting_category = State()
    waiting_wish = State()

# === Клавиатуры ===
def get_start_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пройти диагностику и получить позиционирование", callback_data="start_diagnostic")]
    ])
    return kb

def get_cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])

# === Старт ===
@router.message(F.text.in_({"/start", "старт", "привет"}))
async def cmd_start(message: Message):
    await message.answer(
        "<b>Прозрение</b>\n\n"
        "Я помогу тебе за 5 минут увидеть настоящее позиционирование твоего бренда.\n"
        "Никаких логотипов, пока — только смысл, роль и идея.\n\n"
        "Готов?",
        reply_markup=get_start_kb()
    )

@router.callback_query(F.data == "start_diagnostic")
async def start_diagnostic(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Шаг 1/5\n\n"
        "Как называется ваш бренд/проект/компания?\n"
        "(можно просто название или короткое описание)",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(Positioning.waiting_brand_name)
    await callback.answer()

# === Отмена в любой момент ===
@router.callback_query(F.data == "cancel")
async def cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Диагностика отменена. Когда будете готовы — /start", reply_markup=None)
    await callback.answer()

# === Собираем данные ===
@router.message(Positioning.waiting_brand_name)
async def get_brand_name(message: Message, state: FSMContext):
    await state.update_data(brand=message.text.strip())
    await message.answer(
        "Шаг 2/5\n\n"
        "Как сейчас клиенты/вы сами объясняете, чем вы занимаетесь?\n"
        "(чем честнее — тем точнее будет результат)",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(Positioning.waiting_current_description)

@router.message(Positioning.waiting_current_description)
async def get_current_description(message: Message, state: FSMContext):
    await state.update_data(current=message.text.strip())
    await message.answer(
        "Шаг 3/5 — самый важный\n\n"
        "Какую роль ваш продукт/услуга играет в жизни клиента?\n"
        "Что меняется в его дне/жизни/бизнесе, когда он вас выбирает?\n"
        "Пишите максимально конкретно и эмоционально.",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(Positioning.waiting_client_life)

@router.message(Positioning.waiting_client_life)
async def get_client_life(message: Message, state: FSMContext):
    await state.update_data(role_raw=message.text.strip())
    await message.answer(
        "Шаг 4/5\n\n"
        "В какой категории вы сейчас соревнуетесь?\n"
        "(например: «кофеен», «CRM-систем», «курсов по инвестициям» и т.д.)",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(Positioning.waiting_category)

@router.message(Positioning.waiting_category)
async def get_category(message: Message, state: FSMContext):
    await state.update_data(category=message.text.strip())
    await message.answer(
        "Шаг 5/5\n\n"
        "Последний рывок:\n"
        "Какое одно слово или короткую фразу вы бы хотели, чтобы люди ассоциировали именно с вами?\n"
        "(мечта, желание, обещание — что угодно)",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(Positioning.waiting_wish)

# === Финал — Прозрение! ===
@router.message(Positioning.waiting_wish)
async def final(message: Message, state: FSMContext):
    await state.update_data(wish=message.text.strip())
    data = await state.get_data()

    brand = data["brand"]
    current = data["current"]
    role_raw = data["role_raw"]
    category = data["category"]
    wish = data["wish"]

    # Здесь будет наша 4-слойная магия (пока упрощённо, но уже очень мощно)
    response = f"""
<b>ПРОЗРЕНИЕ ДЛЯ «{brand.upper()}»</b>

<b>1. Роль в жизни клиента</b>
{role_raw}

<b>2. Новая категория (предложение)</b>
Вместо «{category}» → <u>«{wish.lower()} через {brand.lower()}»</u>

<b>3. Собственническая идея</b>
«{brand} — это {wish.lower()}, который наконец-то работает так, как ты всегда хотел»

<b>4. 10-секундная артикуляция</b>
«{brand} — это не просто {category.lower()}. Это {wish.lower()} в твоей жизни.»

<b>Диагностика текущего объяснения</b>
Текущее: {current}
→ { 'Слабое' if len(current) > 50 or 'мы' in current.lower() and 'клиент' not in current.lower() else 'Неплохое, но можно острее'}

<b>Рекомендация</b>
Больше никогда не начинайте презентацию с продукта. Начинайте с роли в жизни клиента.

С этого момента ваш фундамент — смысл. Дизайн — потом.

Сохрани это сообщение. Это и есть ваше новое позиционирование.
    """.strip()

    await message.answer(response, disable_web_page_preview=True)
    await message.answer("Готово. Хочешь пройти ещё раз или для другого проекта — просто /start")
    await state.clear()

# === Запуск ===
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
