import asyncio
import logging
import sys
import os
import importlib
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    # 1. Сканируем папку bots/
    bots_dir = "bots"
    if not os.path.exists(bots_dir):
        print(f"❌ CRITICAL: Папка {bots_dir} не найдена!", flush=True)
        return

    # Получаем список папок-ботов
    bot_folders = [
        f for f in os.listdir(bots_dir) 
        if os.path.isdir(os.path.join(bots_dir, f)) and not f.startswith("__")
    ]

    tasks = []
    print(f"DEBUG: Найдено модулей: {len(bot_folders)} {bot_folders}", flush=True)

    # 2. Универсальный запуск
    for bot_name in bot_folders:
        try:
            # А. Динамический импорт роутера
            # Python сам находит bots/angry_bot/handlers.py
            module = importlib.import_module(f"bots.{bot_name}.handlers")
            
            if not hasattr(module, "router"):
                print(f"⚠️ Пропуск [{bot_name}]: в handlers.py нет 'router'", flush=True)
                continue

            # Б. Авто-поиск токена
            # Если папка 'angry_bot', ищем переменную 'TOKEN_ANGRY_BOT'
            env_var = f"TOKEN_{bot_name.upper()}"
            token = os.getenv(env_var)

            if token:
                # В. Старт (HTML режим для надежности)
                bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
                dp = Dispatcher()
                dp.include_router(module.router)
                
                await bot.delete_webhook(drop_pending_updates=True)
                tasks.append(dp.start_polling(bot))
                print(f"✅ Бот [{bot_name}] ЗАГРУЖЕН (Токен: {env_var})", flush=True)
            else:
                print(f"⚠️ ОШИБКА КОНФИГУРАЦИИ: Для папки '{bot_name}' не найдена переменная '{env_var}'", flush=True)

        except Exception as e:
            print(f"❌ Сбой загрузки [{bot_name}]: {e}", flush=True)

    if not tasks:
        print("❌ FATAL: Нет активных ботов. Проверьте имена переменных в Render!", flush=True)
        return

    print(f"🚀 СИСТЕМА В ЭФИРЕ: {len(tasks)} юнитов работают.", flush=True)
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
