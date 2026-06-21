def test_refresh_requires_token(monkeypatch):
    monkeypatch.setenv('REFRESH_TOKEN', 'abc123')
    from app import app
    client = app.test_client()
    resp = client.post('/internal/refresh')
    assert resp.status_code == 403


def test_refresh_accepts_token(monkeypatch):
    monkeypatch.setenv('REFRESH_TOKEN', 'abc123')
    from app import app
    client = app.test_client()
    resp = client.post('/internal/refresh', headers={'X-Refresh-Token': 'abc123'})
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True
