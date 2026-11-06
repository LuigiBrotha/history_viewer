MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]
MONTH_NAMES = [name.capitalize() for name in MONTHS]


def render_date(numbers):
    """Year, month and day from a date template as text; a lone year stays a bare year."""
    if len(numbers) == 3 and 1 <= int(numbers[1]) <= 12:
        return f"{int(numbers[2])} {MONTH_NAMES[int(numbers[1]) - 1]} {int(numbers[0])}"
    if len(numbers) == 2 and 1 <= int(numbers[1]) <= 12:
        return f"{MONTH_NAMES[int(numbers[1]) - 1]} {int(numbers[0])}"
    return numbers[0] if len(numbers) == 1 else ""
