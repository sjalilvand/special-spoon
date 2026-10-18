"""رجیستری فرم‌های بالینی نسخه‌دار سامانه (بند ۶.۲ سند)

هر فرم با کد یکتای RS-PS-XX-XX در این رجیستری ثبت می‌شود:
- تعریف فرم از ماژول همان فرم خوانده می‌شود (نسخه‌داری حفظ می‌شود).
- API ارزیابی‌ها بر اساس این رجیستری، تعریف فرم را سرو و اعتبارسنجی
  نهایی‌سازی را به ماژول همان فرم واگذار می‌کند.
- افزودن فرم جدید = افزودن ماژول تعریف + یک سطر در FORM_REGISTRY.

فرم‌های پیاده‌سازی‌شده:
- RS-PS-01-01: فرم پذیرش اولیه مراجعان تلفنی
- RS-PS-04-01: فرم پذیرش و تشکیل پرونده مراجع (نسخه ۳ — از قبل موجود)
- RS-PS-08-01: فرم ارزیابی و مدیریت مورد حاد / پر خطر
"""
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable

from fastapi import HTTPException


@dataclass(frozen=True)
class FormMeta:
    code: str
    title: str
    module: str
    description: str
    usage: str  # جایگاه در گردش کار (برای نمایش در انتخاب فرم و نمودارهای BPMN)


FORM_REGISTRY: dict[str, FormMeta] = {
    "RS-PS-01-01": FormMeta(
        code="RS-PS-01-01",
        title="فرم پذیرش اولیه مراجعان تلفنی",
        module="app.core.form_rs_ps_01_01",
        description=(
            "ثبت اطلاعات فردی مراجع تلفنی، ارزیابی اولیه موضوع مراجعه و اقدامات انجام‌شده؛ "
            "خروجی این فرم تعیین مسیر مراجع است: پذیرش حضوری و تشکیل پرونده (RS-PS-04-01) "
            "یا فعال‌سازی فرایند مورد حاد/پرخطر (RS-PS-08-01)."
        ),
        usage="پذیرش تلفنی — مرحله نخست گردش کار",
    ),
    "RS-PS-04-01": FormMeta(
        code="RS-PS-04-01",
        title="فرم پذیرش و تشکیل پرونده مراجع",
        module="app.core.form_rs_ps_04_01",
        description=(
            "ارزیابی تخصصی حضوری شامل تاریخچه بیماری، معاینه وضعیت روانی (MSE)، "
            "ارزیابی خطر، تشخیص و طرح درمان؛ پس از نهایی‌سازی برای تأیید مسئول فنی ارسال می‌شود."
        ),
        usage="پذیرش حضوری و تشکیل پرونده",
    ),
    "RS-PS-08-01": FormMeta(
        code="RS-PS-08-01",
        title="فرم ارزیابی و مدیریت مورد حاد / پر خطر",
        module="app.core.form_rs_ps_08_01",
        description=(
            "ارزیابی موارد حاد و پرخطر (خودکشی، آسیب به خود/دیگران، کودک‌آزاری، خشونت، بحران شدید)، "
            "تعیین سطح فوریت، ثبت اقدام فوری، اطلاعات ارجاع و پیگیری تا وضعیت نهایی."
        ),
        usage="مدیریت مورد حاد/پرخطر — از پذیرش تلفنی یا جلسه درمان قابل فعال‌سازی است",
    ),
}


def get_form_meta(form_code: str) -> FormMeta:
    meta = FORM_REGISTRY.get(form_code)
    if meta is None:
        raise HTTPException(status_code=404, detail="فرم یافت نشد")
    return meta


def get_form_module(form_code: str):
    """بارگذاری تنبل ماژول تعریف فرم."""
    meta = get_form_meta(form_code)
    return import_module(meta.module)


def list_forms() -> list[dict[str, Any]]:
    """فهرست فرم‌های منتشرشده برای انتخاب هنگام ایجاد ارزیابی جدید."""
    out: list[dict[str, Any]] = []
    for meta in FORM_REGISTRY.values():
        mod = import_module(meta.module)
        out.append({
            "code": meta.code,
            "title": meta.title,
            "description": meta.description,
            "usage": meta.usage,
            "version": mod.FORM_VERSION,
        })
    return out


def get_form_definition(form_code: str) -> dict[str, Any]:
    return get_form_module(form_code).FORM_DEFINITION


def get_form_version(form_code: str) -> int:
    return get_form_module(form_code).FORM_VERSION


def validate_finalization(form_code: str, answers: dict) -> list[dict]:
    """اعتبارسنجی نهایی‌سازی به قواعد اختصاصی همان فرم واگذار می‌شود."""
    mod = get_form_module(form_code)
    fn: Callable[[dict], list[dict]] = getattr(mod, "validate_finalization", None)
    if fn is None:
        return []
    return fn(answers or {})
