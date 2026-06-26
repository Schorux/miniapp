import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY", "")

# Абсолютный путь — работает из любой директории
_base = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_base, "music_bot.db")
TEMP_MUSIC_DIR = os.path.join(_base, "temp_music")

MAX_SEARCH_RESULTS = 5
WAVE_BATCH_SIZE = 5
FAVORITES_FOR_RECOMMENDATIONS = 10
