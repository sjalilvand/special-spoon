"""فاز ۲۶ - UI سند ۰۸: تبدیل تاریخ شمسی سراسری (بک‌اند)"""
from datetime import date, datetime

import pytest

from app.core.dates import format_jalali, gregorian_to_jalali, jalali_to_gregorian


@pytest.mark.parametrize("greg,jalali", [
    ((2024, 8, 2), (1403, 5, 12)),
    ((2025, 3, 20), (1403, 12, 30)),   # پایان سال کبیسه ۱۴۰۳
    ((2025, 3, 21), (1404, 1, 1)),     # نوروز ۱۴۰۴
    ((2024, 3, 20), (1403, 1, 1)),     # نوروز ۱۴۰۳
    ((2026, 10, 19), (1405, 7, 27)),
    ((2021, 3, 21), (1400, 1, 1)),
])
def test_known_pairs(greg, jalali):
    assert gregorian_to_jalali(*greg) == jalali
    assert jalali_to_gregorian(*jalali) == date(*greg)


def test_round_trip_two_decades():
    d = date(2015, 1, 1)
    end = date(2035, 12, 31)
    while d <= end:
        jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
        assert jalali_to_gregorian(jy, jm, jd) == d, d
        d = date.fromordinal(d.toordinal() + 1)


def test_format_jalali_accepts_inputs():
    assert format_jalali(date(2024, 8, 2)) == "1403/05/12"
    assert format_jalali(datetime(2024, 8, 2, 10, 30)) == "1403/05/12"
    assert format_jalali("2024-08-02") == "1403/05/12"
    assert format_jalali("1403/05/12") == "1403/05/12"  # شمسی ورودی → همان خروجی
    assert format_jalali(None) is None
    assert format_jalali("") is None
