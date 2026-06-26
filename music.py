"""
Поиск и скачивание музыки через yt-dlp (SoundCloud + Deezer fallback)
"""

import os
import asyncio
import logging
from pathlib import Path
from config import TEMP_MUSIC_DIR, MAX_SEARCH_RESULTS

logger = logging.getLogger(__name__)

Path(TEMP_MUSIC_DIR).mkdir(parents=True, exist_ok=True)

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}


def search_youtube_music(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list:
    """Поиск через SoundCloud с Deezer fallback"""
    results = _search_soundcloud(query, max_results)
    if not results:
        logger.info(f"SoundCloud вернул 0 — пробуем Deezer для: {query}")
        results = _search_deezer(query, max_results)
    return results


def _search_soundcloud(query: str, max_results: int) -> list:
    import yt_dlp
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'http_headers': BROWSER_HEADERS,
    }
    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"scsearch{max_results}:{query}", download=False)
            if not info or 'entries' not in info:
                return []
            for entry in info['entries']:
                if not entry:
                    continue
                title = entry.get('title', 'Unknown')
                artist, track = parse_artist_track(title)
                duration_sec = entry.get('duration', 0)
                results.append({
                    'id': entry.get('id', ''),
                    'title': title,
                    'track_name': track,
                    'artist': artist,
                    'url': entry.get('url') or entry.get('webpage_url', ''),
                    'thumbnail': entry.get('thumbnail', ''),
                    'duration': format_duration(duration_sec),
                    'duration_sec': duration_sec,
                    'channel': entry.get('uploader', ''),
                    'source': 'soundcloud',
                })
    except Exception as e:
        logger.error(f"SoundCloud поиск ошибка: {e}")
    return results


def _search_deezer(query: str, max_results: int) -> list:
    import requests
    results = []
    try:
        r = requests.get(
            'https://api.deezer.com/search',
            params={'q': query, 'limit': max_results},
            timeout=10
        )
        data = r.json()
        for t in data.get('data', []):
            duration_sec = t.get('duration', 0)
            results.append({
                'id': f"deezer_{t['id']}",
                'title': f"{t['artist']['name']} - {t['title']}",
                'track_name': t.get('title', ''),
                'artist': t['artist'].get('name', ''),
                'url': t.get('link', ''),
                'thumbnail': t.get('album', {}).get('cover_medium', ''),
                'duration': format_duration(duration_sec),
                'duration_sec': duration_sec,
                'channel': t['artist'].get('name', ''),
                'preview_url': t.get('preview', ''),  # 30 сек превью бесплатно
                'source': 'deezer',
            })
    except Exception as e:
        logger.error(f"Deezer поиск ошибка: {e}")
    return results


async def download_audio(url_or_id: str, track_id: str) -> str | None:
    """Скачать аудио — SoundCloud напрямую, Deezer через превью"""
    output_path = os.path.join(TEMP_MUSIC_DIR, f"{track_id}.mp3")

    if os.path.exists(output_path):
        return output_path

    # Deezer — скачиваем 30 сек превью напрямую
    if track_id.startswith('deezer_'):
        return await _download_deezer_preview(url_or_id, output_path)

    # SoundCloud — через yt-dlp
    return await _download_soundcloud(url_or_id, track_id, output_path)


async def _download_soundcloud(url: str, track_id: str, output_path: str) -> str | None:
    import yt_dlp

    ydl_opts = {
        'quiet': False,
        'no_warnings': False,
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(TEMP_MUSIC_DIR, f"{track_id}.%(ext)s"),
        'http_headers': BROWSER_HEADERS,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: _download_sync(url, ydl_opts))

        if os.path.exists(output_path):
            return output_path

        temp_dir = Path(TEMP_MUSIC_DIR)
        for f in sorted(temp_dir.glob(f"{track_id}*"), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.suffix in ('.mp3', '.m4a', '.opus', '.webm', '.ogg'):
                if f.suffix != '.mp3':
                    f.rename(output_path)
                    return output_path
                return str(f)

        logger.error(f"Файл не найден после скачивания")
        return None

    except Exception as e:
        logger.error(f"Ошибка скачивания {url}: {e}", exc_info=True)
        return None


async def _download_deezer_preview(preview_url: str, output_path: str) -> str | None:
    """Скачать 30 сек превью с Deezer"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(preview_url, headers=BROWSER_HEADERS)
            if r.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(r.content)
                return output_path
    except Exception as e:
        logger.error(f"Deezer preview download error: {e}")
    return None


def _download_sync(url: str, opts: dict):
    import yt_dlp
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])


def cleanup_old_files(max_files: int = 20):
    temp_dir = Path(TEMP_MUSIC_DIR)
    files = sorted(temp_dir.glob("*.mp3"), key=lambda f: f.stat().st_mtime)
    if len(files) > max_files:
        for old_file in files[:-max_files]:
            old_file.unlink()
            logger.info(f"Удалён старый файл: {old_file.name}")


def parse_artist_track(title: str) -> tuple[str, str]:
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
    if not seconds:
        return '?:??'
    seconds = int(seconds)
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"
