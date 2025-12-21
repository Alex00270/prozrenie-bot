import asyncio
import logging
import os
import importlib

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

logging.basicConfig(level=logging.INFO)

WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")
PORT = int(os.getenv("PORT", 10000))
BASE_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render даёт автоматически


async def main():
    if not BASE_URL:
        raise RuntimeError("RENDER_EXTERNAL_URL is not set")

    app = web.Application()

    bots_dir = "bots"
    bots = []

    print("🔍 Ищу ботов...", flush=True)

    for bot_name in os.listdir(bots_dir):
        bot_path = os.path.join(bots_dir, bot_name)
        if not os.path.isdir(bot_path) or bot_name.startswith("_"):
            continue

        token_env = f"TOKEN_{bot_name.upper()}"
        token = os.getenv(token_env)

        if not token:
            print(f"⚠️ Пропуск {bot_name}: нет {token_env}", flush=True)
            continue

        try:
            module = importlib.import_module(f"bots.{bot_name}.handlers")

            bot = Bot(
                token=token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            dp = Dispatcher()
            dp.include_router(module.router)

            webhook_url = f"{BASE_URL}{WEBHOOK_PATH}/{bot.token}"

            await bot.set_webhook(
                webhook_url,
                secret_token=WEBHOOK_SECRET,
                drop_pending_updates=True,
            )

            SimpleRequestHandler(
                dispatcher=dp,
                bot=bot,
                secret_token=WEBHOOK_SECRET,
            ).register(app, path=f"{WEBHOOK_PATH}/{bot.token}")

            bots.append(bot)
            print(f"✅ Бот [{bot_name}] подключён к webhook", flush=True)

        except Exception as e:
            print(f"❌ Ошибка запуска {bot_name}: {e}", flush=True)

    setup_application(app, bots)

    print(f"🚀 Webhook сервер запущен на порту {PORT}", flush=True)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
