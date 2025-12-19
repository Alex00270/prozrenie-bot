import asyncio
import logging
import sys
import os
from aiohttp import web # <--- НУЖНО ДЛЯ ОБМАНА RENDER
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ИМПОРТЫ РОУТЕРОВ
from bots.prozrenie.handlers import router as prozrenie_router
from bots.angry_bot.handlers import router as angry_router
from bots.staff_bot.handlers import router as staff_router

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- ФУНКЦИЯ-ОБМАНКА ДЛЯ RENDER ---
async def health_check(request):
    return web.Response(text="Bot is alive! 🤖")

async def start_dummy_server():
    # Render сам передает порт через переменную PORT. Если нет - берем 8080.
    port = int(os.getenv("PORT", 8080))
    
    app = web.Application()
    app.router.add_get('/', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    print(f"🌍 FAKE SERVER STARTED ON PORT {port}", flush=True)
    await site.start()
# ----------------------------------

async def main():
    print("🚀 ЗАПУСК МУЛЬТИ-БОТ СИСТЕМЫ...", flush=True)

    # Читаем токены
    token_prozrenie = os.getenv("TOKEN")
    token_skeptic = os.getenv("BOT_TOKEN_2") or os.getenv("TOKEN_2")
    token_staff = os.getenv("TOKEN_STAFF")

    tasks = [] 

    # 1. ЗАПУСКАЕМ ФЕЙКОВЫЙ СЕРВЕР (ОБЯЗАТЕЛЬНО ПЕРВЫМ)
    tasks.append(start_dummy_server())

    # --- БОТ 1: СТРАТЕГ ---
    if token_prozrenie:
        bot_prozrenie = Bot(token=token_prozrenie, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp_prozrenie = Dispatcher()
        dp_prozrenie.include_router(prozrenie_router)
        await bot_prozrenie.delete_webhook(drop_pending_updates=True)
        tasks.append(dp_prozrenie.start_polling(bot_prozrenie))
        print("✅ Бот 'СТРАТЕГ' добавлен в задачи")

    # --- БОТ 2: КАССИР ---
    if token_staff:
        bot_staff = Bot(token=token_staff, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp_staff = Dispatcher()
        dp_staff.include_router(staff_router)
        await bot_staff.delete_webhook(drop_pending_updates=True)
        tasks.append(dp_staff.start_polling(bot_staff))
        print("✅ Бот 'КАССИР' добавлен в задачи")
    else:
        print("❌ ОШИБКА: TOKEN_STAFF не найден!")

    # --- БОТ 3: СКЕПТИК ---
    if token_skeptic:
        bot_skeptic = Bot(token=token_skeptic, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp_skeptic = Dispatcher()
        dp_skeptic.include_router(angry_router)
        await bot_skeptic.delete_webhook(drop_pending_updates=True)
        tasks.append(dp_skeptic.start_polling(bot_skeptic))
        print("✅ Бот 'СКЕПТИК' добавлен в задачи")

    # ЗАПУСК ВСЕГО
    if len(tasks) > 1:
        print(f"🔥 Запускаем {len(tasks)} процессов (Сервер + Боты)...", flush=True)
        await asyncio.gather(*tasks)
    else:
        print("💀 Ничего не запущено.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
