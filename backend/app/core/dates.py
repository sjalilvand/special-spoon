from datetime import date, datetime

_DIGIT_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_digits(value: str) -> str:
    return (value or "").translate(_DIGIT_TABLE)


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> date:
    if not (1 <= jm <= 12 and 1 <= jd <= 31):
        raise ValueError("تاریخ شمسی نامعتبر است")
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    month_days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    for i, md in enumerate(month_days, start=1):
        if gd <= md:
            gm = i
            break
        gd -= md
    return date(gy, gm, gd)


def parse_date_cell(value) -> date:
    """قالب مصوب: شمسی YYYY/MM/DD یا میلادی YYYY-MM-DD (بند ۸ سند: حدس بدون قاعده ممنوع)."""
    if value is None or value == "":
        raise ValueError("تاریخ خالی است")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = normalize_digits(str(value)).strip()
    try:
        if "-" in s:
            y, m, d = (int(p) for p in s.split("-"))
            return date(y, m, d)
        if "/" in s:
            y, m, d = (int(p) for p in s.split("/"))
            if 1900 <= y <= 2100:
                return date(y, m, d)
            if 1200 <= y <= 1600:
                return jalali_to_gregorian(y, m, d)
        raise ValueError
    except ValueError as e:
        if "قالب" in str(e) or "تاریخ" in str(e):
            raise
        raise ValueError(f"قالب تاریخ نامعتبر: {value} (مجاز: 1403/05/12 شمسی یا 2024-08-02 میلادی)")


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """تبدیل میلادی به شمسی - معکوس دقیق jalali_to_gregorian همین ماژول."""
    d = date(gy, gm, gd)
    jy = gy - 621
    # مبدأ مقایسه: نوروز سال شمسی جاری
    nowruz = jalali_to_gregorian(jy, 1, 1)
    if d < nowruz:
        jy -= 1
        nowruz = jalali_to_gregorian(jy, 1, 1)
    delta = (d - nowruz).days  # روز جاری از ابتدای سال شمسی (صفر-مبنا)
    if delta < 186:
        jm = delta // 31 + 1
        jd = delta % 31 + 1
    else:
        jm = (delta - 186) // 30 + 7
        jd = (delta - 186) % 30 + 1
    return jy, jm, jd


def format_jalali(value: date | datetime | str | None) -> str | None:
    """نمایش شمسی استاندارد «YYYY/MM/DD» - برای خروجی API‌های گزارش/داشبورد."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, str):
        value = parse_date_cell(value)
    jy, jm, jd = gregorian_to_jalali(value.year, value.month, value.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"
