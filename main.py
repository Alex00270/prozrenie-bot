import asyncio
import logging
import os
import sys
from aiohttp import web, ClientSession # <--- Добавили ClientSession
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from database import db
from bots.prozrenie.handlers import router as prozrenie_router
from bots.angry_bot.handlers import router as angry_router 
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# --- ФУНКЦИЯ БЕССМЕРТИЯ (SELF-PING) ---
async def keep_alive_loop():
    """Пингует сам себя каждые 10 минут, чтобы Render не уснул"""
    # Render автоматически создает эту переменную с адресом вашего сайта
    app_url = os.getenv("RENDER_EXTERNAL_URL") 
    
    if not app_url:
        print("DEBUG KEEP-ALIVE. No external URL found. Skipping self-ping.", flush=True)
        return

    print(f"DEBUG KEEP-ALIVE. Starting self-ping to {app_url}", flush=True)
    async with ClientSession() as session:
        while True:
            try:
                # Ждем 10 минут (600 секунд), так как лимит Render — 15 минут
                await asyncio.sleep(600) 
                async with session.get(app_url) as response:
                    print(f"DEBUG KEEP-ALIVE. Ping sent. Status: {response.status}", flush=True)
            except Exception as e:
                print(f"DEBUG KEEP-ALIVE. Error: {e}", flush=True)

# --- MAIN ---
async def main():
    await db.connect()

    # Конфигурация ботов
    bots_config = [
        ("TOKEN", prozrenie_router),
        ("BOT_TOKEN_2", angry_router) 
    ]

    apps = [] 

    # 1. Задачи ботов
    for token_env_name, router in bots_config:
        token = os.getenv(token_env_name)
        if not token: continue

        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()
        dp.include_router(router)
        apps.append(dp.start_polling(bot))

    # 2. Веб-сервер
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Alive"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()

    # 3. ДОБАВЛЯЕМ SELF-PING В ЗАДАЧИ
    apps.append(keep_alive_loop())

    # Запуск всего
    await asyncio.gather(*apps)

if __name__ == "__main__":
    asyncio.run(main())
