"""
FastAPI сервер для Telegram Mini App
"""

import os
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional

from database import get_favorites, add_favorite, remove_favorite, get_top_artists_from_favorites
from music import search_youtube_music, download_audio
from lastfm import build_wave_recommendations, get_similar_tracks

logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "webapp_static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/search")
async def api_search(q: str, limit: int = 5):
    if not q or len(q.strip()) < 2:
        raise HTTPException(400, "Query too short")
    results = search_youtube_music(q.strip(), max_results=limit)
    return {"results": results}


@app.get("/api/favorites")
async def api_favorites():
    return {"favorites": get_favorites(limit=50)}


class FavoriteAdd(BaseModel):
    track_name: str
    artist: str
    youtube_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[str] = None


@app.post("/api/favorites")
async def api_add_favorite(body: FavoriteAdd):
    ok = add_favorite(
        track_name=body.track_name,
        artist=body.artist,
        youtube_url=body.youtube_url,
        thumbnail_url=body.thumbnail_url,
        duration=body.duration,
    )
    return {"added": ok}


@app.delete("/api/favorites/{track_id}")
async def api_remove_favorite(track_id: int):
    remove_favorite(track_id)
    return {"removed": True}


@app.get("/api/wave")
async def api_wave(artist: str = None, track: str = None):
    """
    Умная Волна через Last.fm.
    Если передан artist+track — строим волну на основе текущего трека.
    Иначе — на основе избранного.
    """
    favorites = get_favorites(limit=50)

    # Если играет конкретный трек — строим волну от него
    if artist and track:
        similar = get_similar_tracks(artist, track, limit=15)

        if similar:
            # Ищем каждый похожий трек на YouTube
            already_liked = {
                f"{f['artist'].lower()}:{f['track_name'].lower()}"
                for f in favorites
            }
            results = []
            for sim in similar[:8]:
                key = f"{sim['artist'].lower()}:{sim['name'].lower()}"
                if key in already_liked:
                    continue
                found = search_youtube_music(f"{sim['artist']} {sim['name']}", max_results=1)
                if found:
                    t = found[0]
                    t['match_score'] = sim['match']
                    results.append(t)
                if len(results) >= 6:
                    break

            if results:
                return {
                    "tracks": results,
                    "based_on": f"{artist} — {track}",
                    "mode": "similar"
                }

    # Fallback — на основе избранного
    if not favorites:
        return {"tracks": [], "message": "Добавь треки в избранное для рекомендаций"}

    recs = build_wave_recommendations(favorites)

    results = []
    for rec in recs[:8]:
        found = search_youtube_music(f"{rec['artist']} {rec['name']}", max_results=1)
        if found:
            results.append(found[0])
        if len(results) >= 6:
            break

    if not results:
        # Последний fallback — поиск по топ артистам
        top = get_top_artists_from_favorites(limit=2)
        for entry in top:
            found = search_youtube_music(f"{entry['artist']} best songs", max_results=3)
            results.extend(found)

    return {
        "tracks": results[:8],
        "based_on": ", ".join([f['artist'] for f in favorites[:3]]),
        "mode": "favorites"
    }


@app.get("/api/stream/{track_id:path}")
async def api_stream(track_id: str, url: str = None):
    \"\"\"Стримим аудио — начинаем отдавать пока скачивается\"\"\"
    import asyncio
    import yt_dlp
    from fastapi.responses import StreamingResponse

    output_path = os.path.join(str(Path(__file__).parent / "temp_music"), f"{track_id}.mp3")

    # Уже скачан — отдаём сразу
    if os.path.exists(output_path):
        def iter_cached():
            with open(output_path, 'rb') as f:
                while chunk := f.read(65536):
                    yield chunk
        return StreamingResponse(iter_cached(), media_type="audio/mpeg",
            headers={'Content-Length': str(os.path.getsize(output_path)), 'Accept-Ranges': 'bytes'})

    if not url:
        raise HTTPException(400, "url parameter required")

    # Deezer preview — качаем и сразу проксируем
    if 'deezer' in track_id or 'cdns.dzcdn.net' in url:
        import httpx
        async def stream_deezer():
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                async with client.stream('GET', url) as resp:
                    async for chunk in resp.aiter_bytes(32768):
                        yield chunk
        return StreamingResponse(stream_deezer(), media_type="audio/mpeg")

    # SoundCloud — качаем через yt-dlp в файл, начинаем стримить как только появятся данные
    async def stream_while_downloading():
        import asyncio

        # Запускаем скачивание в фоне
        loop = asyncio.get_event_loop()
        download_task = loop.run_in_executor(None, lambda: _ytdlp_download(url, output_path, track_id))

        # Ждём пока появится файл (макс 15 сек)
        for _ in range(150):
            if os.path.exists(output_path) and os.path.getsize(output_path) > 32768:
                break
            await asyncio.sleep(0.1)

        if not os.path.exists(output_path):
            await download_task
            if not os.path.exists(output_path):
                return

        # Стримим файл пока он скачивается
        sent = 0
        while True:
            if os.path.exists(output_path):
                size = os.path.getsize(output_path)
                if size > sent:
                    with open(output_path, 'rb') as f:
                        f.seek(sent)
                        chunk = f.read(32768)
                    if chunk:
                        sent += len(chunk)
                        yield chunk
                        continue

            # Проверяем завершилось ли скачивание
            if download_task.done():
                break
            await asyncio.sleep(0.05)

    return StreamingResponse(stream_while_downloading(), media_type="audio/mpeg",
        headers={'Cache-Control': 'no-cache'})


def _ytdlp_download(url: str, output_path: str, track_id: str):
    \"\"\"Синхронное скачивание через yt-dlp\"\"\"
    import yt_dlp
    from pathlib import Path
    temp_dir = str(Path(output_path).parent)

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(temp_dir, f"{track_id}.%(ext)s"),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        logger.error(f"yt-dlp download error: {e}")"""

if old in content:
    content = content.replace(old, new)
    print("OK")
else:
    print("NOT FOUND")

with open('/home/claude/music_bot/webapp.py', 'w') as f:
    f.write(content)

@app.get("/api/stream_old/{video_id}")
async def api_stream_old(video_id: str):
    """Старый метод — прямая ссылка"""
    import yt_dlp
    import httpx
    from fastapi.responses import StreamingResponse

    url = f"https://www.youtube.com/watch?v={video_id}"
    cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestaudio/best',
        'noplaylist': True,
    }
    if os.path.exists(cookies_file):
        ydl_opts['cookiefile'] = cookies_file
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])

            audio_url = None
            content_type = 'audio/mp4'

            for f in formats:
                if f.get('ext') == 'm4a' and f.get('url') and f.get('acodec') != 'none':
                    audio_url = f['url']
                    content_type = 'audio/mp4'
                    break
            if not audio_url:
                for f in reversed(formats):
                    if f.get('acodec') not in ('none', None) and f.get('url') and f.get('vcodec') == 'none':
                        audio_url = f['url']
                        ext = f.get('ext', 'mp4')
                        content_type = f'audio/{ext}'
                        break
            if not audio_url:
                audio_url = info.get('url', '')
            if not audio_url:
                raise HTTPException(500, "No audio URL found")

            # Проксируем поток
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.youtube.com/',
            }

            async def stream_audio():
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    async with client.stream('GET', audio_url, headers=headers) as resp:
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            yield chunk

            return StreamingResponse(
                stream_audio(),
                media_type=content_type,
                headers={
                    'Accept-Ranges': 'bytes',
                    'Cache-Control': 'no-cache',
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stream error for {video_id}: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.get("/api/download/{video_id}")
async def api_download(video_id: str):
    url = f"https://www.youtube.com/watch?v={video_id}"
    file_path = await download_audio(url, video_id)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(500, "Download failed")
    return FileResponse(file_path, media_type="audio/mpeg", filename=f"{video_id}.mp3")
