#!/usr/bin/env python3
from __future__ import annotations

import hmac
import json
import os
from datetime import timedelta
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from collector import SNAPSHOT_PATH, refresh_snapshot, sample_payload

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-key'),
    JSON_SORT_KEYS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=int(os.environ.get('SESSION_HOURS', '24'))),
)

SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
    'Cache-Control': 'private, no-store',
}


@app.after_request
def add_security_headers(resp):
    for key, value in SECURITY_HEADERS.items():
        resp.headers.setdefault(key, value)
    resp.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com; style-src 'self' 'unsafe-inline' https://unpkg.com; img-src 'self' data: https:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'",
    )
    return resp


def load_snapshot() -> dict:
    if SNAPSHOT_PATH.exists():
        return json.loads(SNAPSHOT_PATH.read_text(encoding='utf-8'))
    return sample_payload()


def configured_pin() -> str:
    return (os.environ.get('ACCESS_PIN') or '').strip()


def pin_matches(candidate: str) -> bool:
    target = configured_pin()
    return bool(target) and hmac.compare_digest(candidate.strip(), target)


def refresh_token_matches(candidate: str) -> bool:
    token = (os.environ.get('REFRESH_TOKEN') or '').strip()
    return bool(token) and hmac.compare_digest(candidate.strip(), token)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('viewer_authenticated'):
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)
    return wrapped


def refresh_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        token = (request.headers.get('X-Refresh-Token') or '').strip()
        if not refresh_token_matches(token):
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
        return view(*args, **kwargs)
    return wrapped


@app.get('/health')
def health():
    snapshot = load_snapshot()
    return jsonify({'ok': True, 'service': 'wildland-dashboard', 'generated_at': snapshot.get('generated_at')})


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if pin_matches(request.form.get('pin', '')):
            session.clear()
            session.permanent = True
            session['viewer_authenticated'] = True
            return redirect(request.args.get('next') or url_for('index'))
        error = 'Invalid PIN.'
    return render_template('login.html', error=error)


@app.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.get('/')
@login_required
def index():
    snapshot = load_snapshot()
    return render_template('dashboard.html', snapshot=snapshot, snapshot_json=json.dumps(snapshot))


@app.get('/api/status')
@login_required
def api_status():
    return jsonify(load_snapshot())


@app.post('/internal/refresh')
@refresh_required
def internal_refresh():
    snapshot = refresh_snapshot()
    return jsonify({'ok': True, 'generated_at': snapshot.get('generated_at'), 'incident_count': len(snapshot.get('priority_incidents') or [])})


@app.errorhandler(404)
def not_found(_err):
    return jsonify({'ok': False, 'error': 'not found'}), 404


@app.errorhandler(500)
def server_error(_err):
    return jsonify({'ok': False, 'error': 'server error'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False)
