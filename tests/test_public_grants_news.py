import json
from pathlib import Path

from collector import normalize_payload, sample_payload


def test_normalize_payload_preserves_grants_and_news():
    payload = normalize_payload(
        {
            'generated_at': '2026-06-22T04:00:28+00:00',
            'last_successful_dashboard_update': '2026-06-22T04:00:28+00:00',
            'grants_watch': {
                'items': [
                    {
                        'title': 'CAL FIRE Wildfire Prevention Grants',
                        'sponsor': 'CAL FIRE',
                    }
                ]
            },
            'relevant_news': {
                'items': [
                    {
                        'title': 'Mission 2 Fire in Fallbrook',
                        'publisher': 'fox5sandiego.com',
                    }
                ],
                'source_status': [
                    {'label': 'County News Center wildfire feed', 'status': 'HEALTHY'}
                ],
            },
        }
    )
    assert payload['grants_watch']['items'][0]['title'] == 'CAL FIRE Wildfire Prevention Grants'
    assert payload['relevant_news']['items'][0]['title'] == 'Mission 2 Fire in Fallbrook'
    assert payload['relevant_news']['source_status'][0]['status'] == 'HEALTHY'


def test_sample_payload_includes_empty_grants_and_news_sections():
    payload = sample_payload()
    assert payload['grants_watch']['items'] == []
    assert payload['relevant_news']['items'] == []
    assert payload['relevant_news']['source_status'] == []


def test_push_snapshot_accepts_grants_and_news_and_dashboard_renders(monkeypatch):
    monkeypatch.setenv('PUSH_TOKEN', 'push-secret')
    monkeypatch.setenv('ACCESS_PIN', '1144')
    from app import app
    from collector import SNAPSHOT_PATH

    original = SNAPSHOT_PATH.read_text(encoding='utf-8') if SNAPSHOT_PATH.exists() else None
    client = app.test_client()
    payload = {
        'generated_at': '2026-06-22T04:00:28+00:00',
        'last_successful_dashboard_update': '2026-06-22T04:00:28+00:00',
        'executive_summary': {'headline': 'Example', 'text': 'Summary'},
        'current_wildland_posture': {'status': 'ELEVATED', 'explanation': 'Example'},
        'san_diego_fire_weather': {'plain_language_summary': 'Example'},
        'priority_incidents': [],
        'todays_prevention_focus': {'items': []},
        'grants_watch': {
            'disclaimer': 'Grant disclaimer.',
            'items': [
                {
                    'title': 'CAL FIRE Wildfire Prevention Grants',
                    'sponsor': 'CAL FIRE',
                    'display_status': 'Open / upcoming',
                    'candidate_reason': 'Good fit for SDFD.',
                    'url': 'https://example.com/grants',
                }
            ],
        },
        'relevant_news': {
            'disclaimer': 'News disclaimer.',
            'items': [
                {
                    'title': 'Mission 2 Fire in Fallbrook',
                    'publisher': 'fox5sandiego.com',
                    'published_at': '2026-06-22T04:00:28+00:00',
                    'summary': 'Brush fire coverage.',
                    'source_type': 'media',
                    'url': 'https://example.com/news',
                }
            ],
            'source_status': [
                {
                    'label': 'County News Center wildfire feed',
                    'status': 'HEALTHY',
                    'last_checked_at': '2026-06-22T04:00:28+00:00',
                    'items_seen': 4,
                }
            ],
        },
        'dashboard_config': {},
        'change_tracking': {'available': False, 'items': []},
        'community_intelligence': {'enabled': False, 'summary': {}, 'sections': {}},
        'source_and_verification_status': {'sources': []},
    }
    try:
        resp = client.post('/internal/push-snapshot', json=payload, headers={'X-Push-Token': 'push-secret'})
        assert resp.status_code == 200
        login_resp = client.post('/login', data={'pin': '1144'}, follow_redirects=True)
        assert login_resp.status_code == 200
        html = login_resp.get_data(as_text=True)
        assert 'Grant watch' in html
        assert 'Relevant news' in html
        assert 'CAL FIRE Wildfire Prevention Grants' in html
        assert 'Mission 2 Fire in Fallbrook' in html
        saved = json.loads(Path(SNAPSHOT_PATH).read_text(encoding='utf-8'))
        assert saved['grants_watch']['items'][0]['title'] == 'CAL FIRE Wildfire Prevention Grants'
        assert saved['relevant_news']['items'][0]['title'] == 'Mission 2 Fire in Fallbrook'
    finally:
        if original is None:
            Path(SNAPSHOT_PATH).unlink(missing_ok=True)
        else:
            Path(SNAPSHOT_PATH).write_text(original, encoding='utf-8')
