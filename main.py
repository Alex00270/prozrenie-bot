import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Импортируем роутеры
from bots.prozrenie.handlers import router as prozrenie_router
from bots.angry_bot.handlers import router as angry_router
from bots.staff_bot.handlers import router as staff_router
from bots.ai_team.handlers import router as ai_team_router 

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    # 1. Читаем токены СТРОГО по скриншоту Render Environment
    token_prozrenie = os.getenv("TOKEN")         #
    token_staff     = os.getenv("TOKEN_STAFF")   #
    token_skeptic   = os.getenv("BOT_TOKEN_2")   # <--- ВОТ ТУТ БЫЛА ОШИБКА
    token_ai_team   = os.getenv("TOKEN_AI_TEAM") #

    # 2. Конфигурация ботов
    # Здесь мы связываем конкретный токен с конкретным роутером (логикой)
    bots_config = [
        # Стратег (Прозрение)
        {"name": "Prozrenie", "token": token_prozrenie, "router": prozrenie_router},
        
        # Кассир (Staff)
        {"name": "StaffBot",  "token": token_staff,     "router": staff_router},
        
        # Скептик (Angry) - используем BOT_TOKEN_2
        {"name": "Skeptic",   "token": token_skeptic,   "router": angry_router},
        
        # Консилиум (AI Team)
        {"name": "AI_Team",   "token": token_ai_team,   "router": ai_team_router},
    ]

    tasks = []

    # 3. Инициализация и запуск
    print("DEBUG: Начинаю инициализацию ботов...", flush=True)

    for bot_conf in bots_config:
        if bot_conf["token"]:
            try:
                # Создаем экземпляр бота
                bot = Bot(token=bot_conf["token"], default=DefaultBotProperties(parse_mode=ParseMode.Markdown))
                dp = Dispatcher()
                dp.include_router(bot_conf["router"])
                
                # Удаляем вебхук, чтобы не было конфликтов с предыдущими запусками
                await bot.delete_webhook(drop_pending_updates=True)
                
                # Добавляем задачу polling в список
                tasks.append(dp.start_polling(bot))
                print(f"✅ Бот [{bot_conf['name']}] успешно добавлен в очередь запуска.", flush=True)
            except Exception as e:
                print(f"❌ CRITICAL ERROR: Не удалось создать бота [{bot_conf['name']}]. Ошибка: {e}", flush=True)
        else:
            print(f"⚠️ WARNING: Токен для [{bot_conf['name']}] не найден в переменных окружения!", flush=True)

    if not tasks:
        print("❌ FATAL: Нет ни одного активного бота для запуска. Проверьте .env!", flush=True)
        return

    print(f"🚀 ЗАПУСК СИСТЕМЫ: Стартуем {len(tasks)} ботов одновременно.", flush=True)
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
