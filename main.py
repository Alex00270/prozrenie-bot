import asyncio
import logging
import sys
import os
import importlib
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Включаем логирование, чтобы видеть в Render каждое действие
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    # Папка с ботами
    bots_dir = "bots"
    
    # 1. Проверяем, существует ли папка
    if not os.path.exists(bots_dir):
        print(f"❌ CRITICAL: Папка {bots_dir} не найдена в корне проекта!", flush=True)
        return

    # Получаем список папок-ботов (исключая системные __pycache__)
    bot_folders = [
        f for f in os.listdir(bots_dir) 
        if os.path.isdir(os.path.join(bots_dir, f)) and not f.startswith("__")
    ]

    tasks = []
    print(f"DEBUG: Найдено модулей: {bot_folders}", flush=True)

    # 2. Автозагрузка
    for bot_name in bot_folders:
        try:
            # А. Формируем имя переменной: staff_bot -> TOKEN_STAFF_BOT
            env_var_name = f"TOKEN_{bot_name.upper()}"
            token = os.getenv(env_var_name)

            # Б. Если токена нет в Render — пропускаем (но пишем в лог)
            if not token:
                print(f"⚠️ ПРОПУСК [{bot_name}]: В Render нет переменной {env_var_name}", flush=True)
                continue

            # В. Импортируем роутер: bots/staff_bot/handlers.py
            module = importlib.import_module(f"bots.{bot_name}.handlers")
            
            if not hasattr(module, "router"):
                print(f"⚠️ ОШИБКА [{bot_name}]: В handlers.py не найден объект 'router'", flush=True)
                continue
            
            # Г. Запуск бота
            # Используем HTML, чтобы бот не падал от жирного шрифта
            bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            dp = Dispatcher()
            dp.include_router(module.router)
            
            # Удаляем вебхук (важно после конфликтов!)
            await bot.delete_webhook(drop_pending_updates=True)
            
            tasks.append(dp.start_polling(bot))
            print(f"✅ Бот [{bot_name}] УСПЕШНО ЗАПУЩЕН (Token: {env_var_name})", flush=True)

        except ImportError:
             print(f"⚠️ ОШИБКА: Не найден файл handlers.py в папке bots/{bot_name}", flush=True)
        except Exception as e:
            print(f"❌ СБОЙ ЗАГРУЗКИ [{bot_name}]: {e}", flush=True)

    # 3. Финальная проверка
    if not tasks:
        print("❌ FATAL: Нет активных ботов. Проверьте переменные окружения!", flush=True)
        # Не выходим, чтобы Render не рестартил контейнер как бешеный
        await asyncio.sleep(600)
        return

    print(f"🚀 СИСТЕМА В ЭФИРЕ: Запущено {len(tasks)} ботов.", flush=True)
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
