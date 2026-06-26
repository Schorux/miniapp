"""
Last.fm API — получение рекомендаций и похожих треков
Бесплатный API: https://www.last.fm/api/account/create
"""

import logging
import requests
from config import LASTFM_API_KEY

logger = logging.getLogger(__name__)

LASTFM_BASE = "https://ws.audioscrobbler.com/2.0/"


def get_similar_tracks(artist: str, track: str, limit: int = 10) -> list:
    """Получить похожие треки через Last.fm"""
    if not LASTFM_API_KEY or LASTFM_API_KEY == "YOUR_LASTFM_API_KEY":
        return []

    params = {
        'method': 'track.getSimilar',
        'artist': artist,
        'track': track,
        'api_key': LASTFM_API_KEY,
        'format': 'json',
        'limit': limit,
        'autocorrect': 1,
    }

    try:
        response = requests.get(LASTFM_BASE, params=params, timeout=10)
        data = response.json()

        if 'similartracks' not in data:
            return []

        tracks = []
        for t in data['similartracks'].get('track', []):
            tracks.append({
                'name': t.get('name', ''),
                'artist': t['artist'].get('name', '') if isinstance(t.get('artist'), dict) else '',
                'url': t.get('url', ''),
                'match': float(t.get('match', 0)),
            })

        return tracks

    except Exception as e:
        logger.error(f"Last.fm similar tracks error: {e}")
        return []


def get_similar_artists(artist: str, limit: int = 5) -> list:
    """Получить похожих исполнителей"""
    if not LASTFM_API_KEY or LASTFM_API_KEY == "YOUR_LASTFM_API_KEY":
        return []

    params = {
        'method': 'artist.getSimilar',
        'artist': artist,
        'api_key': LASTFM_API_KEY,
        'format': 'json',
        'limit': limit,
        'autocorrect': 1,
    }

    try:
        response = requests.get(LASTFM_BASE, params=params, timeout=10)
        data = response.json()

        if 'similarartists' not in data:
            return []

        return [
            {
                'name': a.get('name', ''),
                'match': float(a.get('match', 0)),
            }
            for a in data['similarartists'].get('artist', [])
        ]

    except Exception as e:
        logger.error(f"Last.fm similar artists error: {e}")
        return []


def get_top_tracks_by_artist(artist: str, limit: int = 5) -> list:
    """Получить топ треков исполнителя"""
    if not LASTFM_API_KEY or LASTFM_API_KEY == "YOUR_LASTFM_API_KEY":
        return []

    params = {
        'method': 'artist.getTopTracks',
        'artist': artist,
        'api_key': LASTFM_API_KEY,
        'format': 'json',
        'limit': limit,
        'autocorrect': 1,
    }

    try:
        response = requests.get(LASTFM_BASE, params=params, timeout=10)
        data = response.json()

        if 'toptracks' not in data:
            return []

        return [
            {
                'name': t.get('name', ''),
                'artist': t['artist'].get('name', '') if isinstance(t.get('artist'), dict) else artist,
            }
            for t in data['toptracks'].get('track', [])
        ]

    except Exception as e:
        logger.error(f"Last.fm top tracks error: {e}")
        return []


def build_wave_recommendations(favorite_tracks: list, already_shown: set = None) -> list:
    """
    Алгоритм «Моей Волны»:
    1. Берём любимые треки
    2. Для каждого находим похожие через Last.fm
    3. Фильтруем уже показанные и лайкнутые
    4. Возвращаем рекомендации с весами
    """
    if already_shown is None:
        already_shown = set()

    # Ключи уже лайкнутых треков (для фильтрации)
    liked_keys = {
        f"{t['artist'].lower()}:{t['track_name'].lower()}"
        for t in favorite_tracks
    }

    recommendations = {}  # ключ → {track_info, score}

    for fav in favorite_tracks[:10]:  # берём последние 10
        artist = fav.get('artist', '')
        track = fav.get('track_name', '')

        if not artist or artist == 'Unknown Artist':
            continue

        similar = get_similar_tracks(artist, track, limit=8)

        for sim in similar:
            key = f"{sim['artist'].lower()}:{sim['name'].lower()}"

            # Пропускаем уже лайкнутые
            if key in liked_keys:
                continue

            # Пропускаем уже показанные в этой сессии
            if key in already_shown:
                continue

            if key in recommendations:
                # Встретился снова — повышаем вес
                recommendations[key]['score'] += sim['match']
                recommendations[key]['count'] += 1
            else:
                recommendations[key] = {
                    'name': sim['name'],
                    'artist': sim['artist'],
                    'score': sim['match'],
                    'count': 1,
                    'key': key,
                }

    # Если Last.fm не дал результатов — берём топ треки похожих исполнителей
    if not recommendations:
        recommendations = _fallback_recommendations(favorite_tracks, liked_keys, already_shown)

    # Сортируем по релевантности (частота + match score)
    sorted_recs = sorted(
        recommendations.values(),
        key=lambda x: x['count'] * 2 + x['score'],
        reverse=True
    )

    return sorted_recs


def _fallback_recommendations(favorite_tracks: list, liked_keys: set, already_shown: set) -> dict:
    """Запасной алгоритм: похожие исполнители → их топ треки"""
    recommendations = {}

    # Берём уникальных исполнителей
    artists = list({t.get('artist', '') for t in favorite_tracks if t.get('artist', '') != 'Unknown Artist'})

    for artist in artists[:3]:
        similar_artists = get_similar_artists(artist, limit=3)

        for sim_artist in similar_artists:
            top_tracks = get_top_tracks_by_artist(sim_artist['name'], limit=3)

            for track in top_tracks:
                key = f"{track['artist'].lower()}:{track['name'].lower()}"

                if key in liked_keys or key in already_shown:
                    continue

                if key not in recommendations:
                    recommendations[key] = {
                        'name': track['name'],
                        'artist': track['artist'],
                        'score': sim_artist['match'],
                        'count': 1,
                        'key': key,
                    }

    return recommendations
