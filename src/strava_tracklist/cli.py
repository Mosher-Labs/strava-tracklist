"""Setup and manual runs: ``strava-tracklist-cli <command>``.

Logins take two runs so they work through ``kubectl exec`` without a
terminal. The first prints a URL to approve in a browser. The browser is then
sent to a localhost address that nothing serves, so the page fails to load;
run the command again with that address.
"""

import argparse
import asyncio
import json
import secrets
from urllib.parse import parse_qs, urlparse

import httpx

from strava_tracklist import spotify as spotify_mod
from strava_tracklist import strava as strava_mod
from strava_tracklist.app import build_tracklister
from strava_tracklist.config import Settings, load_settings
from strava_tracklist.tokens import AuthError


def _code(redirected: str, expected_state: str) -> str:
    query = parse_qs(urlparse(redirected.strip()).query)
    if 'error' in query:
        raise AuthError(f"Login refused: {query['error'][0]}")
    if query.get('state', [''])[0] != expected_state:
        raise AuthError('State mismatch: use the URL from the latest login attempt.')
    code = query.get('code', [''])[0]
    if not code:
        raise AuthError('No code in that URL.')
    return code


def _pending(settings: Settings, service: str):
    return settings.data_dir / f"pending-{service}.json"


async def _auth(settings: Settings, service: str, redirected: str | None) -> None:
    pending = _pending(settings, service)
    if redirected is None:
        state = secrets.token_urlsafe(16)
        data = {'state': state}
        if service == 'spotify':
            data['verifier'] = spotify_mod.new_verifier()
            url = spotify_mod.authorize_url(
                settings.spotify_client_id, settings.spotify_redirect_uri, data['verifier'], state
            )
        else:
            url = strava_mod.authorize_url(settings.strava_client_id, settings.strava_redirect_uri, state)
        pending.write_text(json.dumps(data))
        pending.chmod(0o600)
        print(f"Open this URL, approve, then run this command again with the address the browser lands on:\n\n{url}")
        return
    try:
        data = json.loads(pending.read_text())
    except FileNotFoundError:
        raise AuthError('Run the command without a URL first.') from None
    code = _code(redirected, data['state'])
    async with httpx.AsyncClient(timeout=30) as http:
        t = build_tracklister(settings, http)
        if service == 'spotify':
            await t.spotify.exchange(code, settings.spotify_redirect_uri, data['verifier'])
            print('Logged in to Spotify.')
        else:
            athlete = await t.strava.exchange(code)
            print(f"Logged in to Strava as athlete {athlete['id']}.")
    pending.unlink()


async def _run(args: argparse.Namespace) -> None:
    settings = load_settings()
    if args.command in ('auth-spotify', 'auth-strava'):
        await _auth(settings, args.command.removeprefix('auth-'), args.redirected_url)
        return
    async with httpx.AsyncClient(timeout=30) as http:
        t = build_tracklister(settings, http)
        if args.command == 'recent':
            for a in await t.strava.recent_activities(args.count):
                print(a['id'], a['start_date_local'], a['sport_type'], a['name'])
        elif args.command == 'apply':
            print(await t.apply(args.activity_id))
        elif args.command == 'subscribe':
            url = f"{args.base_url.rstrip('/')}/webhook/{settings.webhook_secret}"
            print(await t.strava.subscribe(url, settings.webhook_secret))
        elif args.command == 'subscriptions':
            # Callback URLs contain the webhook secret, so print only the ids.
            print([s['id'] for s in await t.strava.subscriptions()])


def main() -> None:
    parser = argparse.ArgumentParser(prog='strava-tracklist-cli')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('auth-spotify', 'auth-strava'):
        p = sub.add_parser(name, help=f"log in to {name.removeprefix('auth-').title()}")
        p.add_argument('redirected_url', nargs='?')
    p = sub.add_parser('recent', help='list recent Strava activities')
    p.add_argument('--count', type=int, default=10)
    p = sub.add_parser('apply', help='add or refresh the tracklist on one activity')
    p.add_argument('activity_id', type=int)
    p = sub.add_parser('subscribe', help='register the webhook with Strava (one per Strava app)')
    p.add_argument('base_url', help='public base URL, e.g. https://strava-tracklist.example.com')
    sub.add_parser('subscriptions', help="list the Strava app's webhook subscription ids")
    try:
        asyncio.run(_run(parser.parse_args()))
    except AuthError as e:
        raise SystemExit(str(e)) from None


if __name__ == '__main__':
    main()
