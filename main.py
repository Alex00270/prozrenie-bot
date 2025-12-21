"""
Multi-bot webhook с автоматическим обнаружением ботов
Конвенция: папка bots/nezabudka → TOKEN_NEZABUDKA
+ Self-ping чтобы Render не засыпал
"""
import os
import asyncio
import logging
from pathlib import Path
from importlib import import_module
from aiohttp import web
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

PORT = int(os.getenv('PORT', 10000))
RENDER_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME')
BASE_URL = f"https://{RENDER_HOSTNAME}" if RENDER_HOSTNAME else None
BOTS_DIR = Path(__file__).parent / 'bots'

# Self-ping настройки
PING_INTERVAL = 600  # 10 минут (Render засыпает через 15)
PING_ENABLED = os.getenv('SELF_PING_ENABLED', 'true').lower() == 'true'


def discover_bots():
    """
    Сканирует папку bots/ и находит всех ботов
    Конвенция: bots/nezabudka/ → TOKEN_NEZABUDKA
    """
    discovered = []
    
    if not BOTS_DIR.exists():
        logger.warning(f"Bots directory not found: {BOTS_DIR}")
        return discovered
    
    for bot_dir in BOTS_DIR.iterdir():
        if not bot_dir.is_dir() or bot_dir.name.startswith('_'):
            continue
        
        handlers_file = bot_dir / 'handlers.py'
        
        if not handlers_file.exists():
            logger.warning(f"⚠️ {bot_dir.name}: handlers.py not found, skipping")
            continue
        
        # Конвенция: папка → TOKEN_UPPERCASE
        folder_name = bot_dir.name
        token_env = f'TOKEN_{folder_name.upper()}'
        webhook_path = f'/webhook/{folder_name}'
        
        # Опционально загружаем config.py если есть
        enabled = True
        description = ''
        
        config_file = bot_dir / 'config.py'
        if config_file.exists():
            try:
                config_module = import_module(f'bots.{folder_name}.config')
                enabled = getattr(config_module, 'ENABLED', True)
                description = getattr(config_module, 'DESCRIPTION', '')
                # Можно переопределить через config
                token_env = getattr(config_module, 'TOKEN_ENV', token_env)
                webhook_path = getattr(config_module, 'WEBHOOK_PATH', webhook_path)
            except Exception as e:
                logger.warning(f"⚠️ {folder_name}: config.py error - {e}")
        
        discovered.append({
            'name': folder_name,
            'token_env': token_env,
            'webhook_path': webhook_path,
            'enabled': enabled,
            'handlers_module': f'bots.{folder_name}.handlers',
            'description': description
        })
        
        logger.info(f"✅ Discovered: {folder_name} → {token_env}")
    
    return discovered


async def setup_bot(app: web.Application, bot_config: dict):
    """Настраивает одного бота"""
    
    name = bot_config['name']
    
    if not bot_config.get('enabled', True):
        logger.info(f"⏭️ {name}: disabled")
        return False
    
    token = os.getenv(bot_config['token_env'])
    if not token:
        logger.warning(f"⚠️ {name}: token not found ({bot_config['token_env']})")
        return False
    
    try:
        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()
        
        # Загружаем handlers
        try:
            handlers_module = import_module(bot_config['handlers_module'])
            router = getattr(handlers_module, 'router')
            dp.include_router(router)
            logger.info(f"✅ {name}: handlers loaded")
        except Exception as e:
            logger.error(f"❌ {name}: handlers error - {e}")
            return False
        
        webhook_path = bot_config['webhook_path']
        webhook_url = f"{BASE_URL}{webhook_path}"
        
        # Регистрируем handler
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)
        
        if 'bots_data' not in app:
            app['bots_data'] = []
        
        app['bots_data'].append({
            'name': name,
            'bot': bot,
            'dispatcher': dp,
            'webhook_url': webhook_url,
            'config': bot_config
        })
        
        logger.info(f"✅ {name}: registered on {webhook_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ {name}: setup failed - {e}")
        return False


async def self_ping_task(app: web.Application):
    """
    Периодически пингует сам себя чтобы Render не усыплял сервис
    """
    if not PING_ENABLED or not BASE_URL:
        logger.info("⏭️ Self-ping disabled")
        return
    
    ping_url = f"{BASE_URL}/health"
    logger.info(f"🔔 Self-ping enabled: {ping_url} every {PING_INTERVAL}s")
    
    await asyncio.sleep(60)  # Даём время на старт
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                await asyncio.sleep(PING_INTERVAL)
                
                async with session.get(ping_url, timeout=10) as resp:
                    if resp.status == 200:
                        logger.info(f"🏓 Self-ping OK ({resp.status})")
                    else:
                        logger.warning(f"⚠️ Self-ping returned {resp.status}")
                        
            except asyncio.CancelledError:
                logger.info("🛑 Self-ping task cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Self-ping error: {e}")


async def on_startup(app: web.Application):
    """Устанавливает webhook для всех ботов"""
    logger.info("🚀 Setting up webhooks for all bots...")
    
    for bot_data in app.get('bots_data', []):
        name = bot_data['name']
        bot = bot_data['bot']
        webhook_url = bot_data['webhook_url']
        
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info(f"🧹 {name}: old webhook deleted")
            
            await bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
                allowed_updates=['message', 'callback_query', 'inline_query']
            )
            
            info = await bot.get_webhook_info()
            if info.url == webhook_url:
                logger.info(f"✅ {name}: webhook active - {webhook_url}")
            else:
                logger.error(f"❌ {name}: webhook mismatch!")
            
        except Exception as e:
            logger.error(f"❌ {name}: webhook setup failed - {e}")
    
    logger.info(f"🎉 All {len(app['bots_data'])} bot(s) ready")
    
    # Запускаем self-ping task
    if PING_ENABLED:
        app['ping_task'] = asyncio.create_task(self_ping_task(app))


async def on_shutdown(app: web.Application):
    """Cleanup при остановке"""
    logger.info("🛑 Shutting down bots...")
    
    # Останавливаем ping task
    if 'ping_task' in app:
        app['ping_task'].cancel()
        try:
            await app['ping_task']
        except asyncio.CancelledError:
            pass
    
    # Закрываем ботов
    for bot_data in app.get('bots_data', []):
        try:
            await bot_data['bot'].session.close()
            logger.info(f"✅ {bot_data['name']}: closed")
        except Exception as e:
            logger.error(f"⚠️ {bot_data['name']}: {e}")


async def create_app() -> web.Application:
    """Создаёт приложение с автоматическим обнаружением ботов"""
    
    if not BASE_URL:
        raise ValueError("RENDER_EXTERNAL_HOSTNAME not set!")
    
    logger.info("🔍 Discovering bots...")
    discovered_bots = discover_bots()
    logger.info(f"📊 Found {len(discovered_bots)} bot(s)")
    
    if not discovered_bots:
        logger.warning("⚠️ No bots discovered!")
    
    app = web.Application()
    app['bots_data'] = []
    
    # Настраиваем каждого бота
    success_count = 0
    for bot_config in discovered_bots:
        if await setup_bot(app, bot_config):
            success_count += 1
    
    logger.info(f"✅ Successfully configured {success_count}/{len(discovered_bots)} bot(s)")
    
    # Lifecycle hooks
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Health check endpoint
    async def health_check(request):
        active_bots = [bd['name'] for bd in app.get('bots_data', [])]
        return web.json_response({
            'status': 'ok',
            'bots_active': len(active_bots),
            'bots': active_bots,
            'ping_enabled': PING_ENABLED
        })
    
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)  # Для корневого пути тоже
    
    return app


def main():
    """Entry point"""
    
    logger.info("=" * 60)
    logger.info("🌸 Multi-Bot Auto-Discovery Webhook Server")
    logger.info("=" * 60)
    logger.info(f"🌐 Base URL: {BASE_URL}")
    logger.info(f"🔌 Port: {PORT}")
    logger.info(f"📁 Bots dir: {BOTS_DIR}")
    logger.info(f"🔔 Self-ping: {'enabled' if PING_ENABLED else 'disabled'} ({PING_INTERVAL}s)")
    logger.info("=" * 60)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = loop.run_until_complete(create_app())
    
    web.run_app(app, host='0.0.0.0', port=PORT, handle_signals=True)


if __name__ == '__main__':
    main()
