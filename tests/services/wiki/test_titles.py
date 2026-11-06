import pytest

from app.services.wiki.titles import normalize_title


@pytest.mark.parametrize("raw, expected", [
    ("second_Happy_Time", "Second Happy Time"),
    ("Battle%20of%20Crete", "Battle of Crete"),
    ("Battle of Midway#Background", "Battle of Midway"),
    ("  Operation  Torch ", "Operation Torch"),
    ("Battle of the Bulge (1944–45)", "Battle of the Bulge (1944–45)"),
])
def test_normalize_title(raw, expected):
    assert normalize_title(raw) == expected
