"""Which plays belong to an activity, and the text block that lists them.

Spotify's played_at is when a play finished (checked against play lengths in
spotify-mcp's listening log), so a play ran from played_at minus its length
to played_at. A play counts when at least MIN_OVERLAP of that falls inside
the activity. Skipped tracks look like full plays here, because Spotify does
not report how long a play actually lasted.

The block goes at the top of the description and ends at the first blank
line, so anything written below it is kept when the block is replaced.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

HEADER = '🎧 Tracklist'
MIN_OVERLAP = timedelta(seconds=30)


@dataclass(frozen=True)
class Play:
    finished: datetime
    duration: timedelta
    artist: str
    title: str
    context_uri: str | None


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def plays_from_spotify(items: list[dict]) -> list[Play]:
    plays = []
    for item in items:
        track = item.get('track') or {}
        if not track.get('name'):
            continue
        plays.append(
            Play(
                finished=parse_time(item['played_at']),
                duration=timedelta(milliseconds=track.get('duration_ms') or 0),
                artist=', '.join(a['name'] for a in track.get('artists', [])) or 'Unknown artist',
                title=track['name'],
                context_uri=(item.get('context') or {}).get('uri'),
            )
        )
    return plays


def during(plays: list[Play], start: datetime, end: datetime) -> list[Play]:
    """Plays overlapping [start, end] by at least MIN_OVERLAP, oldest first."""
    kept = [
        p for p in plays
        if min(p.finished, end) - max(p.finished - p.duration, start) >= MIN_OVERLAP
    ]
    return sorted(kept, key=lambda p: p.finished)


def playlist_ids(plays: list[Play]) -> list[str]:
    """Playlists the plays came from, in the order they were first played."""
    ids: dict[str, None] = {}
    for p in plays:
        if p.context_uri and p.context_uri.startswith('spotify:playlist:'):
            ids.setdefault(p.context_uri.rsplit(':', 1)[1], None)
    return list(ids)


def build_block(plays: list[Play], playlists: list[tuple[str, str | None]]) -> str:
    """playlists is (id, name or None) pairs."""
    lines = [HEADER]
    lines += [f"{n}. {p.artist} – {p.title}" for n, p in enumerate(plays, 1)]
    for playlist_id, name in playlists:
        lines.append(f"Playlist: {name}" if name else 'Playlist:')
        lines.append(f"https://open.spotify.com/playlist/{playlist_id}")
    return '\n'.join(lines)


def has_block(description: str | None) -> bool:
    return (description or '').startswith(HEADER)


def strip_block(description: str | None) -> str:
    text = description or ''
    if not has_block(text):
        return text
    _, sep, rest = text.partition('\n\n')
    return rest if sep else ''


def with_block(description: str | None, block: str) -> str:
    rest = strip_block(description).strip()
    return f"{block}\n\n{rest}" if rest else block
