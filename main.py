import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

PORT = int(os.environ.get("PORT", 10000))

async def main():
    app = web.Application()

    bots = []   # список (bot, dispatcher)

    # --- тут твоя логика поиска ботов ---
    # пример:
    # bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # dp = Dispatcher()
    # dp.include_router(router)
    # bots.append((bot, dp))

    for bot, dp in bots:
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    ).register(app, path=f"/webhook/{bot.token}")

    setup_application(app, dp)  # ✅ ВАЖНО: ВНУТРИ ЦИКЛА

    await bot.set_webhook(
        url=f"{BASE_URL}/webhook/{bot.token}"
    )

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()

    print(f"🚀 Webhook сервер запущен на порту {PORT}", flush=True)

    # ⛔️ ВАЖНО: держим процесс живым
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
