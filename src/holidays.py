"""Korean public holidays.

Provides fixed-date holidays and lunar-based holidays (설날, 추석, 부처님오신날)
via a pre-computed lookup table for 2024–2030.
"""

from __future__ import annotations

from datetime import date

# ---------------------------------------------------------------------------
# Fixed-date public holidays (every year)
# ---------------------------------------------------------------------------

_FIXED_HOLIDAYS: list[tuple[int, int, str]] = [
    (1, 1, "신정"),
    (3, 1, "삼일절"),
    (5, 5, "어린이날"),
    (6, 6, "현충일"),
    (8, 15, "광복절"),
    (10, 3, "개천절"),
    (10, 9, "한글날"),
    (12, 25, "성탄절"),
]

# ---------------------------------------------------------------------------
# Lunar-based holidays — pre-computed (year → list of (month, day, name))
# Includes 설날 (전날/당일/다음날), 추석 (전날/당일/다음날), 부처님오신날
# ---------------------------------------------------------------------------

_LUNAR_HOLIDAYS: dict[int, list[tuple[int, int, str]]] = {
    2024: [
        (2, 9, "설날 연휴"),
        (2, 10, "설날"),
        (2, 11, "설날 연휴"),
        (2, 12, "대체공휴일"),
        (5, 15, "부처님오신날"),
        (9, 16, "추석 연휴"),
        (9, 17, "추석"),
        (9, 18, "추석 연휴"),
    ],
    2025: [
        (1, 28, "설날 연휴"),
        (1, 29, "설날"),
        (1, 30, "설날 연휴"),
        (5, 5, "부처님오신날"),  # 어린이날과 겹침
        (5, 6, "대체공휴일"),
        (10, 5, "추석 연휴"),
        (10, 6, "추석"),
        (10, 7, "추석 연휴"),
        (10, 8, "대체공휴일"),
    ],
    2026: [
        (2, 16, "설날 연휴"),
        (2, 17, "설날"),
        (2, 18, "설날 연휴"),
        (5, 24, "부처님오신날"),
        (5, 25, "대체공휴일"),
        (9, 24, "추석 연휴"),
        (9, 25, "추석"),
        (9, 26, "추석 연휴"),
    ],
    2027: [
        (2, 6, "설날 연휴"),
        (2, 7, "설날"),
        (2, 8, "설날 연휴"),
        (2, 9, "대체공휴일"),
        (5, 13, "부처님오신날"),
        (9, 14, "추석 연휴"),
        (9, 15, "추석"),
        (9, 16, "추석 연휴"),
    ],
    2028: [
        (1, 25, "설날 연휴"),
        (1, 26, "설날"),
        (1, 27, "설날 연휴"),
        (5, 2, "부처님오신날"),
        (10, 2, "추석 연휴"),
        (10, 3, "추석"),
        (10, 4, "추석 연휴"),
    ],
    2029: [
        (2, 12, "설날 연휴"),
        (2, 13, "설날"),
        (2, 14, "설날 연휴"),
        (5, 20, "부처님오신날"),
        (9, 21, "추석 연휴"),
        (9, 22, "추석"),
        (9, 23, "추석 연휴"),
        (9, 24, "대체공휴일"),
    ],
    2030: [
        (2, 2, "설날 연휴"),
        (2, 3, "설날"),
        (2, 4, "설날 연휴"),
        (5, 9, "부처님오신날"),
        (9, 11, "추석 연휴"),
        (9, 12, "추석"),
        (9, 13, "추석 연휴"),
    ],
}


def get_holidays(year: int, month: int) -> dict[int, str]:
    """Return {day: holiday_name} for the given year/month.

    If a date has multiple holidays (e.g. 어린이날 + 부처님오신날),
    the names are joined with " / ".
    """
    result: dict[int, str] = {}

    # Fixed holidays
    for m, d, name in _FIXED_HOLIDAYS:
        if m == month:
            result[d] = name

    # Lunar holidays
    for m, d, name in _LUNAR_HOLIDAYS.get(year, []):
        if m == month:
            if d in result:
                result[d] = f"{result[d]} / {name}"
            else:
                result[d] = name

    return result


def is_holiday(d: date) -> str | None:
    """Return the holiday name for the given date, or None."""
    holidays = get_holidays(d.year, d.month)
    return holidays.get(d.day)
