def test_push_snapshot_requires_token(monkeypatch):
    monkeypatch.setenv('PUSH_TOKEN', 'push-secret')
    from app import app
    client = app.test_client()
    resp = client.post('/internal/push-snapshot', json={'generated_at': '2026-06-22T04:00:28+00:00'})
    assert resp.status_code == 403


def test_push_snapshot_rejects_non_object(monkeypatch):
    monkeypatch.setenv('PUSH_TOKEN', 'push-secret')
    from app import app
    client = app.test_client()
    resp = client.post(
        '/internal/push-snapshot',
        data='["not-an-object"]',
        headers={'X-Push-Token': 'push-secret', 'Content-Type': 'application/json'},
    )
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'invalid_json_object'


def test_push_snapshot_rejects_missing_required_fields(monkeypatch):
    monkeypatch.setenv('PUSH_TOKEN', 'push-secret')
    from app import app
    client = app.test_client()
    resp = client.post(
        '/internal/push-snapshot',
        json={'generated_at': '2026-06-22T04:00:28+00:00'},
        headers={'X-Push-Token': 'push-secret'},
    )
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'invalid_last_successful_dashboard_update'


def test_push_snapshot_accepts_valid_payload_and_scrubs_private_values(monkeypatch):
    monkeypatch.setenv('PUSH_TOKEN', 'push-secret')
    import json
    from pathlib import Path
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
        'priority_incidents': [
            {
                'name': 'Example Fire',
                'location': 'San Diego County',
                'acreage': 12,
                'containment': 0,
                'incident_status': 'ACTIVE',
                'updated_at': '2026-06-22T04:00:28+00:00',
            }
        ],
        'todays_prevention_focus': {'items': []},
        'dashboard_config': {
            'inputPath': '/opt/data/private.json',
            'defaultMapCenter': [32.95, -116.85],
        },
        'change_tracking': {'available': False, 'items': []},
        'community_intelligence': {'enabled': True, 'summary': {}, 'sections': {}},
        'source_and_verification_status': {
            'sources': [
                {'source_name': 'private-file', 'source_url': 'file:///opt/data/private.json', 'status': 'healthy'},
                {'source_name': 'public-api', 'source_url': 'https://example.com/feed.json', 'status': 'healthy'},
            ]
        },
    }
    try:
        resp = client.post('/internal/push-snapshot', json=payload, headers={'X-Push-Token': 'push-secret'})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['ok'] is True
        assert body['incident_count'] == 1
        saved = json.loads(Path(SNAPSHOT_PATH).read_text(encoding='utf-8'))
        assert saved['collector']['mode'] == 'hermes-push'
        assert saved['dashboard_config'].get('inputPath') is None
        assert len(saved['source_and_verification_status']['sources']) == 1
        assert saved['source_and_verification_status']['sources'][0]['source_url'] == 'https://example.com/feed.json'
    finally:
        if original is None:
            Path(SNAPSHOT_PATH).unlink(missing_ok=True)
        else:
            Path(SNAPSHOT_PATH).write_text(original, encoding='utf-8')
