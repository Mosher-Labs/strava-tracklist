# strava-tracklist - Project Memory

## Project Overview

A webhook service that adds the Spotify tracks played during a Strava activity,
and the playlist they came from, to the top of the activity's description.
Single user, self-hosted, standalone: it does not depend on spotify-mcp.

**Key Details:**

- **Stack:** Python 3.12, FastAPI, httpx, uv
- **Deploy:** `homelab-gitops` `apps/strava-tracklist`, image
  `ghcr.io/mosher-labs/strava-tracklist`, pinned by digest
- **Auth:** Strava OAuth with the app's client secret; Spotify PKCE with no
  secret. Both tokens are JSON files on the data volume, mode 0600
- **Webhook:** `/webhook/<secret>`. Strava does not sign events, so the path
  secret is the check, and activities are always re-read from Strava

## Repository Structure

```text
src/strava_tracklist/
├── app.py        # FastAPI webhook server
├── cli.py        # logins, subscribe, recent, apply
├── config.py     # env settings
├── service.py    # one activity: read, match plays, write description
├── spotify.py    # PKCE login, recently played, playlist name
├── strava.py     # OAuth, activities, push subscriptions
├── tokens.py     # token files
└── tracklist.py  # pure logic: plays in window, the description block
```

## Behavior worth knowing

- Spotify's `played_at` is when a play finished. A play counts when 30 s of it
  overlaps the activity.
- The block starts with `🎧 Tracklist` and ends at the first blank line.
  Replacing it never touches the text below.
- `create` events always write; `update` events only restore a missing block.
- Strava allows one API app per account and one webhook subscription per app.

## Git Workflow

- Feature branch, PR, squash merge. Conventional Commits (`feat:`, `fix:`).
- Run `pre-commit run --all-files` before committing. The Docker-based hooks
  need Docker running.
- `uv run pytest` must pass.
