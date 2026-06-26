"""
🌊 Моя Волна — автоматически скачивает и присылает MP3
"""

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database import get_recent_favorites, add_favorite, is_favorite
from lastfm import build_wave_recommendations
from music import search_youtube_music, download_audio

logger = logging.getLogger(__name__)


async def wave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запустить Мою Волну"""
    context.user_data['wave_shown'] = set()
    context.user_data['wave_recommendations'] = []
    context.user_data['wave_active'] = True
    await send_wave_track(update.message, context)


async def wave_next_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопки под треком"""
    query = update.callback_query
    await query.answer()

    action = query.data

    if action == "wave_like":
        current = context.user_data.get('wave_current')
        if current and not is_favorite(current['name'], current['artist']):
            add_favorite(track_name=current['name'], artist=current['artist'])
            await query.answer("❤️ Добавлено в избранное!", show_alert=False)
            # Сбрасываем кэш — новый лайк улучшает рекомендации
            context.user_data['wave_recommendations'] = []

        # Убираем кнопки у предыдущего трека
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        await send_wave_track(query.message, context, reply=True)

    elif action == "wave_next":
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await send_wave_track(query.message, context, reply=True)

    elif action == "wave_stop":
        context.user_data['wave_active'] = False
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await query.message.reply_text("⏹ Волна остановлена. /wave — запустить снова.")


async def send_wave_track(message, context: ContextTypes.DEFAULT_TYPE, reply: bool = False):
    """Получить следующий трек, скачать и отправить как MP3"""

    favorites = get_recent_favorites(limit=10)
    if not favorites:
        await message.reply_text(
            "🌊 *Моя Волна*\n\nСначала добавь треки в ❤️ Избранное!\n"
            "Скинь MP3 в чат или найди через поиск.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Получаем пул рекомендаций
    recommendations = context.user_data.get('wave_recommendations', [])
    shown = context.user_data.get('wave_shown', set())

    if not recommendations:
        status = await message.reply_text("🌊 Подбираю музыку...")
        recommendations = build_wave_recommendations(favorites, already_shown=shown)

        if not recommendations:
            # Fallback: берём треки похожих исполнителей через YouTube
            recommendations = await _youtube_fallback(favorites, shown)

        context.user_data['wave_recommendations'] = recommendations

        try:
            await status.delete()
        except Exception:
            pass

    if not recommendations:
        await message.reply_text(
            "😕 Не удалось подобрать треки.\n"
            "Добавь больше треков в избранное или укажи LASTFM_API_KEY в config.py"
        )
        return

    # Берём следующий трек
    track = recommendations.pop(0)
    context.user_data['wave_recommendations'] = recommendations
    context.user_data['wave_current'] = track

    shown.add(track.get('key', f"{track['artist']}:{track['name']}"))
    context.user_data['wave_shown'] = shown

    # Ищем на YouTube
    query = f"{track['artist']} {track['name']}"
    status = await message.reply_text(f"⬇️ Скачиваю: *{track['name']}* — {track['artist']}...", parse_mode=ParseMode.MARKDOWN)

    search_results = search_youtube_music(query, max_results=1)

    if not search_results:
        try:
            await status.delete()
        except Exception:
            pass
        await message.reply_text(f"😕 Не нашёл: {query}\nПропускаю...")
        # Пробуем следующий трек автоматически
        await send_wave_track(message, context, reply=True)
        return

    result = search_results[0]
    audio_path = await download_audio(result['url'], result['id'])

    try:
        await status.delete()
    except Exception:
        pass

    if not audio_path:
        await message.reply_text(f"😕 Не удалось скачать. Пропускаю...")
        await send_wave_track(message, context, reply=True)
        return

    # Кнопки под треком
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("❤️ Лайк", callback_data="wave_like"),
        InlineKeyboardButton("⏭ Следующий", callback_data="wave_next"),
        InlineKeyboardButton("⏹ Стоп", callback_data="wave_stop"),
    ]])

    # Отправляем MP3
    with open(audio_path, 'rb') as audio_file:
        await message.reply_audio(
            audio=audio_file,
            title=result['track_name'],
            performer=result['artist'],
            duration=result.get('duration_sec'),
            reply_markup=keyboard
        )


async def _youtube_fallback(favorites: list, shown: set) -> list:
    """Если Last.fm недоступен — ищем похожее на YouTube"""
    import random
    results = []

    for fav in favorites[:3]:
        artist = fav.get('artist', '')
        if not artist or artist == 'Unknown Artist':
            continue

        tracks = search_youtube_music(f"{artist} mix similar", max_results=3)
        for t in tracks:
            key = f"{t['artist'].lower()}:{t['track_name'].lower()}"
            if key not in shown:
                results.append({
                    'name': t['track_name'],
                    'artist': t['artist'],
                    'score': 0.5,
                    'count': 1,
                    'key': key,
                })

    random.shuffle(results)
    return results
