"""فاز ۳۲ - B40 سند جامع: نقشه شعب با سرویس نقشه پلاگین‌پذیر (تصمیم D03).

همان الگوی معماری D02 (درگاه پرداخت): سرویس نقشه یک آداپتور قابل‌جایگزین است؛
تغییر سرویس فقط با config انجام می‌شود، بدون تغییر کد صفحه عمومی شعب.

سرویس‌ها (D03):
- osm: OpenStreetMap رستری + Leaflet — بدون کلید، پیش‌فرض توسعه و بدون
  هزینه؛ مناسب راه‌اندازی فوری.
- neshan: نشنال (تولید داخل ایران) — نیازمند neshan_api_key؛ بدون کلید
  «غیرفعال» گزارش می‌شود.
- mapir: Map.ir — نیازمند mapir_api_key؛ بدون کلیر «غیرفعال» گزارش می‌شود.

محرمانگی (پذیرش سند جامع):
- «مکان کاربر فقط برای مرتب‌سازی، ذخیره نمی‌شود» — مختصات کاربر در
  /public/branches/nearby فقط به‌عنوان پارامتر فراخوانی استفاده می‌شود؛
  در پایگاه‌داده نوشته نمی‌شود، در audit ثبت نمی‌شود و در پاسخ بازتاب
  نمی‌یابد (نگاه کنید به branches.public_branches_nearby).
- کلید سرویس نقشه هرگز به کلاینت ارسال نمی‌شود؛ برای سرویس‌های دارای کلید
  tile_url صادر نمی‌شود و در تولید از SDK رسمی همان سرویس استفاده می‌گردد.
"""
import math
from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass
class MapProviderInfo:
    code: str
    title: str
    enabled: bool
    is_default: bool
    tile_url: str | None
    attribution: str
    requires_key: bool


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """فاصله کروماتیک (کیلومتر) بین دو نقطه — برای مرتب‌سازی شعب نزدیک."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _providers(s: Settings) -> list[MapProviderInfo]:
    neshan_ready = bool(s.neshan_api_key)
    mapir_ready = bool(s.mapir_api_key)
    default = (s.map_provider or "osm").strip().lower()
    return [
        MapProviderInfo(
            code="osm",
            title="OpenStreetMap (Leaflet) — بدون کلید",
            enabled=True,
            is_default=default == "osm",
            tile_url="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            attribution="© OpenStreetMap contributors",
            requires_key=False,
        ),
        MapProviderInfo(
            code="neshan",
            title="نشنال (پیشنهاد تولید داخل ایران)",
            enabled=neshan_ready,
            is_default=default == "neshan",
            # کلید سمت سرور می‌ماند؛ در تولید با SDK رسمی نشنال رندر می‌شود
            tile_url=None,
            attribution="© Neshan",
            requires_key=True,
        ),
        MapProviderInfo(
            code="mapir",
            title="Map.ir (گزینه تولید)",
            enabled=mapir_ready,
            is_default=default == "mapir",
            tile_url=None,
            attribution="© Map.ir",
            requires_key=True,
        ),
    ]


def configured_map_providers(s: Settings | None = None) -> list[dict]:
    """وضعیت پیکربندی سرویس نقشه — شفافیت تصمیم D03 برای مدیریت و کلاینت."""
    s = s or get_settings()
    return [
        {
            "code": p.code,
            "title": p.title,
            "enabled": p.enabled,
            "is_default": p.is_default,
            "tile_url": p.tile_url if p.enabled else None,
            "attribution": p.attribution,
            "requires_key": p.requires_key,
        }
        for p in _providers(s)
    ]


def active_map_provider(s: Settings | None = None) -> dict:
    """سرویس فعال؛ اگر پیش‌فرض پیکربندی‌شده غیرفعال بود، به osm (بدون کلید)
    سقوط می‌کند تا نقشه همیشه رندر شود (fallback همان روح D02 است)."""
    s = s or get_settings()
    providers = _providers(s)
    for p in providers:
        if p.code == (s.map_provider or "osm").strip().lower() and p.enabled:
            chosen = p
            break
    else:
        chosen = next(p for p in providers if p.code == "osm")
    return {
        "code": chosen.code,
        "title": chosen.title,
        "tile_url": chosen.tile_url,
        "attribution": chosen.attribution,
    }
