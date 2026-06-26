"""
Обработчик избранного (❤️ Любимые треки)
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database import add_favorite, remove_favorite, get_favorites, is_favorite

logger = logging.getLogger(__name__)


async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список избранного"""
    await show_favorites_list(update.message)


async def show_favorites_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback для кнопки 'показать избранное'"""
    query = update.callback_query
    await query.answer()
    await show_favorites_list(query.message, edit=True)


async def show_favorites_list(message, edit: bool = False):
    """Вывести список любимых треков"""
    favorites = get_favorites(limit=20)

    if not favorites:
        text = (
            "❤️ *Избранное пусто*\n\n"
            "Добавляй треки кнопкой 🤍 в результатах поиска!"
        )
        if edit:
            await message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
        else:
            await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return

    text = f"❤️ *Любимые треки* ({len(favorites)} шт):\n\n"
    keyboard = []

    for i, track in enumerate(favorites, 1):
        text += f"{i}. 🎵 *{track['track_name']}* — {track['artist']}\n"
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 {track['track_name'][:25]}",
                callback_data=f"fav_remove:{track['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("🌊 Моя Волна (рекомендации)", callback_data="wave_start")
    ])

    if edit:
        await message.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def add_favorite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить/убрать из избранного"""
    query = update.callback_query
    await query.answer()

    # Парсим данные из callback_data
    # Формат: "fav_add:VIDEO_ID:ARTIST:TRACK_NAME"
    parts = query.data.split(':', 3)
    if len(parts) < 4:
        await query.answer("❌ Ошибка данных", show_alert=True)
        return

    _, video_id, artist, track_name = parts

    # Получаем URL из кэша
    youtube_url = None
    if 'track_cache' in context.bot_data:
        cached = context.bot_data['track_cache'].get(video_id, {})
        youtube_url = cached.get('url')
        thumbnail = cached.get('thumbnail')
        duration = cached.get('duration')
    else:
        thumbnail = None
        duration = None

    # Проверяем, уже в избранном?
    if is_favorite(track_name, artist):
        await query.answer("✅ Уже в избранном!", show_alert=False)
        return

    success = add_favorite(
        track_name=track_name,
        artist=artist,
        youtube_url=youtube_url,
        thumbnail_url=thumbnail,
        duration=duration
    )

    if success:
        await query.answer("❤️ Добавлено в избранное!", show_alert=False)

        # Обновляем кнопку
        try:
            keyboard = query.message.reply_markup.inline_keyboard
            new_keyboard = []
            for row in keyboard:
                new_row = []
                for btn in row:
                    if btn.callback_data == query.data:
                        new_row.append(InlineKeyboardButton(
                            "❤️ В избранном",
                            callback_data=f"fav_remove_by_name:{artist}:{track_name}"
                        ))
                    else:
                        new_row.append(btn)
                new_keyboard.append(new_row)

            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(new_keyboard)
            )
        except Exception:
            pass  # Не критично если кнопка не обновилась
    else:
        await query.answer("Уже в избранном!", show_alert=False)


async def remove_favorite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить из избранного"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(':', 1)
    if len(parts) < 2:
        return

    try:
        track_id = int(parts[1])
        remove_favorite(track_id)
        await query.answer("🗑 Удалено из избранного", show_alert=False)

        # Обновляем список избранного
        await show_favorites_list(query.message, edit=True)

    except (ValueError, Exception) as e:
        logger.error(f"Ошибка удаления из избранного: {e}")
        await query.answer("❌ Ошибка", show_alert=True)
