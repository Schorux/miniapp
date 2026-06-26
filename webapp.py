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
import aiofiles

from database import (
    get_favorites, add_favorite, remove_favorite,
    is_favorite, get_top_artists_from_favorites
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

@app.get("/api/download/{video_id}")
async def api_download(video_id: str, request: Request):
    url = f"https://www.youtube.com/watch?v={video_id}"
    file_path = await download_audio(url, video_id)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(500, "Download failed")

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    if range_header:
        start, end = range_header.replace("bytes=", "").split("-")
        start = int(start)
        end = int(end) if end else file_size - 1
        chunk_size = end - start + 1

        async def stream_range():
            async with aiofiles.open(file_path, "rb") as f:
                await f.seek(start)
                data = await f.read(chunk_size)
                yield data

        return StreamingResponse(
            stream_range(), status_code=206, media_type="audio/mpeg",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
            }
        )

    return FileResponse(
        file_path, media_type="audio/mpeg",
        headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)}
    )
