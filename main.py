import asyncio
import logging
import os
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from database import db
# Импортируем логику из новой папки
from bots.prozrenie.handlers import router as prozrenie_router

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    print("DEBUG MAIN. System starting...", flush=True)
    await db.connect()

    token = os.getenv("TOKEN")
    if not token: sys.exit(1)

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Подключаем бота
    dp.include_router(prozrenie_router)

    # Web-server для Render
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Alive"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
