import sys
import os
_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _dir)
os.chdir(_dir)
import logging
import threading
import uvicorn
from webapp import app as fastapi_app

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def run_fastapi():
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        fastapi_app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        http="httptools",      # вместо h11 — поддерживает chunked transfer
        loop="asyncio",
    )

if __name__ == '__main__':
    t = threading.Thread(target=run_fastapi, daemon=True)
    t.start()
    from bot import main as bot_main
    bot_main()
