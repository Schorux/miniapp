import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY", "")

# Всегда используем локальные папки — не зависим от Volume
DB_PATH = "music_bot.db"
TEMP_MUSIC_DIR = "temp_music"

MAX_SEARCH_RESULTS = 5
WAVE_BATCH_SIZE = 5
FAVORITES_FOR_RECOMMENDATIONS = 10
