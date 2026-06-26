"""
FastAPI сервер для Telegram Mini App
"""

import os
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import httpx

from database import (
    get_favorites, add_favorite, remove_favorite,
    is_favorite, get_top_artists_from_favorites
)
from music import search_youtube_music

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
async def api_stream(video_id: str, request: Request):
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best',
        'extractor_args': {
            'youtube': {'player_client': ['ios', 'android']}
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            audio_url = None
            audio_mime = 'audio/webm'

            for fmt in reversed(info.get('formats', [])):
                if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none' and fmt.get('url'):
                    audio_url = fmt['url']
                    break

            if not audio_url:
                audio_url = info.get('url')

            if not audio_url:
                raise HTTPException(500, "No audio URL found")

            yt_headers = info.get('http_headers', {
                'User-Agent': 'Mozilla/5.0',
            })

    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
        raise HTTPException(500, str(e))

    range_header = request.headers.get("range")
    proxy_headers = {**yt_headers}
    if range_header:
        proxy_headers["Range"] = range_header

    async def proxy_stream():
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("GET", audio_url, headers=proxy_headers) as resp:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    yield chunk

    # НЕ передаём Content-Length — избегаем ошибки "Too little data"
    response_headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-cache",
    }

    status_code = 206 if range_header else 200

    return StreamingResponse(
        proxy_stream(),
        status_code=status_code,
        media_type=audio_mime,
        headers=response_headers,
    )
