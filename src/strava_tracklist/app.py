"""The webhook server Strava calls when an activity is created or changed."""

import hmac
import logging

import httpx
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from strava_tracklist.config import Settings, load_settings
from strava_tracklist.service import Tracklister
from strava_tracklist.spotify import Spotify
from strava_tracklist.strava import Strava
from strava_tracklist.tokens import TokenFile

log = logging.getLogger('strava_tracklist')


def build_tracklister(settings: Settings, http: httpx.AsyncClient) -> Tracklister:
    return Tracklister(
        Strava(
            http,
            TokenFile(settings.strava_token_path, 'Strava'),
            settings.strava_client_id,
            settings.strava_client_secret,
        ),
        Spotify(http, TokenFile(settings.spotify_token_path, 'Spotify'), settings.spotify_client_id),
    )


def create_app(settings: Settings, tracklister: Tracklister) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def check(secret: str) -> None:
        if not hmac.compare_digest(secret.encode(), settings.webhook_secret.encode()):
            raise HTTPException(status_code=404)

    @app.get('/healthz')
    async def healthz():
        return PlainTextResponse('ok')

    @app.get('/readyz')
    async def readyz():
        missing = [p.name for p in (settings.strava_token_path, settings.spotify_token_path) if not p.is_file()]
        if missing:
            return JSONResponse({'status': 'not logged in', 'missing': missing}, status_code=503)
        return {'status': 'ready'}

    # Strava's check when the subscription is created.
    @app.get('/webhook/{secret}')
    async def verify(
        secret: str,
        mode: str = Query(alias='hub.mode'),
        challenge: str = Query(alias='hub.challenge'),
        verify_token: str = Query(alias='hub.verify_token'),
    ):
        check(secret)
        check(verify_token)
        if mode != 'subscribe':
            raise HTTPException(status_code=400)
        return {'hub.challenge': challenge}

    # Strava wants a 200 within two seconds, so the work runs after the reply.
    # Events are not signed: the secret path is the only check, and the
    # activity is always re-read from Strava rather than trusted from the body.
    @app.post('/webhook/{secret}')
    async def event(secret: str, request: Request, background: BackgroundTasks):
        check(secret)
        body = await request.json()
        background.add_task(_handle, tracklister, body)
        return {'ok': True}

    return app


async def _handle(tracklister: Tracklister, event: dict) -> None:
    try:
        log.info('event %s %s: %s', event.get('aspect_type'), event.get('object_id'),
                 await tracklister.handle_event(event))
    except Exception:
        log.exception('event %s %s failed', event.get('aspect_type'), event.get('object_id'))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    settings = load_settings()
    http = httpx.AsyncClient(timeout=30)
    app = create_app(settings, build_tracklister(settings, http))
    # The webhook URL carries the secret, so keep it out of the access log.
    uvicorn.run(app, host=settings.host, port=settings.port, access_log=False)


if __name__ == '__main__':
    main()
