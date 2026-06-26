import sys
import os

# Получаем абсолютный путь к папке где лежит main.py
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

print(f"APP_DIR: {APP_DIR}")
print(f"sys.path: {sys.path[:3]}")
print(f"files: {os.listdir(APP_DIR)}")

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
    sys.path.insert(0, APP_DIR)
    from bot import main as bot_main
    bot_main()

async def run_all():
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    await server.serve()

if __name__ == '__main__':
    asyncio.run(run_all())
