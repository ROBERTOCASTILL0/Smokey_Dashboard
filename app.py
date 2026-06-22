#!/usr/bin/env python3
from __future__ import annotations

import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from collector import SNAPSHOT_PATH, normalize_payload, sample_payload, write_snapshot

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-key'),
    JSON_SORT_KEYS=False,
    MAX_CONTENT_LENGTH=int(os.environ.get('MAX_SNAPSHOT_BYTES', str(1024 * 1024))),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=(os.environ.get('SESSION_COOKIE_SECURE', 'true').strip().lower() not in {'0', 'false', 'no'}),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=int(os.environ.get('SESSION_HOURS', '24'))),
)

SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
    'Cache-Control': 'private, no-store',
}
DISPLAY_TZ_NAME = os.environ.get('DISPLAY_TIMEZONE', 'America/Los_Angeles')
DISPLAY_TZ = ZoneInfo(DISPLAY_TZ_NAME)


def _parse_timestamp(value: str | None):
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    try:
        dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(DISPLAY_TZ)


def format_timestamp(value: str | None, fallback: str = 'n/a') -> str:
    dt = _parse_timestamp(value)
    if not dt:
        return fallback if value in (None, '') else str(value)
    label = dt.strftime('%a, %b %-d · %-I:%M %p').replace('AM', 'am').replace('PM', 'pm')
    return f'{label} {dt.tzname()}'


@app.template_filter('friendly_time')
def friendly_time_filter(value):
    return format_timestamp(value)


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


def push_token_matches(candidate: str) -> bool:
    token = (os.environ.get('PUSH_TOKEN') or '').strip()
    return bool(token) and hmac.compare_digest(candidate.strip(), token)


def validate_push_payload(payload: dict) -> str | None:
    required_str_fields = ('generated_at', 'last_successful_dashboard_update')
    for field in required_str_fields:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            return f'invalid_{field}'

    typed_fields = {
        'priority_incidents': list,
        'dashboard_config': dict,
        'source_and_verification_status': dict,
        'community_intelligence': dict,
        'change_tracking': dict,
        'san_diego_fire_weather': dict,
        'current_wildland_posture': dict,
        'todays_prevention_focus': dict,
        'grants_watch': dict,
        'relevant_news': dict,
        'executive_summary': dict,
    }
    for field, expected_type in typed_fields.items():
        value = payload.get(field)
        if value is not None and not isinstance(value, expected_type):
            return f'invalid_{field}'
    return None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('viewer_authenticated'):
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)
    return wrapped


def push_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        token = (request.headers.get('X-Push-Token') or '').strip()
        if not push_token_matches(token):
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


@app.post('/internal/push-snapshot')
@push_required
def internal_push_snapshot():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'ok': False, 'error': 'invalid_json_object'}), 400
    validation_error = validate_push_payload(payload)
    if validation_error:
        return jsonify({'ok': False, 'error': validation_error}), 400
    normalized = normalize_payload(payload)
    normalized['collector'] = {
        'refreshed_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'mode': 'hermes-push',
    }
    write_snapshot(normalized)
    return jsonify({
        'ok': True,
        'generated_at': normalized.get('generated_at'),
        'incident_count': len(normalized.get('priority_incidents') or []),
        'mode': 'hermes-push',
    })


@app.errorhandler(404)
def not_found(_err):
    return jsonify({'ok': False, 'error': 'not found'}), 404


@app.errorhandler(413)
def payload_too_large(_err):
    return jsonify({'ok': False, 'error': 'payload_too_large'}), 413


@app.errorhandler(500)
def server_error(_err):
    return jsonify({'ok': False, 'error': 'server error'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False)
