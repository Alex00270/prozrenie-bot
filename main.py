import asyncio
import logging
import sys
import os
import importlib
from aiohttp import web  # ЭТО НУЖНО ДЛЯ RENDER
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- ФЕЙКОВЫЙ СЕРВЕР ЧТОБЫ RENDER НЕ УБИВАЛ БОТА ---
async def health_check(request):
    return web.Response(text="Bot is alive")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    # Render сам дает порт через переменную PORT, обычно это 10000
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    print(f"🌍 Dummy Server started on port {port}", flush=True)
    await site.start()

# --- ОСНОВНОЙ КОД ---
async def main():
    # 1. Запускаем фейковый сервер ПЕРВЫМ делом
    await start_dummy_server()

    bots_dir = "bots"
    if not os.path.exists(bots_dir):
        print(f"❌ CRITICAL: Папка {bots_dir} не найдена!", flush=True)
        await asyncio.Event().wait() # Не падаем, держим порт

    bot_folders = [f for f in os.listdir(bots_dir) if os.path.isdir(os.path.join(bots_dir, f)) and not f.startswith("__")]
    
    tasks = []
    print(f"DEBUG: Найдено ботов: {bot_folders}", flush=True)

    for bot_name in bot_folders:
        try:
            # Ищем переменную TOKEN_ИМЯПАПКИ (например TOKEN_STAFF_BOT)
            env_var_name = f"TOKEN_{bot_name.upper()}"
            token = os.getenv(env_var_name)

            if not token:
                print(f"⚠️ ПРОПУСК [{bot_name}]: Нет переменной {env_var_name}", flush=True)
                continue

            module = importlib.import_module(f"bots.{bot_name}.handlers")
            
            # Запускаем
            bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            dp = Dispatcher()
            dp.include_router(module.router)
            await bot.delete_webhook(drop_pending_updates=True)
            
            tasks.append(dp.start_polling(bot))
            print(f"✅ Бот [{bot_name}] ЗАПУЩЕН", flush=True)

        except Exception as e:
            print(f"❌ ОШИБКА [{bot_name}]: {e}", flush=True)

    if not tasks:
        print("❌ FATAL: Боты не запущены. Сервер работает вхолостую.", flush=True)
        await asyncio.Event().wait() # Держим процесс живым
    else:
        print(f"🚀 ВСЕ СИСТЕМЫ В НОРМЕ. Работает {len(tasks)} ботов.", flush=True)
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
