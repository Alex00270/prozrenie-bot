import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

PORT = int(os.environ.get("PORT", 10000))
BASE_URL = os.environ.get(
    "BASE_URL",
    f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}"
)


async def main():
    app = web.Application()
    dp = Dispatcher()

    bots = []

    # пример
    bot = Bot(
        token=os.environ["TOKEN_NEZABUDKA"],
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    from bots.nezabudka.handlers import router
    dp.include_router(router)

    bots.append(bot)

    # webhook handler
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bots,
    ).register(app, path="/webhook")

    setup_application(app, dp)

   for bot in bots:
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(f"{BASE_URL}/webhook")


    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    print("🚀 Webhook сервер запущен", flush=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
