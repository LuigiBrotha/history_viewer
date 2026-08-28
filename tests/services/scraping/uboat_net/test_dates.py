from datetime import date

from app.services.scraping.uboat_net.dates import parse_date, parse_iso_date


def test_parse_date_valid():
    assert parse_date("18 Jun 1940") == date(1940, 6, 18)


def test_parse_date_strips_trailing_nbsp():
    assert parse_date("18 Jun 1940\xa0\xa0") == date(1940, 6, 18)


def test_parse_date_none_input_returns_none():
    assert parse_date(None) is None


def test_parse_date_empty_string_returns_none():
    assert parse_date("") is None


def test_parse_date_unknown_text_returns_none():
    assert parse_date("Unknown") is None


def test_parse_iso_date_valid():
    assert parse_iso_date("1940-06-18") == date(1940, 6, 18)


def test_parse_iso_date_none_returns_none():
    assert parse_iso_date(None) is None


def test_parse_iso_date_malformed_returns_none():
    assert parse_iso_date("not-a-date") is None
