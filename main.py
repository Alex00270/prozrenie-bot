import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Импорты роутеров
from bots.prozrenie.handlers import router as prozrenie_router
from bots.angry_bot.handlers import router as angry_router
from bots.staff_bot.handlers import router as staff_router
from bots.ai_team.handlers import router as ai_team_router 

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    # 1. Читаем переменные (Строго по скриншоту Render)
    token_prozrenie = os.getenv("TOKEN")
    token_staff     = os.getenv("TOKEN_STAFF")
    token_skeptic   = os.getenv("BOT_TOKEN_2") # Исправлено под реальность
    token_ai_team   = os.getenv("TOKEN_AI_TEAM")

    # 2. Конфиг запуска
    bots_config = [
        {"name": "Prozrenie", "token": token_prozrenie, "router": prozrenie_router},
        {"name": "StaffBot",  "token": token_staff,     "router": staff_router},
        {"name": "Skeptic",   "token": token_skeptic,   "router": angry_router},
        {"name": "AI_Team",   "token": token_ai_team,   "router": ai_team_router},
    ]

    tasks = []
    print("DEBUG: Инициализация системы...", flush=True)

    # 3. Старт
    for bot_conf in bots_config:
        if bot_conf["token"]:
            try:
                bot = Bot(token=bot_conf["token"], default=DefaultBotProperties(parse_mode=ParseMode.Markdown))
                dp = Dispatcher()
                dp.include_router(bot_conf["router"])
                
                await bot.delete_webhook(drop_pending_updates=True)
                tasks.append(dp.start_polling(bot))
                print(f"✅ [{bot_conf['name']}] добавлен в очередь.", flush=True)
            except Exception as e:
                print(f"❌ Ошибка старта [{bot_conf['name']}]: {e}", flush=True)
        else:
            # Не паникуем, если какого-то токена нет, просто предупреждаем
            print(f"⚠️ Пропуск [{bot_conf['name']}]: Токен не найден.", flush=True)

    if not tasks:
        print("❌ CRITICAL: Ни один бот не запущен!", flush=True)
        return

    print(f"🚀 ЗАПУСК {len(tasks)} БОТОВ.", flush=True)
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
