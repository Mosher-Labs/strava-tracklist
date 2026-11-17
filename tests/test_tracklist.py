from datetime import timedelta

from strava_tracklist import tracklist
from strava_tracklist.tracklist import HEADER

from conftest import PLAYLIST, START, minutes, play


def plays(*items):
    return tracklist.plays_from_spotify(list(items))


def test_play_counts_when_it_overlaps_the_activity():
    end = START + timedelta(minutes=40)
    got = tracklist.during(
        plays(
            play('Before', minutes(-1)),          # finished before the start
            play('Started before', minutes(2)),  # 3 min long, 2 min of it in the run
            play('Barely', minutes(0.4)),        # only 24 s in the run
            play('Middle', minutes(20)),
            play('Last', minutes(42)),           # still playing when the run ended
            play('After', minutes(44)),          # started after the end
        ),
        START,
        end,
    )
    assert [p.title for p in got] == ['Started before', 'Middle', 'Last']


def test_playlists_in_first_played_order_ignoring_albums():
    got = tracklist.playlist_ids(plays(
        play('a', minutes(1), context='spotify:album:x'),
        play('b', minutes(2), context='spotify:playlist:p2'),
        play('c', minutes(3)),
        play('d', minutes(4), context='spotify:playlist:p2'),
        play('e', minutes(5), context=None),
    ))
    assert got == ['p2', PLAYLIST]


def test_block_lists_tracks_then_playlist_links():
    block = tracklist.build_block(plays(play('One', minutes(3)), play('Two', minutes(6))), [(PLAYLIST, 'Run')])
    assert block.splitlines() == [
        HEADER,
        '1. One Band – One',
        '2. Two Band – Two',
        'Playlist: Run',
        f"https://open.spotify.com/playlist/{PLAYLIST}",
    ]


def test_block_goes_above_the_existing_description_and_replaces_itself():
    first = tracklist.with_block('Felt good.\n\nWindy.', f"{HEADER}\n1. A")
    assert first == f"{HEADER}\n1. A\n\nFelt good.\n\nWindy."
    assert tracklist.with_block(first, f"{HEADER}\n1. B") == f"{HEADER}\n1. B\n\nFelt good.\n\nWindy."
    assert tracklist.with_block(None, f"{HEADER}\n1. A") == f"{HEADER}\n1. A"
    assert tracklist.with_block(f"{HEADER}\n1. A", f"{HEADER}\n1. B") == f"{HEADER}\n1. B"
