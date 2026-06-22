def test_internal_refresh_route_not_exposed(monkeypatch):
    monkeypatch.setenv('PUSH_TOKEN', 'push-secret')
    from app import app
    client = app.test_client()
    resp = client.post('/internal/refresh', headers={'X-Refresh-Token': 'anything'})
    assert resp.status_code == 404
