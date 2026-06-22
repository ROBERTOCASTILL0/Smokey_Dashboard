#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'data'
SNAPSHOT_PATH = DATA_DIR / 'dashboard_snapshot.json'
DEFAULT_SOURCE = (os.environ.get('SOURCE_STATUS_URL') or '').strip()
DEFAULT_BEARER = (os.environ.get('SOURCE_STATUS_BEARER_TOKEN') or '').strip()
TIMEOUT = 30
KEEP_KEYS = [
    'generated_at',
    'last_successful_dashboard_update',
    'executive_summary',
    'current_wildland_posture',
    'san_diego_fire_weather',
    'priority_incidents',
    'todays_prevention_focus',
    'dashboard_config',
    'change_tracking',
    'source_and_verification_status',
    'community_intelligence',
    'security_note',
]


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sample_payload() -> dict:
    now = utcnow()
    return {
        'generated_at': now,
        'last_successful_dashboard_update': now,
        'executive_summary': {
            'headline': 'Waiting for first live refresh',
            'text': 'No upstream snapshot has been configured yet. Set SOURCE_STATUS_URL and run a refresh to populate live data.',
            'severity': 'gray',
            'posture': 'UNKNOWN',
            'generated_at': now,
        },
        'current_wildland_posture': {
            'status': 'UNKNOWN',
            'explanation': 'No live posture snapshot is available yet.',
            'sd_count': 0,
            'socal_significant_count': 0,
            'red_flag_or_watch_status': 'Unknown',
            'supporting_factors': ['Configure an upstream snapshot source and refresh the cache.'],
            'threshold_rules': [],
        },
        'san_diego_fire_weather': {
            'operational_summary': {
                'title': 'Operational Fire Weather Factors',
                'primary_source': 'Awaiting configured source',
                'issued_at': now,
                'last_verified_at': now,
                'source_note': 'Live weather details will appear after the first successful refresh.',
                'items': [],
            },
            'alerts': [],
            'observations': [],
            'regions': [],
            'most_concerning_region': None,
            'red_flag_or_watch_status': 'Unknown',
            'plain_language_summary': 'Awaiting first refresh.',
            'official_links': [],
        },
        'priority_incidents': [],
        'todays_prevention_focus': {
            'label': 'Suggested prevention considerations — not incident commands or official directives',
            'items': [],
        },
        'dashboard_config': {
            'description': 'Dashboard thresholds and map defaults for the public viewer.',
            'watchAreas': [],
            'defaultMapCenter': [32.95, -116.85],
            'defaultMapZoom': 8,
            'defaultMapBounds': [[32.45, -117.55], [33.55, -116.05]],
        },
        'change_tracking': {
            'available': False,
            'since': None,
            'items': [],
            'thresholds': {},
        },
        'source_and_verification_status': {
            'last_successful_dashboard_update': now,
            'healthy_sources': 0,
            'delayed_or_failing_sources': 0,
            'warning': 'Awaiting first successful refresh.',
            'source_health_summary': {'healthy': 0, 'delayed': 0, 'stale': 0, 'failed': 0, 'cached': 0, 'oldest_age_minutes': None},
            'primary_source_health_summary': {'healthy': 0, 'delayed': 0, 'stale': 0, 'failed': 0, 'cached': 0, 'oldest_age_minutes': None},
            'sources': [],
        },
        'community_intelligence': {
            'enabled': False,
            'generated_at': now,
            'disclaimer': 'Community/social reporting is used as an awareness signal, not confirmed truth. Confirm with official sources before operational use.',
            'summary': {},
            'sections': {
                'high_confidence_community_intelligence': {'label': 'High Confidence Community Intelligence', 'cap': 5, 'items': []},
                'prevention_and_stakeholder_intelligence': {'label': 'Prevention & Stakeholder Intelligence', 'cap': 10, 'items': []},
                'community_signals_low_confidence': {'label': 'Low Confidence Community Signals', 'cap': 10, 'items': []},
            },
            'community_review_queue': {
                'enabled': False,
                'generated_at': now,
                'disclaimer': 'Review-required stakeholder/public-page items are shown for operator awareness only.',
                'summary': {},
                'sections': {
                    'autonomous_awareness': {'label': 'Autonomous Awareness: Review-Required Items', 'cap': 3, 'items': []},
                    'high_priority': {'label': 'Review Queue: High Priority', 'cap': 5, 'items': []},
                    'normal_priority': {'label': 'Review Queue: Normal', 'cap': 10, 'items': []},
                    'low_priority': {'label': 'Review Queue: Low Priority', 'cap': 10, 'items': []},
                },
            },
        },
        'security_note': 'Public-safe read-only viewer. Dashboard conclusions are not official agency statements.',
    }


def scrub_private_values(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(token in key_text for token in ('path', 'inputpath', 'summarypath', 'candidatepath', 'rejectionpath')):
                continue
            cleaned[key] = scrub_private_values(item)
        return cleaned
    if isinstance(value, list):
        return [scrub_private_values(item) for item in value]
    if isinstance(value, str) and ('/opt/data' in value or value.startswith('file://')):
        return ''
    return value


def normalize_payload(raw: dict) -> dict:
    baseline = sample_payload()
    payload = {key: deepcopy(raw.get(key)) for key in KEEP_KEYS}
    for key in KEEP_KEYS:
        if payload.get(key) is None:
            payload[key] = deepcopy(baseline[key])
    if not isinstance(payload.get('priority_incidents'), list):
        payload['priority_incidents'] = []
    if not isinstance(payload.get('change_tracking'), dict):
        payload['change_tracking'] = deepcopy(baseline['change_tracking'])
    if not isinstance(payload.get('todays_prevention_focus'), dict):
        payload['todays_prevention_focus'] = deepcopy(baseline['todays_prevention_focus'])
    if not isinstance(payload.get('dashboard_config'), dict):
        payload['dashboard_config'] = deepcopy(baseline['dashboard_config'])
    if not isinstance(payload.get('community_intelligence'), dict):
        payload['community_intelligence'] = deepcopy(baseline['community_intelligence'])
    if not isinstance(payload.get('source_and_verification_status'), dict):
        payload['source_and_verification_status'] = deepcopy(baseline['source_and_verification_status'])
    source_status = payload.get('source_and_verification_status')
    if not isinstance(source_status, dict):
        source_status = deepcopy(baseline['source_and_verification_status'])
        payload['source_and_verification_status'] = source_status
    source_items = source_status.get('sources') or []
    source_status['sources'] = [
        item for item in source_items
        if isinstance(item, dict)
        and '/opt/data' not in str(item.get('source_url') or '')
        and not str(item.get('source_url') or '').startswith('file://')
    ]
    payload['dashboard_config'] = scrub_private_values(payload.get('dashboard_config') or {})
    payload['community_intelligence'] = scrub_private_values(payload.get('community_intelligence') or {})
    payload['security_note'] = baseline['security_note']
    return payload


def fetch_upstream(url: str, bearer: str = '') -> dict:
    headers = {'User-Agent': 'WildlandDashboardCollector/1.0', 'Accept': 'application/json'}
    if bearer:
        headers['Authorization'] = f'Bearer {bearer}'
    req = Request(url, headers=headers)
    with urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Upstream payload must be a JSON object')
    return data


def write_snapshot(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile('w', encoding='utf-8', dir=DATA_DIR, delete=False) as tmp:
        json.dump(payload, tmp, indent=2)
        tmp.write('\n')
        temp_path = Path(tmp.name)
    temp_path.replace(SNAPSHOT_PATH)


def refresh_snapshot(url: str | None = None, bearer: str | None = None) -> dict:
    source_url = (url or DEFAULT_SOURCE or '').strip()
    source_bearer = (bearer if bearer is not None else DEFAULT_BEARER or '').strip()
    if source_url:
        raw = fetch_upstream(source_url, source_bearer)
        payload = normalize_payload(raw)
        payload['collector'] = {'refreshed_at': utcnow(), 'mode': 'upstream-json'}
    elif SNAPSHOT_PATH.exists():
        payload = json.loads(SNAPSHOT_PATH.read_text(encoding='utf-8'))
        payload.setdefault('collector', {'refreshed_at': utcnow(), 'mode': 'existing-cache'})
    else:
        payload = sample_payload()
        payload['collector'] = {'refreshed_at': utcnow(), 'mode': 'bootstrap-sample'}
    write_snapshot(payload)
    return payload


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else 'refresh'
    if cmd not in {'refresh', 'json'}:
        print('usage: python collector.py [refresh|json]', file=sys.stderr)
        return 2
    payload = refresh_snapshot()
    if cmd == 'json':
        print(json.dumps(payload, indent=2))
    else:
        print(json.dumps({'ok': True, 'snapshot_path': str(SNAPSHOT_PATH), 'generated_at': payload.get('generated_at'), 'incident_count': len(payload.get('priority_incidents') or [])}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
