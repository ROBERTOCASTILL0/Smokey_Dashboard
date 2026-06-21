def login(client, pin='1144'):
    return client.post('/login', data={'pin': pin}, follow_redirects=False)


def test_login_redirects_to_dashboard(monkeypatch):
    monkeypatch.setenv('ACCESS_PIN', '1144')
    from app import app
    client = app.test_client()
    resp = login(client)
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/')


def test_api_requires_login(monkeypatch):
    monkeypatch.setenv('ACCESS_PIN', '1144')
    from app import app
    client = app.test_client()
    resp = client.get('/api/status', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']
