"""
База данных — все операции с SQLite
"""

import sqlite3
from datetime import datetime
from config import DB_PATH


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # результаты как словари
    return conn


def init_db():
    import os
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else '.', exist_ok=True)
    """Создаём все таблицы при первом запуске"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_name TEXT NOT NULL,
            artist TEXT NOT NULL,
            youtube_url TEXT,
            thumbnail_url TEXT,
            duration TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS listen_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_name TEXT NOT NULL,
            artist TEXT NOT NULL,
            listened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS recommendations_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            based_on_artist TEXT NOT NULL,
            recommended_track TEXT NOT NULL,
            recommended_artist TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")


# ─── FAVORITES ────────────────────────────────────────────────


def add_favorite(track_name: str, artist: str, youtube_url: str = None,
                 thumbnail_url: str = None, duration: str = None) -> bool:
    """Добавить трек в избранное. Возвращает False если уже есть."""
    if is_favorite(track_name, artist):
        return False

    conn = get_connection()
    conn.execute(
        "INSERT INTO favorites (track_name, artist, youtube_url, thumbnail_url, duration) "
        "VALUES (?, ?, ?, ?, ?)",
        (track_name, artist, youtube_url, thumbnail_url, duration)
    )
    conn.commit()
    conn.close()
    return True


def remove_favorite(track_id: int):
    """Удалить трек из избранного по ID"""
    conn = get_connection()
    conn.execute("DELETE FROM favorites WHERE id = ?", (track_id,))
    conn.commit()
    conn.close()


def is_favorite(track_name: str, artist: str) -> bool:
    """Проверить, есть ли трек в избранном"""
    conn = get_connection()
    result = conn.execute(
        "SELECT id FROM favorites WHERE LOWER(track_name) = LOWER(?) AND LOWER(artist) = LOWER(?)",
        (track_name, artist)
    ).fetchone()
    conn.close()
    return result is not None


def get_favorites(limit: int = 50) -> list:
    """Получить список любимых треков"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM favorites ORDER BY added_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_artists_from_favorites(limit: int = 10) -> list:
    """Получить самых частых исполнителей из избранного"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT artist, COUNT(*) as count 
           FROM favorites 
           GROUP BY LOWER(artist) 
           ORDER BY count DESC 
           LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_favorites(limit: int = 10) -> list:
    """Последние добавленные треки для рекомендаций"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM favorites ORDER BY added_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── HISTORY ──────────────────────────────────────────────────


def add_to_history(track_name: str, artist: str):
    """Записать прослушивание"""
    conn = get_connection()
    conn.execute(
        "INSERT INTO listen_history (track_name, artist) VALUES (?, ?)",
        (track_name, artist)
    )
    conn.commit()
    conn.close()


# ─── CACHE ────────────────────────────────────────────────────


def cache_recommendations(based_on_artist: str, tracks: list):
    """Сохранить рекомендации в кэш"""
    conn = get_connection()
    # Удаляем старый кэш для этого исполнителя
    conn.execute(
        "DELETE FROM recommendations_cache WHERE based_on_artist = ?",
        (based_on_artist,)
    )
    for track in tracks:
        conn.execute(
            "INSERT INTO recommendations_cache (based_on_artist, recommended_track, recommended_artist) "
            "VALUES (?, ?, ?)",
            (based_on_artist, track['name'], track['artist'])
        )
    conn.commit()
    conn.close()


def get_cached_recommendations(based_on_artist: str, max_age_hours: int = 24) -> list:
    """Получить рекомендации из кэша (если не старше max_age_hours)"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM recommendations_cache 
           WHERE based_on_artist = ? 
           AND created_at > datetime('now', ? || ' hours')""",
        (based_on_artist, f'-{max_age_hours}')
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Инициализируем БД при импорте
init_db()
