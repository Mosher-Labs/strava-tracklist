from fastapi.testclient import TestClient

from strava_tracklist.app import create_app
from strava_tracklist.tracklist import HEADER

from conftest import ACTIVITY, ATHLETE, SECRET, minutes, play


def event(aspect='create', owner=ATHLETE, **extra):
    return {'object_type': 'activity', 'aspect_type': aspect, 'object_id': ACTIVITY, 'owner_id': owner, **extra}


async def test_create_prepends_tracklist_and_keeps_description(tracklister, apis):
    apis.plays = [play('One', minutes(3)), play('Two', minutes(6))]
    assert await tracklister.handle_event(event()) == f"{ACTIVITY}: added 2 tracks"
    lines = apis.description.splitlines()
    assert lines[0] == HEADER and lines[1] == '1. One Band – One'
    assert lines[3] == 'Playlist: Run · 2026-11-16 · 150'
    assert apis.description.endswith('\n\nFelt good.')


async def test_create_twice_does_not_duplicate(tracklister, apis):
    apis.plays = [play('One', minutes(3))]
    await tracklister.handle_event(event())
    assert await tracklister.handle_event(event()) == f"{ACTIVITY}: unchanged"
    assert len(apis.puts) == 1 and apis.description.count(HEADER) == 1


async def test_update_restores_a_dropped_block_but_never_rewrites_one(tracklister, apis):
    apis.plays = [play('One', minutes(3))]
    await tracklister.handle_event(event())
    apis.plays = []  # Spotify's history has moved on
    assert await tracklister.handle_event(event('update', updates={'title': 'x'})) == f"{ACTIVITY}: block already there"
    apis.description = 'Typed in an old edit screen.'
    apis.plays = [play('One', minutes(3))]
    await tracklister.handle_event(event('update', updates={'title': 'x'}))
    assert apis.description.startswith(HEADER) and apis.description.endswith('Typed in an old edit screen.')


async def test_no_plays_leaves_activity_alone(tracklister, apis):
    apis.plays = [play('Yesterday', minutes(-600))]
    assert await tracklister.handle_event(event()) == f"{ACTIVITY}: no Spotify plays during the activity"
    assert apis.puts == []


async def test_other_athletes_and_objects_are_ignored(tracklister, apis):
    assert (await tracklister.handle_event(event(owner=7))).startswith('ignored')
    assert (await tracklister.handle_event({**event(), 'object_type': 'athlete'})).startswith('ignored')
    assert (await tracklister.handle_event(event('delete'))).startswith('ignored')
    assert apis.calls == []


async def test_expired_strava_token_is_refreshed_and_saved(tracklister, apis, settings):
    import json
    path = settings.strava_token_path
    data = json.loads(path.read_text())
    path.write_text(json.dumps({**data, 'expires_at': 0}))
    await tracklister.apply(ACTIVITY)
    assert ('POST', '/oauth/token') in apis.calls
    saved = json.loads(path.read_text())
    assert saved['refresh_token'] == 'r2' and saved['athlete_id'] == ATHLETE


def test_webhook_needs_the_secret_and_answers_the_challenge(settings, tracklister, apis):
    client = TestClient(create_app(settings, tracklister))
    params = {'hub.mode': 'subscribe', 'hub.challenge': 'abc', 'hub.verify_token': SECRET}
    assert client.get(f"/webhook/{SECRET}", params=params).json() == {'hub.challenge': 'abc'}
    assert client.get('/webhook/wrong', params=params).status_code == 404
    assert client.get(f"/webhook/{SECRET}", params={**params, 'hub.verify_token': 'no'}).status_code == 404
    assert client.post('/webhook/wrong', json=event()).status_code == 404
    assert apis.calls == []


def test_webhook_event_runs_after_the_reply(settings, tracklister, apis):
    apis.plays = [play('One', minutes(3))]
    client = TestClient(create_app(settings, tracklister))
    assert client.post(f"/webhook/{SECRET}", json=event()).status_code == 200
    assert apis.description.startswith(HEADER)


def test_readyz_waits_for_both_logins(settings, tracklister):
    client = TestClient(create_app(settings, tracklister))
    assert client.get('/readyz').status_code == 200
    settings.spotify_token_path.unlink()
    assert client.get('/readyz').json()['missing'] == ['spotify-token.json']
