"""Put the tracklist on one Strava activity."""

import asyncio
import logging
from datetime import timedelta

from strava_tracklist import tracklist
from strava_tracklist.spotify import Spotify
from strava_tracklist.strava import Strava

log = logging.getLogger('strava_tracklist')

# Ask Spotify for plays from a little before the activity, so a song already
# playing at the start is included.
_LOOKBACK = timedelta(minutes=15)


class Tracklister:
    def __init__(self, strava: Strava, spotify: Spotify):
        self.strava = strava
        self.spotify = spotify
        # One pod, so a process lock is enough to keep two events for the same
        # activity from both writing.
        self._lock = asyncio.Lock()

    async def handle_event(self, event: dict) -> str:
        if event.get('object_type') != 'activity' or event.get('aspect_type') not in ('create', 'update'):
            return 'ignored: not an activity create or update'
        if event.get('owner_id') != self.strava.athlete_id:
            return 'ignored: another athlete'
        # Strava sends an update for title, type and privacy changes. A save
        # from an edit screen opened before the block was added drops it, so
        # an update puts it back, but never rewrites a block that is there.
        return await self.apply(int(event['object_id']), replace=event['aspect_type'] == 'create')

    async def apply(self, activity_id: int, replace: bool = True) -> str:
        async with self._lock:
            activity = await self.strava.activity(activity_id)
            description = activity.get('description') or ''
            if not replace and tracklist.has_block(description):
                return f"{activity_id}: block already there"
            start = tracklist.parse_time(activity['start_date'])
            end = start + timedelta(seconds=activity['elapsed_time'])
            after_ms = int((start - _LOOKBACK).timestamp() * 1000)
            plays = tracklist.during(
                tracklist.plays_from_spotify(await self.spotify.recently_played(after_ms)), start, end
            )
            if not plays:
                return f"{activity_id}: no Spotify plays during the activity"
            playlists = [(pid, await self.spotify.playlist_name(pid)) for pid in tracklist.playlist_ids(plays)]
            updated = tracklist.with_block(description, tracklist.build_block(plays, playlists))
            if updated == description:
                return f"{activity_id}: unchanged"
            await self.strava.set_description(activity_id, updated)
            return f"{activity_id}: added {len(plays)} tracks"
