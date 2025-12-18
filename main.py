import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Импорты ваших ботов
from bots.prozrenie.handlers import router as prozrenie_router
from bots.angry_bot.handlers import router as angry_router
# --- ДОБАВИЛИ ИМПОРТ КАССИРА ---
from bots.staff_bot.handlers import router as staff_router

# ... (тут настройка логирования и загрузка переменных) ...

async def main():
    # ... (инициализация ботов) ...
    
    # БОТ 1: ПРОЗРЕНИЕ
    bot_prozrenie = Bot(token=os.getenv("TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp_prozrenie = Dispatcher()
    dp_prozrenie.include_router(prozrenie_router)
    
    # --- ПОДКЛЮЧАЕМ КАССИРА СЮДА ---
    dp_prozrenie.include_router(staff_router) 
    # Теперь Прозрение умеет и стратегии строить, и кассу принимать по команде /report

    # БОТ 2: ЗЛОЙ СКЕПТИК
    bot_skeptic = Bot(token=os.getenv("TOKEN_2"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp_skeptic = Dispatcher()
    dp_skeptic.include_router(angry_router)

    await bot_prozrenie.delete_webhook(drop_pending_updates=True)
    await bot_skeptic.delete_webhook(drop_pending_updates=True)

    # Запускаем обоих
    await asyncio.gather(
        dp_prozrenie.start_polling(bot_prozrenie),
        dp_skeptic.start_polling(bot_skeptic)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
