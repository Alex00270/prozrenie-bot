import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# 1. ИМПОРТЫ РОУТЕРОВ (Логика ботов)
from bots.prozrenie.handlers import router as prozrenie_router
from bots.angry_bot.handlers import router as angry_router
from bots.staff_bot.handlers import router as staff_router

# Логирование
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    print("🚀 ЗАПУСК МУЛЬТИ-БОТ СИСТЕМЫ...", flush=True)

    # 2. ЧИТАЕМ ВСЕ ТОКЕНЫ (Строго по твоим именам)
    token_prozrenie = os.getenv("TOKEN")
    token_skeptic = os.getenv("BOT_TOKEN_2") or os.getenv("TOKEN_2")
    token_staff = os.getenv("TOKEN_STAFF") # <--- Твой новый токен

    tasks = [] # Список задач для запуска

    # --- БОТ 1: СТРАТЕГ (Прозрение) ---
    if token_prozrenie:
        bot_prozrenie = Bot(token=token_prozrenie, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp_prozrenie = Dispatcher()
        dp_prozrenie.include_router(prozrenie_router)
        
        await bot_prozrenie.delete_webhook(drop_pending_updates=True)
        tasks.append(dp_prozrenie.start_polling(bot_prozrenie))
        print("✅ Бот 'СТРАТЕГ' готов")
    else:
        print("❌ ОШИБКА: Нет TOKEN для Стратега!")

    # --- БОТ 2: КАССИР (Staff) ---
    if token_staff:
        bot_staff = Bot(token=token_staff, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp_staff = Dispatcher()
        dp_staff.include_router(staff_router)
        
        await bot_staff.delete_webhook(drop_pending_updates=True)
        tasks.append(dp_staff.start_polling(bot_staff))
        print("✅ Бот 'КАССИР' готов")
    else:
        print("⚠️ Внимание: TOKEN_STAFF не найден. Кассир не запустится.")

    # --- БОТ 3: СКЕПТИК (Angry) ---
    if token_skeptic:
        bot_skeptic = Bot(token=token_skeptic, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp_skeptic = Dispatcher()
        dp_skeptic.include_router(angry_router)
        
        await bot_skeptic.delete_webhook(drop_pending_updates=True)
        tasks.append(dp_skeptic.start_polling(bot_skeptic))
        print("✅ Бот 'СКЕПТИК' готов")

    # 3. ЗАПУСКАЕМ ВСЕХ
    if tasks:
        print(f"🔥 Работают {len(tasks)} ботов одновременно...", flush=True)
        await asyncio.gather(*tasks)
    else:
        print("💀 Ни один бот не запущен. Проверь переменные!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
