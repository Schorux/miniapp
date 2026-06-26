"""
Обработчик загрузки MP3 файлов прямо из Telegram.
Пользователь скидывает аудио/документ → бот сохраняет в базу.
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database import add_favorite, is_favorite
from config import TEMP_MUSIC_DIR

logger = logging.getLogger(__name__)

os.makedirs(TEMP_MUSIC_DIR, exist_ok=True)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает аудио-файлы и голосовые сообщения.
    Telegram присылает их как Audio объект с метаданными.
    """
    audio = update.message.audio

    # Telegram сам парсит ID3-теги из MP3
    track_name = audio.title or "Неизвестный трек"
    artist = audio.performer or "Неизвестный исполнитель"
    duration_sec = audio.duration or 0
    file_id = audio.file_id

    minutes = duration_sec // 60
    secs = duration_sec % 60
    duration_str = f"{minutes}:{secs:02d}"

    already = is_favorite(track_name, artist)
    heart = "❤️ Уже в избранном" if already else "❤️ Добавить в избранное"

    text = (
        f"🎵 *{track_name}*\n"
        f"👤 {artist}\n"
        f"⏱ {duration_str}\n\n"
        f"Что сделать с этим треком?"
    )

    keyboard = [[
        InlineKeyboardButton(
            heart,
            callback_data=f"upload_fav:{file_id}:{artist[:30]}:{track_name[:30]}"
        )
    ]]

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает документы — MP3, отправленные как файл (не как аудио).
    Такое бывает если отправить файл через 'отправить как файл'.
    """
    doc = update.message.document

    if not doc.mime_type or 'audio' not in doc.mime_type:
        return  # не аудио — игнорируем

    # Имя файла как fallback
    filename = doc.file_name or "track.mp3"
    track_name = filename.replace('.mp3', '').replace('.flac', '').replace('.ogg', '')

    # Пробуем распарсить "Artist - Track" из имени файла
    if ' - ' in track_name:
        parts = track_name.split(' - ', 1)
        artist = parts[0].strip()
        track_name = parts[1].strip()
    else:
        artist = "Неизвестный исполнитель"

    file_id = doc.file_id
    already = is_favorite(track_name, artist)
    heart = "❤️ Уже в избранном" if already else "❤️ Добавить в избранное"

    text = (
        f"📄 *{track_name}*\n"
        f"👤 {artist}\n\n"
        f"Файл получен! Что сделать?"
    )

    keyboard = [[
        InlineKeyboardButton(
            heart,
            callback_data=f"upload_fav:{file_id}:{artist[:30]}:{track_name[:30]}"
        )
    ]]

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def upload_add_favorite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить загруженный трек в избранное"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(':', 3)
    if len(parts) < 4:
        return

    _, file_id, artist, track_name = parts

    if is_favorite(track_name, artist):
        await query.answer("✅ Уже в избранном!", show_alert=False)
        return

    # Сохраняем file_id вместо youtube_url — это Telegram file ID
    add_favorite(
        track_name=track_name,
        artist=artist,
        youtube_url=f"tg://{file_id}",  # префикс tg:// означает Telegram файл
    )

    await query.answer("❤️ Добавлено в избранное!", show_alert=False)

    # Обновляем кнопку
    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❤️ В избранном", callback_data="noop")
            ]])
        )
    except Exception:
        pass
