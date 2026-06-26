"""
Обработчик поиска музыки
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from music import search_youtube_music, download_audio, cleanup_old_files
from database import add_to_history, is_favorite

logger = logging.getLogger(__name__)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /search"""
    if context.args:
        query = ' '.join(context.args)
        await perform_search(update, context, query)
    else:
        await update.message.reply_text(
            "🔍 Введи название трека:\nНапример: `Radiohead Creep`",
            parse_mode=ParseMode.MARKDOWN
        )


async def handle_search_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка любого текстового сообщения как поискового запроса"""
    query = update.message.text.strip()

    # Игнорируем очень короткие запросы
    if len(query) < 2:
        return

    await perform_search(update, context, query)


async def perform_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Выполнить поиск и показать результаты"""
    msg = await update.message.reply_text(f"🔍 Ищу: *{query}*...", parse_mode=ParseMode.MARKDOWN)

    results = search_youtube_music(query)

    if not results:
        await msg.edit_text("😕 Ничего не найдено. Попробуй другой запрос.")
        return

    await msg.delete()

    for i, track in enumerate(results[:5], 1):
        in_favorites = is_favorite(track['track_name'], track['artist'])
        heart = "❤️" if in_favorites else "🤍"

        text = (
            f"{i}. 🎵 *{track['track_name']}*\n"
            f"👤 {track['artist']}\n"
            f"⏱ {track['duration']}"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "▶️ Скачать и слушать",
                    callback_data=f"play:{track['id']}:{track['artist'][:30]}:{track['track_name'][:30]}"
                ),
                InlineKeyboardButton(
                    f"{heart} Избранное",
                    callback_data=f"fav_add:{track['id']}:{track['artist'][:30]}:{track['track_name'][:30]}"
                ),
            ]
        ]

        # Сохраняем URL в контексте для последующего скачивания
        if 'track_cache' not in context.bot_data:
            context.bot_data['track_cache'] = {}
        context.bot_data['track_cache'][track['id']] = track

        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def play_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скачать и отправить трек по нажатию кнопки"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":", 3)
    if len(parts) < 2:
        await query.message.reply_text("❌ Ошибка: неверные данные.")
        return

    video_id = parts[1]
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"

    # Пробуем получить трек из кэша
    track = context.bot_data.get('track_cache', {}).get(video_id, {})
    title = track.get('title', video_id)

    msg = await query.message.reply_text(f"⏳ Скачиваю: *{title}*...", parse_mode=ParseMode.MARKDOWN)

    file_path = await download_audio(youtube_url, video_id)

    if not file_path:
        await msg.edit_text("❌ Не удалось скачать трек. Попробуй ещё раз.")
        return

    await msg.edit_text(f"📤 Отправляю: *{title}*...", parse_mode=ParseMode.MARKDOWN)

    try:
        with open(file_path, 'rb') as audio_file:
            await query.message.reply_audio(
                audio=audio_file,
                title=track.get('track_name', title),
                performer=track.get('artist', ''),
            )
        await msg.delete()
        cleanup_old_files()
    except Exception as e:
        logger.error(f"Ошибка отправки аудио: {e}")
        await msg.edit_text("❌ Ошибка при отправке файла.")


async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline-поиск через @botname запрос"""
    query = update.inline_query.query.strip()

    if not query or len(query) < 2:
        return

    results = search_youtube_music(query, max_results=5)

    inline_results = []
    for track in results:
        inline_results.append(
            InlineQueryResultArticle(
                id=track['id'],
                title=f"🎵 {track['track_name']}",
                description=f"{track['artist']} • {track['duration']}",
                input_message_content=InputTextMessageContent(
                    f"🎵 {track['track_name']} — {track['artist']}\n"
                    f"🔗 {track['url']}"
                )
            )
        )

    await update.inline_query.answer(inline_results, cache_time=30)
