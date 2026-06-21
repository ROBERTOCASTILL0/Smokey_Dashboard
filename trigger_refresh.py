#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

base_url = (os.environ.get('APP_BASE_URL') or '').strip().rstrip('/')
refresh_token = (os.environ.get('REFRESH_TOKEN') or '').strip()

if not base_url:
    print('APP_BASE_URL is required', file=sys.stderr)
    raise SystemExit(2)
if not refresh_token:
    print('REFRESH_TOKEN is required', file=sys.stderr)
    raise SystemExit(2)

req = Request(
    f'{base_url}/internal/refresh',
    method='POST',
    headers={
        'X-Refresh-Token': refresh_token,
        'User-Agent': 'WildlandDashboardCron/1.0',
    },
)

try:
    with urlopen(req, timeout=60) as resp:
        print(resp.read().decode('utf-8', errors='replace'))
except HTTPError as err:
    print(err.read().decode('utf-8', errors='replace'), file=sys.stderr)
    raise SystemExit(err.code)
except URLError as err:
    print(str(err), file=sys.stderr)
    raise SystemExit(1)
