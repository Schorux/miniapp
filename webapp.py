"""
FastAPI сервер для Telegram Mini App
"""

import os
import logging
import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import Response
from pydantic import BaseModel

from database import (
    get_favorites, add_favorite, remove_favorite,
    get_top_artists_from_favorites
)
from music import search_youtube_music

logger = logging.getLogger(__name__)

CACHE_DIR = Path("/tmp/audio_cache")
CACHE_DIR.mkdir(exist_ok=True)

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
    youtube_url: str = None
    thumbnail_url: str = None
    duration: str = None

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
async def api_wave():
    top_artists = get_top_artists_from_favorites(limit=3)
    if not top_artists:
        return {"tracks": [], "message": "Добавь треки в избранное для рекомендаций"}
    all_tracks = []
    for entry in top_artists[:2]:
        results = search_youtube_music(f"{entry['artist']} similar", max_results=4)
        for t in results:
            if t not in all_tracks:
                all_tracks.append(t)
    return {"tracks": all_tracks[:10], "based_on": [e["artist"] for e in top_artists]}

@app.get("/api/audio/{video_id}")
async def api_audio(video_id: str):
    """Скачиваем MP3 в /tmp и отдаём как байты"""
    import yt_dlp

    cache_file = CACHE_DIR / f"{video_id}.mp3"

    # Если уже скачан — отдаём сразу
    if not cache_file.exists():
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'bestaudio/best',
            'outtmpl': str(CACHE_DIR / f"{video_id}.%(ext)s"),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
        }
        try:
            loop = asyncio.get_event_loop()
            def download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
            await loop.run_in_executor(None, download)
        except Exception as e:
            logger.error(f"Download error: {e}")
            raise HTTPException(500, f"Download failed: {e}")

    if not cache_file.exists():
        raise HTTPException(500, "File not found after download")

    # Читаем и отдаём весь файл как байты — без Content-Length проблем
    data = cache_file.read_bytes()
    return Response(
        content=data,
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=3600"}
    )
