"""فاز ۲۵ — دسته ۵ آزمون سند (Security): ماتریس دسترسی نقش×مسیر

بند سند: «هر مسیر با یک permission چک می‌شود؛ نه فقط پنهان‌سازی UI»
و «تست خودکار ماتریس دسترسی در هر PR».

الگوریتم: برای هر نقش، مسیرهای حساس را با نتیجه موردانتظار (کد وضعیت)
مقایسه می‌کنیم. نکته: مسیرهای با منبع ناموجود باید 404 برگردانند نه 403،
لذا برای آزمون مجاز/غیرمجاز از منابع واقعی موجود استفاده می‌شود.
"""
from conftest import bearer, login

def _h(client, who):
    """توکن Bearer بر اساس نام کاربری - الگوی سایر تست‌های مخزن."""
    return bearer(login(client, who))


API = "/api/v1"

# کدگذاری نتیجه موردانتظار:
#   "public"  → بدون احراز هویت قابل دسترس (2xx)
#   "auth"    → 401 بدون توکن، 403 برای نقش فاقد مجوز
#   "open"    → 2xx برای هر کاربر احرازشده
MATRIX = [
    # (مسیر، انتظار بدون توکن، نقش‌های مجاز؛ بقیه نقش‌های فعال 403 یا 404 می‌گیرند)
    ("/health", "public", None),
    ("/notifications", "auth", None),          # همه کاربران احرازشده
    ("/notifications/unread-count", "auth", None),
    ("/consent-versions", "auth", None),       # خواندن نسخه رضایت برای همه احرازشده
    ("/consent-versions", "auth", "POST:SYSTEM_ADMIN"),
    ("/files", "auth", None),
    ("/worklists/supervisor", "auth", ("TECHNICAL_SUPERVISOR",)),
    ("/worklists/level3", "auth", ("TECHNICAL_SUPERVISOR",)),
    ("/users", "auth", ("SYSTEM_ADMIN",)),
    ("/audit-events", "auth", None),  # همه احرازشده؛ دامنه رخدادها بر اساس نقش
    ("/reports/summary", "auth", ("SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "RECEPTION", "COUNSELOR")),
]


def test_unauthenticated_gets_401_on_protected(client):
    """هر مسیر محافظت‌شده بدون توکن باید 401 بدهد؛ نه 403 نه 2xx."""
    for path, public, allowed in MATRIX:
        method = "POST" if (allowed and isinstance(allowed, str) and allowed.startswith("POST:")) else "GET"
        body = {"kind": "treatment", "title": "تست", "body": "متن تست برای ماتریس دسترسی"} if method == "POST" else None
        r = client.request(method, f"{API}{path}", json=body)
        expected = (200, 404) if public == "public" else (401,)
        assert r.status_code in expected, f"{method} {path}: بدون توکن {r.status_code} گرفت، انتظار {expected}"


def test_rbac_denials(client, env):
    """نقش غیرمجاز روی مسیر حساس نباید 2xx بگیرد (403/404)."""
    tokens = {
        "APPLICANT": _h(client, "t_appa"),
        "COUNSELOR": _h(client, "t_counsa"),
        "RECEPTION": _h(client, "t_reception"),
        "ORG_MANAGER": _h(client, "t_manager"),
    }  # مقدارها آماده هدر هستند
    checks = [
        ("/worklists/supervisor", "APPLICANT"),
        ("/worklists/supervisor", "COUNSELOR"),
        ("/worklists/supervisor", "RECEPTION"),
        ("/worklists/level3", "APPLICANT"),
        ("/worklists/level3", "COUNSELOR"),
        ("/worklists/level3", "RECEPTION"),
        ("/users", "APPLICANT"),
        ("/users", "COUNSELOR"),
        ("/users", "RECEPTION"),
        ("/audit-events", "APPLICANT"),
        ("/audit-events", "COUNSELOR"),
        ("/consent-versions", "APPLICANT:POST"),
        ("/consent-versions", "RECEPTION:POST"),
        ("/consent-versions", "COUNSELOR:POST"),
    ]
    for entry in checks:
        path, who = entry
        role, method = (who.split(":") + ["GET"])[:2] if ":" in who else (who, "GET")
        headers = tokens[role]
        body = {"kind": "treatment", "title": "تست", "body": "متن تست برای ماتریس دسترسی"} if method == "POST" else None
        r = client.request(method, f"{API}{path}", json=body, headers=headers)
        assert r.status_code in (403, 404), f"{method} {path} با نقش {role}: {r.status_code} گرفت (باید 403/404 باشد)"


def test_rbac_allows(client, env):
    """نقش مجاز باید 2xx بگیرد."""
    checks = [
        ("/worklists/supervisor", "t_super", "GET"),
        ("/worklists/level3", "t_super", "GET"),
        ("/users", "t_admin", "GET"),
        ("/audit-events", "t_admin", "GET"),
        ("/audit-events", "t_manager", "GET"),
        ("/notifications", "t_counsa", "GET"),
        ("/notifications/unread-count", "t_appa", "GET"),
        ("/consent-versions", "t_appa", "GET"),
    ]
    for path, who, method in checks:
        r = client.get(f"{API}{path}", headers=_h(client, who))
        assert r.status_code == 200, f"{path} با {who}: {r.status_code} — {r.text[:200]}"


def test_applicant_cannot_read_others_notifications(client, env):
    """متقاضی فقط اعلان‌های خودش را می‌بیند؛ هیچ اعلان staff در لیست او نیست."""
    items = client.get(f"{API}/notifications", headers=_h(client, "t_appa")).json()
    for n in items["items"]:
        # اعلان‌های staff (finalized/level3) نباید برای متقاضی بیاید
        assert n["event_code"] not in ("assessment.finalized", "assessment.level3", "consent.revoked")
