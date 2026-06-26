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

from database import (
    get_favorites, add_favorite, remove_favorite,
    get_top_artists_from_favorites
)
from music import search_youtube_music, download_audio

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
        artist = entry["artist"]
        results = search_youtube_music(f"{artist} similar", max_results=4)
        for t in results:
            if t not in all_tracks:
                all_tracks.append(t)
    return {"tracks": all_tracks[:10], "based_on": [e["artist"] for e in top_artists]}


@app.get("/api/stream/{video_id}")
async def api_stream(video_id: str):
    """Получить прямую ссылку на аудио"""
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        'extractor_args': {
            'youtube': {'player_client': ['android']}
        },
        'noplaylist': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # Ищем лучший аудио формат
            audio_url = None
            formats = info.get('formats', [])
            
            # Сначала ищем m4a
            for f in formats:
                if f.get('ext') == 'm4a' and f.get('url') and f.get('acodec') != 'none':
                    audio_url = f['url']
                    break
            
            # Потом любой аудио
            if not audio_url:
                for f in reversed(formats):
                    if f.get('acodec') not in ('none', None) and f.get('url') and f.get('vcodec') == 'none':
                        audio_url = f['url']
                        break

            # Fallback — прямой url из info
            if not audio_url:
                audio_url = info.get('url')

            if not audio_url:
                raise HTTPException(500, "No audio URL found")

            # Редирект на прямую ссылку
            return RedirectResponse(url=audio_url, status_code=302)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stream error for {video_id}: {e}", exc_info=True)
        raise HTTPException(500, f"Stream error: {str(e)}")


@app.get("/api/download/{video_id}")
async def api_download(video_id: str):
    url = f"https://www.youtube.com/watch?v={video_id}"
    file_path = await download_audio(url, video_id)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(500, "Download failed")
    return FileResponse(file_path, media_type="audio/mpeg", filename=f"{video_id}.mp3")
