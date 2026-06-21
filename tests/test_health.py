from app import app


def test_health_ok():
    client = app.test_client()
    resp = client.get('/health')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['ok'] is True
    assert payload['service'] == 'wildland-dashboard'
