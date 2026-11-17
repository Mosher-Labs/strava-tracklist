import json
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from strava_tracklist.config import Settings
from strava_tracklist.service import Tracklister
from strava_tracklist.spotify import Spotify
from strava_tracklist.strava import Strava
from strava_tracklist.tokens import TokenFile

ATHLETE = 42
ACTIVITY = 1001
SECRET = 'hook-secret'
START = datetime(2026, 11, 16, 20, 20, tzinfo=timezone.utc)
PLAYLIST = '6LPHxO7nFb6Px5NfGZqEpH'


def play(title: str, finished: datetime, seconds: int = 180, context: str | None = f"spotify:playlist:{PLAYLIST}"):
    return {
        'played_at': finished.isoformat().replace('+00:00', 'Z'),
        'track': {'name': title, 'duration_ms': seconds * 1000, 'artists': [{'name': f"{title} Band"}]},
        'context': {'uri': context} if context else None,
    }


class FakeApis:
    """Fake Strava and Spotify; records every request."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.description: str | None = 'Felt good.'
        self.elapsed = 2400
        self.plays: list[dict] = []
        self.puts: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append((request.method, path))
        if path == f"/api/v3/activities/{ACTIVITY}":
            if request.method == 'PUT':
                self.description = json.loads(request.content)['description']
                self.puts.append(self.description)
            return httpx.Response(200, json={
                'id': ACTIVITY, 'start_date': START.isoformat().replace('+00:00', 'Z'),
                'elapsed_time': self.elapsed, 'description': self.description,
            })
        if path == '/v1/me/player/recently-played':
            return httpx.Response(200, json={'items': self.plays})
        if path == f"/v1/playlists/{PLAYLIST}":
            return httpx.Response(200, json={'name': 'Run · 2026-11-16 · 150'})
        if path == '/oauth/token':
            return httpx.Response(200, json={
                'access_token': 'new', 'refresh_token': 'r2', 'expires_at': time.time() + 3600,
            })
        return httpx.Response(404, json={})


@pytest.fixture
def apis():
    return FakeApis()


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path, strava_client_id='1', strava_client_secret='s', strava_redirect_uri='http://localhost/x',
        spotify_client_id='c', spotify_redirect_uri='http://127.0.0.1:8888/callback', webhook_secret=SECRET,
    )


@pytest.fixture
async def tracklister(settings, apis):
    future = time.time() + 3600
    strava_tokens = TokenFile(settings.strava_token_path, 'Strava')
    strava_tokens.save({'access_token': 'a', 'refresh_token': 'r', 'expires_at': future, 'athlete_id': ATHLETE})
    spotify_tokens = TokenFile(settings.spotify_token_path, 'Spotify')
    spotify_tokens.save({'access_token': 'a', 'refresh_token': 'r', 'expires_at': future})
    http = httpx.AsyncClient(transport=httpx.MockTransport(apis))
    yield Tracklister(Strava(http, strava_tokens, '1', 's'), Spotify(http, spotify_tokens, 'c'))
    await http.aclose()


def minutes(n: float) -> datetime:
    return START + timedelta(minutes=n)
