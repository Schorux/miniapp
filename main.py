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
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000, log_level="warning")

if __name__ == '__main__':
    # FastAPI в отдельном потоке
    t = threading.Thread(target=run_fastapi, daemon=True)
    t.start()

    # Бот в главном потоке (требует main thread для сигналов)
    from bot import main as bot_main
    bot_main()
