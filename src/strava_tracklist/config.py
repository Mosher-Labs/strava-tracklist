"""Settings read from the environment."""

import os
from dataclasses import dataclass
from pathlib import Path

# Strava always accepts localhost as a redirect, and Spotify needs the exact
# URI registered on its app. Nothing has to serve either address: the CLI asks
# you to paste the URL the browser was sent to.
DEFAULT_STRAVA_REDIRECT_URI = 'http://localhost/exchange_token'
DEFAULT_SPOTIFY_REDIRECT_URI = 'http://127.0.0.1:8888/callback'


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    strava_client_id: str
    strava_client_secret: str
    strava_redirect_uri: str
    spotify_client_id: str
    spotify_redirect_uri: str
    # Path segment of the webhook URL and Strava's verify token. Strava does
    # not sign its events, so this is what keeps strangers from calling it.
    webhook_secret: str
    host: str = '127.0.0.1'
    port: int = 8000

    @property
    def strava_token_path(self) -> Path:
        return self.data_dir / 'strava-token.json'

    @property
    def spotify_token_path(self) -> Path:
        return self.data_dir / 'spotify-token.json'


def _required(name: str) -> str:
    value = os.getenv(name, '').strip()
    if not value:
        raise SystemExit(f"{name} is not set.")
    return value


def load_settings() -> Settings:
    data_dir = Path(os.getenv('STRAVA_TRACKLIST_DATA_DIR', '~/.strava-tracklist')).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        data_dir=data_dir,
        strava_client_id=_required('STRAVA_CLIENT_ID'),
        strava_client_secret=_required('STRAVA_CLIENT_SECRET'),
        strava_redirect_uri=os.getenv('STRAVA_REDIRECT_URI', DEFAULT_STRAVA_REDIRECT_URI).strip(),
        spotify_client_id=_required('SPOTIFY_CLIENT_ID'),
        spotify_redirect_uri=os.getenv('SPOTIFY_REDIRECT_URI', DEFAULT_SPOTIFY_REDIRECT_URI).strip(),
        webhook_secret=_required('STRAVA_TRACKLIST_WEBHOOK_SECRET'),
        host=os.getenv('STRAVA_TRACKLIST_HOST', '127.0.0.1'),
        port=int(os.getenv('STRAVA_TRACKLIST_PORT', '8000')),
    )
