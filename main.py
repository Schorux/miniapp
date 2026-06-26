import sys
import os

# Добавляем /app в путь ДО любых импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import logging
import threading
import uvicorn
from webapp import app as fastapi_app

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def run_bot():
    from bot import main as bot_main
    bot_main()

async def run_all():
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(config)

    # Бот в отдельном потоке, FastAPI в async
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    await server.serve()

if __name__ == '__main__':
    asyncio.run(run_all())
