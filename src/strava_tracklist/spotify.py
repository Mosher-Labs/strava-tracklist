"""Spotify login (authorization code with PKCE) and the two reads this service needs."""

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx

from strava_tracklist.tokens import AuthError, TokenFile

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API = 'https://api.spotify.com/v1'
# Recently played tracks, and the names of private playlists they came from.
SCOPES = ('user-read-recently-played', 'playlist-read-private')
_EXPIRY_SKEW_SECONDS = 60


def new_verifier() -> str:
    return secrets.token_urlsafe(64)


def challenge_for(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


def authorize_url(client_id: str, redirect_uri: str, verifier: str, state: str) -> str:
    return AUTH_URL + '?' + urlencode(
        {
            'client_id': client_id,
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'scope': ' '.join(SCOPES),
            'code_challenge_method': 'S256',
            'code_challenge': challenge_for(verifier),
            'state': state,
        }
    )


class Spotify:
    def __init__(self, http: httpx.AsyncClient, tokens: TokenFile, client_id: str):
        self._http = http
        self._tokens = tokens
        self._client_id = client_id

    async def _post_token(self, data: dict) -> dict:
        response = await self._http.post(TOKEN_URL, data={**data, 'client_id': self._client_id})
        if response.status_code != 200:
            raise AuthError(f"Spotify token request failed ({response.status_code}): {response.text[:300]}")
        return response.json()

    def _save(self, payload: dict, previous_refresh: str | None = None) -> None:
        # Spotify may leave refresh_token out of a refresh response.
        refresh = payload.get('refresh_token') or previous_refresh
        if not refresh:
            raise AuthError('Spotify returned no refresh token.')
        self._tokens.save(
            {
                'access_token': payload['access_token'],
                'refresh_token': refresh,
                'expires_at': time.time() + int(payload.get('expires_in', 3600)),
            }
        )

    async def exchange(self, code: str, redirect_uri: str, verifier: str) -> None:
        payload = await self._post_token(
            {
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri,
                'code_verifier': verifier,
            }
        )
        self._save(payload)

    async def _access_token(self) -> str:
        data = self._tokens.load()
        if data['expires_at'] - _EXPIRY_SKEW_SECONDS > time.time():
            return data['access_token']
        payload = await self._post_token({'grant_type': 'refresh_token', 'refresh_token': data['refresh_token']})
        self._save(payload, data['refresh_token'])
        return payload['access_token']

    async def _get(self, path: str, **params) -> dict:
        headers = {'Authorization': f"Bearer {await self._access_token()}"}
        response = await self._http.get(API + path, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    async def recently_played(self, after_ms: int) -> list[dict]:
        """Up to 50 plays that finished after after_ms. Spotify keeps no more history than this."""
        return (await self._get('/me/player/recently-played', limit=50, after=after_ms)).get('items', [])

    async def playlist_name(self, playlist_id: str) -> str | None:
        try:
            return (await self._get(f"/playlists/{playlist_id}", fields='name')).get('name')
        except httpx.HTTPStatusError:
            return None  # deleted, or someone else's private playlist: link it without a name
