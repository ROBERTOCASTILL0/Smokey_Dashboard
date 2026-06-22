from app import format_timestamp


def test_format_timestamp_converts_iso_to_pacific():
    formatted = format_timestamp('2026-06-21T22:01:06+00:00')
    assert formatted == 'Sun, Jun 21 · 3:01 pm PDT'


def test_format_timestamp_handles_missing_value():
    assert format_timestamp(None) == 'n/a'
