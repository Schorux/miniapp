import logging
import os
import sys

# Гарантируем что папка бота в пути
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, InlineQueryHandler
)
from telegram import WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup

from config import BOT_TOKEN
from handlers.search import search_command, handle_search_text, inline_search, play_callback
from handlers.favorites import (
    favorites_command, add_favorite_callback,
    remove_favorite_callback, show_favorites_callback
)
from handlers.wave import wave_command, wave_next_callback
from handlers.upload import handle_audio, handle_document, upload_add_favorite_callback

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WEBAPP_URL = os.environ.get("WEBAPP_URL", "")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("favorites", favorites_command))
    app.add_handler(CommandHandler("wave", wave_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("test", test_command))

    app.add_handler(InlineQueryHandler(inline_search))

    app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.Document.AUDIO, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_text))

    app.add_handler(CallbackQueryHandler(play_callback, pattern="^play:"))
    app.add_handler(CallbackQueryHandler(add_favorite_callback, pattern="^fav_add:"))
    app.add_handler(CallbackQueryHandler(remove_favorite_callback, pattern="^fav_remove:"))
    app.add_handler(CallbackQueryHandler(show_favorites_callback, pattern="^fav_show$"))
    app.add_handler(CallbackQueryHandler(upload_add_favorite_callback, pattern="^upload_fav:"))
    app.add_handler(CallbackQueryHandler(wave_next_callback, pattern="^wave_"))
    app.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern="^noop$"))

    logger.info("🎵 Бот запущен!")
    app.run_polling(drop_pending_updates=True)


async def start_command(update, context):
    keyboard = []
    if WEBAPP_URL:
        keyboard = [[InlineKeyboardButton("🎵 Открыть плеер", web_app=WebAppInfo(url=WEBAPP_URL))]]

    text = (
        "🎵 *Привет! Я твой личный музыкальный бот.*\n\n"
        "🔍 *Поиск:* просто напиши название трека\n"
        "🎧 *Свои треки:* скинь MP3 прямо в чат\n"
        "❤️ /favorites — любимые треки\n"
        "🌊 /wave — персональные рекомендации\n"
        "❓ /help — помощь"
    )
    if WEBAPP_URL:
        text += "\n\n👆 Или открой полноценный плеер кнопкой ниже"

    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )


async def help_command(update, context):
    text = (
        "❓ *Как пользоваться:*\n\n"
        "1️⃣ *Поиск на YouTube:*\n"
        "   Напиши `Radiohead Creep` → получи результаты\n\n"
        "2️⃣ *Свои MP3 из Telegram:*\n"
        "   Скинь аудиофайл в чат → бот предложит добавить в избранное\n\n"
        "3️⃣ *Моя Волна:* /wave — рекомендации по лайкам\n\n"
        "💡 Чем больше лайков — тем точнее волна!"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


async def test_command(update, context):
    lines = ["🔧 *Диагностика:*\n"]

    try:
        import yt_dlp
        lines.append(f"✅ yt-dlp {yt_dlp.version.__version__}")
    except Exception as e:
        lines.append(f"❌ yt-dlp: {e}")

    import subprocess
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        lines.append("✅ ffmpeg установлен")
    except Exception as e:
        lines.append(f"❌ ffmpeg: {e}")

    try:
        from music import search_youtube_music
        results = search_youtube_music("test", max_results=1)
        lines.append(f"✅ Поиск работает" if results else "⚠️ Поиск вернул 0 результатов")
    except Exception as e:
        lines.append(f"❌ Поиск: {e}")

    try:
        from database import get_favorites
        get_favorites()
        lines.append("✅ База данных работает")
    except Exception as e:
        lines.append(f"❌ БД: {e}")

    webapp_url = os.environ.get("WEBAPP_URL", "не задан")
    lines.append(f"🌐 WEBAPP_URL: `{webapp_url}`")

    await update.message.reply_text("\n".join(lines), parse_mode='Markdown')


if __name__ == '__main__':
    main()
