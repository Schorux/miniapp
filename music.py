"""
Поиск и скачивание музыки через yt-dlp
"""

import os
import asyncio
import logging
from pathlib import Path
from config import TEMP_MUSIC_DIR, MAX_SEARCH_RESULTS

logger = logging.getLogger(__name__)

# Создаём папку для временных файлов
Path(TEMP_MUSIC_DIR).mkdir(parents=True, exist_ok=True)

# Общие опции для обхода блокировок YouTube
BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}


def search_youtube_music(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list:
    """
    Поиск музыки на YouTube Music.
    Возвращает список треков с метаданными.
    """
    import yt_dlp

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'default_search': f'ytsearch{max_results}',
        'format': 'bestaudio/best',
        'http_headers': BROWSER_HEADERS,
    }

    results = []
    search_query = f"ytsearch{max_results}:{query}"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)

            if 'entries' in info:
                for entry in info['entries']:
                    if entry is None:
                        continue

                    title = entry.get('title', 'Unknown')
                    artist, track = parse_artist_track(title)

                    duration_sec = entry.get('duration', 0)
                    duration_str = format_duration(duration_sec)

                    results.append({
                        'id': entry.get('id', ''),
                        'title': title,
                        'track_name': track,
                        'artist': artist,
                        'url': f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                        'thumbnail': entry.get('thumbnail', ''),
                        'duration': duration_str,
                        'duration_sec': duration_sec,
                        'channel': entry.get('channel', entry.get('uploader', '')),
                    })

    except Exception as e:
        logger.error(f"Ошибка поиска: {e}", exc_info=True)

    return results


async def download_audio(youtube_url: str, video_id: str) -> str | None:
    """
    Скачать аудио из YouTube видео.
    Возвращает путь к MP3 файлу или None при ошибке.
    """
    output_path = os.path.join(TEMP_MUSIC_DIR, f"{video_id}.mp3")

    # Если уже скачан — не скачиваем снова
    if os.path.exists(output_path):
        return output_path

    cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')

    ydl_opts = {
        'quiet': False,
        'no_warnings': False,
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(TEMP_MUSIC_DIR, f"{video_id}.%(ext)s"),
        'http_headers': BROWSER_HEADERS,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    if os.path.exists(cookies_file):
        ydl_opts['cookiefile'] = cookies_file
        logger.info(f"download_audio: using cookies {cookies_file}")
    else:
        logger.warning(f"download_audio: cookies.txt NOT FOUND at {cookies_file}")

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: _download_sync(youtube_url, ydl_opts))

        # Ищем mp3
        if os.path.exists(output_path):
            return output_path

        # yt-dlp иногда оставляет другое расширение
        temp_dir = Path(TEMP_MUSIC_DIR)
        for f in sorted(temp_dir.glob(f"{video_id}*"), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.suffix in ('.mp3', '.m4a', '.opus', '.webm', '.ogg'):
                if f.suffix != '.mp3':
                    f.rename(output_path)
                    return output_path
                return str(f)

        logger.error(f"Файл не найден после скачивания в {TEMP_MUSIC_DIR}")
        return None

    except Exception as e:
        logger.error(f"Ошибка скачивания {youtube_url}: {e}", exc_info=True)
        return None


def _download_sync(url: str, opts: dict):
    """Синхронная версия для запуска в executor"""
    import yt_dlp
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])


def cleanup_old_files(max_files: int = 20):
    """Удалить старые MP3 файлы, чтобы не засорять диск"""
    temp_dir = Path(TEMP_MUSIC_DIR)
    files = sorted(temp_dir.glob("*.mp3"), key=lambda f: f.stat().st_mtime)

    if len(files) > max_files:
        for old_file in files[:-max_files]:
            old_file.unlink()
            logger.info(f"Удалён старый файл: {old_file.name}")


def parse_artist_track(title: str) -> tuple[str, str]:
    """
    Попытаться разобрать 'Artist - Track Name' из заголовка YouTube.
    """
    for suffix in ['(Official Video)', '(Official Music Video)', '(Lyric Video)',
                   '[Official Video]', '(Audio)', '[Audio]', '(Official Audio)',
                   '(HD)', '4K', 'Official', 'Lyrics']:
        title = title.replace(suffix, '').strip()

    if ' - ' in title:
        parts = title.split(' - ', 1)
        return parts[0].strip(), parts[1].strip()

    if ' – ' in title:
        parts = title.split(' – ', 1)
        return parts[0].strip(), parts[1].strip()

    return 'Unknown Artist', title.strip()


def format_duration(seconds) -> str:
    """Форматировать секунды в MM:SS"""
    if not seconds:
        return '?:??'
    seconds = int(seconds)
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"
