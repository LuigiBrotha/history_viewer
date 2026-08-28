from datetime import date

_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def parse_date(text: str | None) -> date | None:
    if not text:
        return None
    cleaned = text.replace("\xa0", " ").strip()
    parts = cleaned.split()
    if len(parts) != 3:
        return None
    day_text, month_text, year_text = parts
    month = _MONTHS.get(month_text[:3].title())
    if month is None:
        return None
    try:
        return date(int(year_text), month, int(day_text))
    except ValueError:
        return None


def parse_iso_date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None
