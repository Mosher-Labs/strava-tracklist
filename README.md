# strava-tracklist

![GitHub branch status](https://img.shields.io/github/checks-status/mosher-labs/strava-tracklist/main)
![GitHub last commit](https://img.shields.io/github/last-commit/mosher-labs/strava-tracklist)
![GitHub License](https://img.shields.io/github/license/mosher-labs/strava-tracklist)

A small service that adds the songs you listened to on Spotify during a
workout to the top of its Strava description, followed by a link to the
playlist they came from:

```text
🎧 Tracklist
1. Linkin Park – Papercut
2. Megadeth – Hey God?!
Playlist: Run · 2026-11-16 · 150
https://open.spotify.com/playlist/6LPHxO7nFb6Px5NfGZqEpH

Anything you wrote yourself stays down here.
```

It is built for one person. You run your own copy with your own Strava and
Spotify apps, and your tokens stay on your own disk.

## How it works

1. Strava calls the webhook as soon as a new activity is uploaded.
2. The service reads the activity from Strava and asks Spotify for your
   recently played tracks. A track counts when at least 30 seconds of it
   overlaps the activity.
3. It puts the tracklist at the top of the description and the playlist link
   below it. The block ends at the first blank line, and everything under it
   is kept.

Running it again replaces the block instead of adding a second one. When
Strava reports a later change to the activity's title, type, or privacy, the
service puts the block back if it is missing, for example after a save from an
edit screen that was opened before the block was added. It never rewrites a
block that is already there.

### Limits

- Spotify's recently played list holds only your last 50 plays. If an activity
  reaches Strava after you have played 50 more songs, its tracks are gone.
- Spotify does not report how long a play lasted, so a skipped song is listed
  like any other.
- The Strava API has no conditional writes. If you are editing the description
  at the moment the service writes it, whichever save lands last wins.

## Setup

You need:

- **A Strava API app** from [strava.com/settings/api](https://www.strava.com/settings/api).
  Strava allows one app per account, and one app can serve several services,
  each with its own login. Set the callback domain to `localhost`.
- **A Spotify app** from the [Spotify developer dashboard](https://developer.spotify.com/dashboard),
  with `http://127.0.0.1:8888/callback` as a redirect URI. Its client secret is
  not used.
- **A public HTTPS address** that forwards to the service, for Strava's
  webhook. A Cloudflare Tunnel works.

### Configuration

| Variable | Meaning |
|----------|---------|
| `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` | From the Strava app. |
| `SPOTIFY_CLIENT_ID` | From the Spotify app. |
| `STRAVA_TRACKLIST_WEBHOOK_SECRET` | A random string (`openssl rand -hex 24`). It is the last part of the webhook URL. |
| `STRAVA_TRACKLIST_DATA_DIR` | Where the two token files live. `/data` in the image. |
| `STRAVA_TRACKLIST_HOST`, `STRAVA_TRACKLIST_PORT` | Default `127.0.0.1`, `8000`. `0.0.0.0` in the image. |
| `STRAVA_REDIRECT_URI`, `SPOTIFY_REDIRECT_URI` | Defaults `http://localhost/exchange_token` and `http://127.0.0.1:8888/callback`. |

### Log in and subscribe

Each login runs twice. The first run prints a URL to approve. Your browser then
lands on a localhost page that fails to load. Run the command again with that
address.

```bash
strava-tracklist-cli auth-strava
strava-tracklist-cli auth-strava 'http://localhost/exchange_token?state=...&code=...'
strava-tracklist-cli auth-spotify
strava-tracklist-cli auth-spotify 'http://127.0.0.1:8888/callback?code=...&state=...'
```

With the service reachable at its public address, register the webhook once:

```bash
strava-tracklist-cli subscribe https://strava-tracklist.example.com
```

To try it on an existing activity:

```bash
strava-tracklist-cli recent
strava-tracklist-cli apply <activity id>
```

## Endpoints

| Path | Purpose |
|------|---------|
| `GET /webhook/<secret>` | Strava's subscription check. |
| `POST /webhook/<secret>` | Strava's activity events. Any other path segment returns 404. |
| `GET /healthz` | Liveness. |
| `GET /readyz` | 503 until both logins are done. |

Strava does not sign webhook events, so the secret in the path is the only
check on the caller. The service also re-reads every activity from Strava and
ignores events for any athlete other than the one logged in.

## Tests

```bash
uv sync && uv run pytest
```

## Deployment

Mosher Labs runs it from `homelab-gitops` (`apps/strava-tracklist`). Every push
to `main` builds `ghcr.io/mosher-labs/strava-tracklist:<short sha>`.

## Contributing

Install the pre-commit hooks once after cloning, and run them before each
commit:

```bash
pre-commit install
pre-commit run --all-files
```

Commits follow Conventional Commits, which drives the release workflow.
