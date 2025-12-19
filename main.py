import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Импорты ботов
from bots.prozrenie.handlers import router as prozrenie_router
from bots.angry_bot.handlers import router as angry_router
from bots.staff_bot.handlers import router as staff_router

# Логирование
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    # 1. Читаем токены (ТЕПЕРЬ ПРАВИЛЬНО: BOT_TOKEN_2)
    token1 = os.getenv("TOKEN")
    token2 = os.getenv("BOT_TOKEN_2") # <--- Исправил, теперь совпадает с Render
    
    if not token1 or not token2:
        print(f"CRITICAL ERROR: Tokens missing. Got token1={bool(token1)}, token2={bool(token2)}", flush=True)
        return

    # --- БОТ 1: ПРОЗРЕНИЕ (СТРАТЕГ + КАССИР) ---
    bot_prozrenie = Bot(token=token1, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp_prozrenie = Dispatcher()
    
    # ПОРЯДОК ВАЖЕН: Сначала Кассир (ловит /report)
    dp_prozrenie.include_router(staff_router)
    # Потом Стратег (ловит всё остальное)
    dp_prozrenie.include_router(prozrenie_router)

    # --- БОТ 2: СКЕПТИК ---
    bot_skeptic = Bot(token=token2, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp_skeptic = Dispatcher()
    dp_skeptic.include_router(angry_router)

    # Чистка и запуск
    await bot_prozrenie.delete_webhook(drop_pending_updates=True)
    await bot_skeptic.delete_webhook(drop_pending_updates=True)

    print("✅ БОТЫ ЗАПУЩЕНЫ УСПЕШНО", flush=True)

    await asyncio.gather(
        dp_prozrenie.start_polling(bot_prozrenie),
        dp_skeptic.start_polling(bot_skeptic)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
