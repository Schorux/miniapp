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
    """
    Получаем прямой URL от yt-dlp и проксируем его через сервер.
    Музыка начинает играть сразу — без скачивания на диск.
    """
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

            # Ищем лучший аудио формат
            for fmt in reversed(info.get('formats', [])):
                if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none' and fmt.get('url'):
                    audio_url = fmt['url']
                    audio_mime = fmt.get('http_headers', {}).get('Content-Type', 'audio/webm')
                    break

            if not audio_url:
                audio_url = info.get('url')

            if not audio_url:
                raise HTTPException(500, "No audio URL found")

            headers = info.get('http_headers', {
                'User-Agent': 'Mozilla/5.0',
            })

    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
        raise HTTPException(500, str(e))

    # Проксируем запрос — браузер получает аудио через наш сервер
    range_header = request.headers.get("range", "bytes=0-")

    async def proxy_stream():
        proxy_headers = {**headers, "Range": range_header}
        async with httpx.AsyncClient(timeout=30) as client:
            async with client.stream("GET", audio_url, headers=proxy_headers) as resp:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    yield chunk

    # Получаем размер файла для заголовков
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            head = await client.head(audio_url, headers=headers)
            content_length = head.headers.get("content-length", "")
            content_range = head.headers.get("content-range", "")
    except Exception:
        content_length = ""
        content_range = ""

    response_headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-cache",
    }
    if content_length:
        response_headers["Content-Length"] = content_length
    if range_header and range_header != "bytes=0-":
        status_code = 206
        if content_range:
            response_headers["Content-Range"] = content_range
    else:
        status_code = 200

    return StreamingResponse(
        proxy_stream(),
        status_code=status_code,
        media_type=audio_mime,
        headers=response_headers,
    )
