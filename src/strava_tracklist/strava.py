"""Strava OAuth, activities, and webhook subscriptions."""

import time
from urllib.parse import urlencode

import httpx

from strava_tracklist.tokens import AuthError, TokenFile

AUTH_URL = 'https://www.strava.com/oauth/authorize'
TOKEN_URL = 'https://www.strava.com/oauth/token'
API = 'https://www.strava.com/api/v3'
# Read private activities too, and edit their descriptions.
SCOPES = 'read,activity:read_all,activity:write'
_EXPIRY_SKEW_SECONDS = 60


def authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    return AUTH_URL + '?' + urlencode(
        {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'approval_prompt': 'auto',
            'scope': SCOPES,
            'state': state,
        }
    )


async def _post_token(http: httpx.AsyncClient, data: dict) -> dict:
    response = await http.post(TOKEN_URL, data=data)
    if response.status_code != 200:
        # Strava's error body names the bad field; it never echoes the secret.
        raise AuthError(f"Strava token request failed ({response.status_code}): {response.text[:300]}")
    return response.json()


class Strava:
    def __init__(self, http: httpx.AsyncClient, tokens: TokenFile, client_id: str, client_secret: str):
        self._http = http
        self._tokens = tokens
        self._client_id = client_id
        self._client_secret = client_secret

    async def exchange(self, code: str) -> dict:
        payload = await _post_token(
            self._http,
            {
                'client_id': self._client_id,
                'client_secret': self._client_secret,
                'code': code,
                'grant_type': 'authorization_code',
            },
        )
        self._save(payload, athlete_id=payload['athlete']['id'])
        return payload['athlete']

    def _save(self, payload: dict, athlete_id: int) -> None:
        self._tokens.save(
            {
                'access_token': payload['access_token'],
                'refresh_token': payload['refresh_token'],
                'expires_at': payload['expires_at'],
                'athlete_id': athlete_id,
            }
        )

    @property
    def athlete_id(self) -> int:
        return self._tokens.load()['athlete_id']

    async def _access_token(self) -> str:
        data = self._tokens.load()
        if data['expires_at'] - _EXPIRY_SKEW_SECONDS > time.time():
            return data['access_token']
        # Strava may rotate the refresh token; always keep the newest one.
        payload = await _post_token(
            self._http,
            {
                'client_id': self._client_id,
                'client_secret': self._client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': data['refresh_token'],
            },
        )
        self._save(payload, athlete_id=data['athlete_id'])
        return payload['access_token']

    async def _request(self, method: str, path: str, **kwargs) -> dict | list:
        headers = {'Authorization': f"Bearer {await self._access_token()}"}
        response = await self._http.request(method, API + path, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    async def activity(self, activity_id: int) -> dict:
        return await self._request('GET', f"/activities/{activity_id}")

    async def recent_activities(self, count: int = 10) -> list:
        return await self._request('GET', '/athlete/activities', params={'per_page': count})

    async def set_description(self, activity_id: int, description: str) -> None:
        await self._request('PUT', f"/activities/{activity_id}", json={'description': description})

    # Subscriptions are per app and authenticate with the app's secret, not a user token.
    async def subscribe(self, callback_url: str, verify_token: str) -> dict:
        response = await self._http.post(
            f"{API}/push_subscriptions",
            data={
                'client_id': self._client_id,
                'client_secret': self._client_secret,
                'callback_url': callback_url,
                'verify_token': verify_token,
            },
        )
        if response.status_code >= 400:
            raise AuthError(f"Subscription failed ({response.status_code}): {response.text[:300]}")
        return response.json()

    async def subscriptions(self) -> list:
        response = await self._http.get(
            f"{API}/push_subscriptions",
            params={'client_id': self._client_id, 'client_secret': self._client_secret},
        )
        response.raise_for_status()
        return response.json()
