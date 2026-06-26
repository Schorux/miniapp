"""
Точка входа — запускает бот и веб-сервер одновременно
"""
import asyncio
import logging
import uvicorn
from webapp import app as fastapi_app
from bot import main as bot_main

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def run_all():
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    await asyncio.gather(
        server.serve(),
        asyncio.to_thread(bot_main)
    )

if __name__ == '__main__':
    asyncio.run(run_all())
