"""داده نمونه جامع سامانه رزپسی — پر کردن همه جدول‌های اصلی با سناریوی واقع‌گرایانه.

اجرا:    docker compose run --rm api python seed_demo_rich.py
پاک‌سازی: docker compose run --rm api python seed_demo_rich.py --reset

خروجی سناریو (گردش کامل کار):
  ۱۰۰ متقاضی → ۵۸ درخواست مشاوره سایت → ۴۲ پرونده → ۳۴ تخصیص مشاور
  → ~۶۸ نوبت (پر و خالی در تقویم) → ۲۲ جلسه مشاوره انجام‌شده + یادداشت
  → ارزیابی/تأیید فرم، طرح درمان، تشخیص، مالی کامل، آزمون‌های روان‌شناسی،
    دوره‌های آموزشی، پشتیبانی، اعلان‌ها و گزارش حسابرسی.

- idempotent: اگر قبلاً اجرا شده باشد دوباره داده نمی‌سازد (شمارش متقاضی ≥ ۹۰).
- deterministic: با seed ثابت (۱۴۰۴) تا نتیجه تکرارپذیر باشد.
- حساب‌های نمونه: admin/Rosepsy@Admin2026 و counselor1..8 / reception1 /
  manager1 / supervisor1 / dpo1 / user2001..user2020 با رمز Demo@1234
  (فقط برای دمو؛ در محیط عملیاتی حتماً تغییر داده شود).
"""
from __future__ import annotations

import argparse
import hashlib
import random
import shutil
import sys
import uuid as uuid_mod
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, func, select

from app.core.security import hash_password
from app.core.forms import get_form_definition
from app.db.session import SessionLocal

# مدل‌ها
from app.models.people import Applicant, Counselor, OrganizationUnit, ServiceLocation, UserScope
from app.models.branch import Branch, BranchServiceOffering, Clinic
from app.models.user import Role, User, UserStatus
from app.models.org_contract import Contract, ContractService, Organization
from app.models.catalog import CounselorCredential, Service, Specialty, TariffVersion
from app.models.topics import ServiceTopic, Topic
from app.models.consultation import ConsultationRequest
from app.models.intake import IntakeQuestionnaire
from app.models.case import Case, CaseAssignment, Consent
from app.models.appointment import Appointment, Session, SessionNoteRevision
from app.models.booking import SlotClaim
from app.models.clinical import Diagnosis, TreatmentPlan
from app.models.recommendation import Recommendation
from app.models.referral import Referral
from app.models.assessment import Assessment, FormVersion, ReviewAction
from app.models.payment import Invoice, InvoiceItem, Order, Payment
from app.models.discount import Discount, DiscountRedemption
from app.models.wallet import Wallet, WalletEntry
from app.models.refund import Refund, RefundRequest
from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.psych_test import PsychAttempt, PsychInterpretation, PsychQuestion, PsychTest
from app.models.learning import (
    Certificate, Content, Course, CourseEnrollment, CourseSession,
    Exam, ExamAttempt, ExamQuestion,
)
from app.models.support import Complaint, SessionSurvey, Ticket, TicketMessage
from app.models.notification import Notification
from app.models.email_outbox import EmailOutbox
from app.models.integration import SmsOutbox
from app.models.audit import AuditEvent
from app.models.import_job import ImportJob, ImportRow
from app.models.process import (
    ProcessDefinition, ProcessInstance, ProcessInstanceEvent, ProcessVersion,
)

TZ = timezone(timedelta(hours=3, minutes=30))
TODAY = date.today()
NOW = datetime.now(TZ).replace(minute=0, second=0, microsecond=0)

rng = random.Random(1404)

# ---------------------------------------------------------------- استخرها
MALE = ["علی", "محمد", "رضا", "حسین", "امیر", "مهدی", "سعید", "کاوه", "بهنام", "آرش",
        "فرهاد", "بابک", "نیما", "پویا", "سامان", "احسان", "وحید", "سینا", "کیان", "آرمان"]
FEMALE = ["مریم", "زهرا", "فاطمه", "سارا", "نگار", "الهام", "نازنین", "شیرین", "پریسا", "لیلا",
          "سمانه", "رویا", "مهسا", "آیدا", "نیلوفر", "ترانه", "بهاره", "شیما", "عسل", "کیمیا"]
LAST = ["رضایی", "محمدی", "حسینی", "کریمی", "صادقی", "موسوی", "جعفری", "نوری", "اکبری", "احمدی",
        "شریفی", "قاسمی", "دهقان", "یوسفی", "مرادی", "امینی", "فرهادی", "کاظمی", "رسولی", "همتی",
        "تهرانی", "اصفهانی", "شیرازی", "بابایی", "زارعی", "رحیمی", "سلیمانی", "نجفی", "خسروی", "عباسی"]

PROVINCE_CITY = [("تهران", "تهران"), ("البرز", "کرج"), ("اصفهان", "اصفهان"), ("فارس", "شیراز"),
                 ("خراسان رضوی", "مشهد"), ("آذربایجان شرقی", "تبریز"), ("گیلان", "رشت"), ("یزد", "یزد")]
OCCUPATIONS = ["کارمند اداری", "دانشجو", "معلم", "مهندس", "پرستار", "خانه‌دار", "شاغل آزاد",
               "حسابدار", "راننده", "کارشناس فروش", "برنامه‌نویس", "مدیر فروشگاه", "بازرس ایمنی"]
EDUCATIONS = ["دیپلم", "کاردانی", "کارشناسی", "کارشناسی ارشد", "دکتری"]
REF_SOURCES = ["وب‌سایت", "تماس تلفنی", "معرفی سازمان", "اینستاگرام", "معرف خانواده", "بیمه‌گر"]

REQUEST_TOPICS = ["اضطراب و حملات پنیک", "افسردگی و بی‌انگیزگی", "تعارض زناشویی", "مشکلات رفتاری کودک",
                  "استرس شغلی و فرسودگی", "مشاوره پیش از ازدواج", "اختلال خواب", "وسواس فکری - عملی",
                  "مشکلات تحصیلی نوجوان", "سوگ و فقدان"]
REQUEST_MSGS = [
    "چند ماه است دچار تپش قلب و نگرانی مداوم هستم؛ برای مشاوره حضوری راهنمایی می‌خواهم.",
    "به‌تازگی افت شدید انرژی و خواب را تجربه می‌کنم و انجام کارهای روزمره سخت شده است.",
    "اختلاف جدی با همسرم داریم و مایلیم زوج‌درمانی شروع کنیم؛ اسلات آخر هفته مدنظرمان است.",
    "فرشته هفت‌ساله‌ام رفتار پرخاشگرانه در مدرسه دارد؛ برای بازی‌درمانی وقت می‌خواهم.",
    "بعد از تغییر شغل دچار فرسودگی شدم؛ مشاوره آنلاین برایم مناسب‌تر است.",
    "برای مشاوره پیش از ازدواج نیاز به دو جلسه ارزیابی داریم.",
    "ماه‌هاست بی‌خوابی و وسواس فکری دارم؛ لطفاً امکان وقت اضطراری را بررسی کنید.",
    "پسر نوجوانم افت تحصیلی شدید دارد و انگیزه‌ای برای درس ندارد.",
    "پس از فقدان والد، دوره سوگ طولانی‌مدتی را می‌گذرانم و نیاز به حمایت تخصصی دارم.",
    "برای مدیریت خشم و تعامل بهتر با همکاران، مشاوره فردی درخواست می‌کنم.",
]
DIAGNOSES = [("اختلال اضطراب فراگیر", "F41.1", "confirmed"), ("افسردگی اساسی - دوره متوسط", "F32.1", "confirmed"),
             ("وسواس فکری - عملی", "F42.2", "confirmed"), ("اختلال استرس پس از سانحه", "F43.1", "probable"),
             ("اختلال وحشت‌زدگی", "F41.0", "confirmed"), ("اختلال سازگاری با واکنش افسرده‌وار", "F43.21", "under_review"),
             ("اختلال خواب غیرارگانیک", "F51.1", "probable")]
COMPLAINTS = ["تپش قلب و نگرانی مداوم", "خلق پایین و بی‌علاقگی", "تعارض‌های مکرر با همسر",
              "پرخاشگری کودک در مدرسه", "فرسودگی شغلی", "بی‌خوابی مزمن"]

NOTE_SOAP = [
    ("مراجع از کاهش شدت نشانه‌ها گزارش می‌دهد؛ تمرین‌های تن‌آرامی هفته گذشته انجام شده است.",
     "تماس چشمی مناسب، گفتار منسجم، اثر شناختی سالم.",
     "پاسخ‌دهی اولیه به CBT مطلوب است؛ مقیاس BAI افت ۴ نمره‌ای نشان می‌دهد.",
     "ادامه ساختار جلسات هفتگی؛ تمرین ثبت افکار خودآینده و بازبینی در جلسه بعد."),
    ("مراجع درباره فشارهای شغلی و تعارض با سرپرست صحبت می‌کند.",
     "اضطراب آشکار در پردازش موضوع کاری، عاطفه کمی فشرده.",
     "الگوی اجتناب شناختی محرک‌های سازمانی شناسایی شد.",
     "آموزش مهارت قاطعیت و برنامه‌ریزی تدریجی مواجهه با موقعیت‌های پرتنش."),
    ("بهبود الگوی خواب گزارش می‌شود؛ بیدارهای شبانه از ۴ به ۱ کاهش یافته است.",
     "ظاهر پذیرفتنی، خلق کمی بهبودیافته نسبت به جلسه قبل.",
     "بهداشت خواب و روان‌آموزش مؤثر بوده است.",
     "ادامه بهداشت خواب + شروع مواجهه‌درمانی تدریجی؛ جلسه بعد ارزیابی پیشرفت."),
]


def fa_dt(d: datetime) -> datetime:
    return d


def dt_days_ago(days: int, hour: int = 11, minute: int = 0) -> datetime:
    base = NOW - timedelta(days=days)
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def workday(offset: int) -> date:
    """تاریخ کاری: از امروز با جابجایی، آخر هفته (پنجشنبه/جمعه) را رد می‌کند."""
    d = TODAY + timedelta(days=offset)
    while d.weekday() in (3, 4):  # پنجشنبه=3، جمعه=4
        d += timedelta(days=1 if offset >= 0 else -1)
    return d


def gen_mobile(used: set) -> str:
    while True:
        m = "0912" + f"{rng.randint(1000000, 9999999)}"
        if m not in used:
            used.add(m)
            return m


def gen_national_id(used: set) -> str:
    while True:
        n = "00" + f"{rng.randint(10000000, 99999999)}"
        if n not in used:
            used.add(n)
            return n


def get_or_create(db, model, defaults: dict | None = None, **keys):
    """بازگرداندن ردیف موجود بر اساس کلید یکتا یا ساخت آن — سازگار با داده قدیمی seed_demo.py و داده ثبت‌شده از پنل."""
    obj = db.scalar(select(model).filter_by(**keys))
    if obj is None:
        obj = model(**keys, **(defaults or {}))
        db.add(obj)
        db.flush()
    return obj


def unique_numbered(candidate: str, used: set) -> str:
    """رشته یکتا با پسوند عددی در صورت تداخل با داده‌های موجود دیتابیس."""
    if candidate not in used:
        used.add(candidate)
        return candidate
    n = 1
    while f"{candidate}-{n}" in used:
        n += 1
    out = f"{candidate}-{n}"
    used.add(out)
    return out


def make_user(db, username: str, display: str, role_code: str, password: str = "Demo@1234",
              status: str = UserStatus.ACTIVE, must_change: bool = False,
              email: str | None = None, mobile: str | None = None) -> User:
    u = db.scalar(select(User).where(User.username == username))
    if u is None:
        u = User(username=username, display_name=display, status=status,
                 must_change_password=must_change, email=email, mobile=mobile)
        u.password_hash = hash_password(password)
        db.add(u)
        db.flush()
    role = db.get(Role, role_code)
    if role is not None and role not in u.roles:
        u.roles.append(role)
    if username != "admin":
        # حساب‌های دمو (غیر از admin): فعال و با رمز مستند — حتی اگر از seed قدیمی با وضعیت PENDING مانده باشند
        u.status = UserStatus.ACTIVE
        u.must_change_password = False
        u.password_hash = hash_password("Demo@1234")
        if email and not u.email:
            u.email = email
        if mobile and not u.mobile:
            u.mobile = mobile
    return u


def sample_answers(definition: dict, applicant: Applicant) -> dict:
    """پاسخ نمونه واقع‌نما بر اساس تعریف نسخه‌دار فرم."""
    out: dict = {}
    for sec in definition.get("sections", []):
        for f in sec.get("fields", []):
            key, ftype = f.get("key"), f.get("type", "text")
            opts = f.get("options") or []
            if ftype == "select" and opts:
                out[key] = opts[0]["value"]
            elif key == "form_date":
                out[key] = "۱۴۰۴/۰۷/۱۲"
            elif key in ("education",):
                out[key] = applicant.education or "کارشناسی"
            elif key in ("job",):
                out[key] = applicant.occupation or "کارمند"
            elif key in ("province",):
                out[key] = applicant.province_code or "تهران"
            elif ftype in ("text", "textarea"):
                out[key] = "ثبت نمونه در داده دمو"
            elif ftype == "number":
                out[key] = 0
    return out


# ================================================================ بخش‌های seed

def seed_base(db) -> dict:
    """واحدها، محل‌های خدمت، سازمان‌ها/قرارداد، دسته‌ها، خدمات/تعرفه، مشاوران."""
    ref: dict = {}
    u1 = get_or_create(db, OrganizationUnit, defaults={"title": "واحد اداری و پذیرش"}, code="U1")
    u2 = get_or_create(db, OrganizationUnit, defaults={"title": "واحد بالینی"}, code="U2")
    u3 = get_or_create(db, OrganizationUnit, defaults={"title": "واحد فروش و بازاریابی"}, code="U3")
    u4 = get_or_create(db, OrganizationUnit, defaults={"title": "واحد پشتیبانی فنی", "parent_id": u3.id}, code="U4")
    l1 = get_or_create(db, ServiceLocation, defaults={"title": "کلینیک مرکزی - ولیعصر", "address": "تهران، خیابان ولیعصر، پلاک ۱۲۴۰، طبقه ۳"}, code="L1")
    l2 = get_or_create(db, ServiceLocation, defaults={"title": "شعبه شمال تهران", "address": "تهران، سعادت‌آباد، بلوار دریا، پلاک ۸۸"}, code="L2")
    l3 = get_or_create(db, ServiceLocation, defaults={"title": "شعبه اصفهان", "address": "اصفهان، خیابان چهارباغ بالا، پلاک ۲۲۰"}, code="L3")
    db.flush()
    ref["units"] = [u1, u2, u3, u4]
    ref["locations"] = [l1, l2, l3]

    # کاربران ستاد (پذیرش/مدیر سازمان/مسئول فنی/DPO) + admin
    ref["admin"] = make_user(db, "admin", "مدیر سامانه", "SYSTEM_ADMIN",
                             password="Rosepsy@Admin2026", email="admin@rosepsy.demo")
    ref["reception"] = make_user(db, "reception1", "زهرا کاظمی - پذیرش", "RECEPTION",
                                 email="reception@rosepsy.demo")
    ref["manager"] = make_user(db, "manager1", "فرهاد تهرانی - مدیر سازمان", "ORG_MANAGER",
                               email="manager@rosepsy.demo")
    ref["supervisor"] = make_user(db, "supervisor1", "کیان سلیمانی - مسئول فنی", "TECHNICAL_SUPERVISOR",
                                  email="supervisor@rosepsy.demo")
    ref["dpo"] = make_user(db, "dpo1", "شیرین نجفی - حسابرس حفاظت داده", "DPO",
                           email="dpo@rosepsy.demo")
    db.flush()

    # سازمان‌های کارفرما + قرارداد
    o1 = get_or_create(db, Organization, defaults={"name": "سازمان فناوری پارس", "phone": "02188776655", "email": "hr@parstech.ir", "address": "تهران، میدان آرژانتین"}, slug="pars-tech")
    o2 = get_or_create(db, Organization, defaults={"name": "هلدینگ ساختمانی آرمان", "phone": "02144556677", "email": "welfare@arman.ir", "address": "تهران، میدان ونک"}, slug="arman-holding")
    o3 = get_or_create(db, Organization, defaults={"name": "آموزشگاه رشد", "phone": "03136655443", "email": "admin@roshd.edu", "address": "اصفهان، خیابان سعادت"}, slug="roshd-edu")
    db.flush()
    c1 = get_or_create(db, Contract, defaults={"coverage_percent": 70, "valid_from": date(TODAY.year, 1, 1), "status": "active"}, organization_id=o1.id, title="قرارداد خدمات روان‌شناسی کارکنان ۱۴۰۴")
    c2 = get_or_create(db, Contract, defaults={"coverage_percent": 50, "valid_from": date(TODAY.year, 1, 1), "status": "active"}, organization_id=o2.id, title="قرارداد بهره‌وری و سلامت روان ۱۴۰۴")
    c3 = get_or_create(db, Contract, defaults={"coverage_percent": 60, "valid_from": date(TODAY.year, 2, 1), "status": "active"}, organization_id=o3.id, title="قرارداد حمایت معلمان و کادر آموزشی")
    ref["orgs"] = [o1, o2, o3]
    ref["contracts"] = [c1, c2, c3]

    # دسته‌های موضوعی + تخصص‌ها + خدمات + تعرفه
    topic_names = ["استرس و اضطراب", "افسردگی و خلق", "روابط زناشویی", "فرزندپروری",
                   "بهره‌وری شغلی", "سوگ و فقدان"]
    topics = [get_or_create(db, Topic,
                            defaults={"name": n, "sort_order": i, "is_active": True},
                            slug=f"t{i+1}-{['stress','mood','couples','parenting','work','grief'][i]}")
              for i, n in enumerate(topic_names)]

    sp_names = ["اضطراب و استرس", "افسردگی و اختلالات خلق", "زوج و خانواده درمانی",
                "کودک و نوجوان", "روان‌شناسی شغلی و سازمانی", "آسیب‌شناسی و تروما"]
    sps = [get_or_create(db, Specialty, name=n) for n in sp_names]
    db.flush()

    svc_data = [
        ("SRV-01", "مشاوره فردی بالینی", 0, 60, "in_person", 1200000),
        ("SRV-02", "درمان شناختی - رفتاری (CBT)", 1, 60, "in_person", 1500000),
        ("SRV-03", "زوج‌درمانی ساختاری", 2, 80, "in_person", 1900000),
        ("SRV-04", "بازی‌درمانی کودک", 3, 45, "in_person", 1400000),
        ("SRV-05", "مشاوره آنلاین فردی", 0, 50, "online", 900000),
        ("SRV-06", "مشاوره شغلی و سازمانی", 4, 60, "online", 1100000),
        ("SRV-07", "مشاوره تلفنی مدیریت استرس", 0, 30, "phone", 600000),
        ("SRV-08", "ارزیابی و مصاحبه بالینی اولیه", 5, 80, "in_person", 1800000),
    ]
    services = []
    for code, title, sp_i, dur, stype, amount in svc_data:
        s = get_or_create(db, Service,
                          defaults={"title": title, "duration_minutes": dur, "session_type": stype,
                                    "status": "active", "created_by": ref["admin"].id,
                                    "description": f"خدمت {title} با مدت {dur} دقیقه توسط مشاوران دارای صلاحیت B05 ارائه می‌شود."},
                          code=code, specialty_id=sps[sp_i].id)
        services.append(s)
    for (code, title, sp_i, dur, stype, amount), s in zip(svc_data, services):
        get_or_create(db, TariffVersion,
                      defaults={"amount": amount, "currency": "IRR", "note": "تعرفه مصوب ۱۴۰۴",
                                "created_by": ref["admin"].id},
                      service_id=s.id, valid_from=date(2025, 6, 1))
    # نسخه قدیمی بسته‌شده برای SRV-02 (نمایش نسخه‌داری تعرفه)
    get_or_create(db, TariffVersion,
                  defaults={"amount": 1200000, "currency": "IRR", "valid_to": date(2025, 5, 31),
                            "note": "تعرفه سال ۱۴۰۳ (بسته‌شده)", "created_by": ref["admin"].id},
                  service_id=services[1].id, valid_from=date(2024, 6, 1))
    for s, t in zip(services, [topics[0], topics[1], topics[2], topics[3], topics[0], topics[4], topics[0], topics[5]]):
        get_or_create(db, ServiceTopic, service_id=s.id, topic_id=t.id)
    # خدمات تحت پوشش قرارداد سازمان‌ها
    for contract, idxs in ((c1, (0, 1, 4)), (c2, (0, 2, 6)), (c3, (3, 5))):
        for ix in idxs:
            get_or_create(db, ContractService, contract_id=contract.id, service_id=services[ix].id)
    db.flush()
    ref["services"] = services
    ref["topics"] = topics

    tariff_of = {s.id: svc_data[[x[0] for x in svc_data].index(s.code)][5] for s in services}
    ref["tariff_of"] = tariff_of

    # مشاوران + حساب‌ها + مدارک
    counselors_data = [
        ("C-1001", "سارا", "محمدی", "روان‌شناس بالینی", "دکتری تخصصی", 0, 10, 0),
        ("C-1002", "رضا", "احمدی", "روان‌درمانگر", "کارشناسی ارشد", 1, 8, 0),
        ("C-1003", "مریم", "حسینی", "زوج‌درمانگر", "دکتری تخصصی", 2, 8, 1),
        ("C-1004", "نیما", "کریمی", "بازی‌درمانگر کودک", "کارشناسی ارشد", 3, 6, 1),
        ("C-1005", "نگار", "رضایی", "روان‌شناس سازمانی", "کارشناسی ارشد", 4, 8, 2),
        ("C-1006", "امیر", "موسوی", "روان‌شناس بالینی", "دکتری تخصصی", 5, 7, 0),
        ("C-1007", "الهام", "صادقی", "روان‌درمانگر", "کارشناسی ارشد", 0, 9, 0),
        ("C-1008", "بهنام", "نوری", "مشاور خانواده", "کارشناسی ارشد", 2, 6, 2),
    ]
    counselors: list[Counselor] = []
    for i, (code, fn, ln, title, degree, sp_i, cap, loc_i) in enumerate(counselors_data):
        acc = make_user(db, f"counselor{i+1}", f"{fn} {ln}", "COUNSELOR",
                        email=f"counselor{i+1}@rosepsy.demo", mobile=f"0912000{i+1:05d}")
        c = db.scalar(select(Counselor).where(Counselor.counselor_code == code))
        if c is None:
            c = Counselor(counselor_code=code, first_name=fn, last_name=ln,
                          professional_title=title, degree=degree,
                          specialty=sp_names[sp_i], capacity=cap, status="active",
                          service_location_id=ref["locations"][loc_i].id,
                          license_number=f"LIC-{1000+i}", license_verified=True,
                          work_mobile=f"0912000{i+1:05d}", email=f"counselor{i+1}@rosepsy.demo")
            db.add(c)
            db.flush()
        c.user_id = acc.id
        # تکمیل فیلدهای خالی مشاور موجود (مثلاً از seed قدیمی) برای نمایش بهتر
        if not c.license_number:
            c.license_number = f"LIC-{1000+i}"
            c.license_verified = True
        if not c.email:
            c.email = f"counselor{i+1}@rosepsy.demo"
        if not c.work_mobile:
            c.work_mobile = f"0912000{i+1:05d}"
        if not c.service_location_id:
            c.service_location_id = ref["locations"][loc_i].id
        if db.scalar(select(CounselorCredential).where(
                CounselorCredential.counselor_id == c.id,
                CounselorCredential.kind == "license")) is None:
            db.add(CounselorCredential(counselor_id=c.id, kind="license", title="پروانه نظام روان‌شناسی",
                                       license_number=f"LIC-{1000+i}", issued_at=date(2021, 4, 1),
                                       expires_at=date(TODAY.year + 1, 4, 1),
                                       verification_status="approved", reviewed_by=ref["supervisor"].id,
                                       review_note="مدرک معتبر است"))
        if db.scalar(select(CounselorCredential).where(
                CounselorCredential.counselor_id == c.id,
                CounselorCredential.kind == "degree")) is None:
            db.add(CounselorCredential(counselor_id=c.id, kind="degree", title=f"مدرک {degree}",
                                       verification_status="approved" if i not in (3, 7) else "pending",
                                       reviewed_by=ref["supervisor"].id if i not in (3, 7) else None))
        counselors.append(c)
    db.flush()
    ref["counselors"] = counselors
    seed_counselor_photos(counselors)
    return ref


# عکس‌های پیش‌فرض مشاوران (فاز ۴۹) — خانم‌ها با حجاب اسلامی؛ فایل‌ها از
# backend/avatar_seed به uploads/counselor_photos کپی می‌شوند تا هم سایت
# عمومی و هم پنل، بدون آپلود دستی، عکس واقعی نشان دهند.
FEMALE_FIRST = {"سارا", "مریم", "نگار", "الهام", "زهرا", "فاطمه", "نازنین", "شیرین",
                "پریسا", "لیلا", "سمانه", "رویا", "مهسا", "آیدا", "نیلوفر", "ترانه",
                "بهاره", "شیما", "عسل", "کیمیا"}
AVATAR_DIR = Path("avatar_seed")
AVATAR_UPLOAD_DIR = Path("uploads") / "counselor_photos"
FEMALE_AVATARS = ["f1.jpg", "f2.jpg", "f3.jpg"]
MALE_AVATARS = ["m1.jpg", "m2.jpg", "m3.jpg"]


def seed_counselor_photos(counselors: list[Counselor]) -> None:
    if not AVATAR_DIR.exists():
        return
    AVATAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    f_i = m_i = 0
    for c in counselors:
        if c.photo_path and (Path("uploads") / c.photo_path).is_file():
            continue  # عکس قبلی معتبر است (مثلاً آپلود دستی) — دست نمی‌زنیم
        if c.first_name in FEMALE_FIRST:
            fname = FEMALE_AVATARS[f_i % len(FEMALE_AVATARS)]
            f_i += 1
        else:
            fname = MALE_AVATARS[m_i % len(MALE_AVATARS)]
            m_i += 1
        src = AVATAR_DIR / fname
        if not src.is_file():
            continue
        dst = AVATAR_UPLOAD_DIR / f"{c.counselor_code}.jpg"
        shutil.copyfile(src, dst)
        c.photo_path = f"counselor_photos/{dst.name}"


# ---------------------------------------------------------------- شعب ۳۱ استان
# فاز ۴۹: برای هر استان یک شعبه با موقعیت پیش‌فرض (مرکز استان) ثبت می‌شود؛
# همه فیلدها از پنل «شعب» قابل ویرایش و در نقشه B40 نمایش داده می‌شوند.
IRAN_PROVINCES: list[tuple[str, str, float, float, str]] = [
    # (استان، مرکز، عرض، طول، کد تلفن)
    ("تهران", "تهران", 35.6892, 51.3890, "021"),
    ("البرز", "کرج", 35.8355, 50.9915, "026"),
    ("اصفهان", "اصفهان", 32.6539, 51.6660, "031"),
    ("فارس", "شیراز", 29.5918, 52.5837, "071"),
    ("خراسان رضوی", "مشهد", 36.2605, 59.6168, "051"),
    ("آذربایجان شرقی", "تبریز", 38.0962, 46.2738, "041"),
    ("آذربایجان غربی", "ارومیه", 37.5527, 45.0759, "044"),
    ("اردبیل", "اردبیل", 38.2498, 48.2933, "045"),
    ("ایلام", "ایلام", 33.6374, 46.4227, "084"),
    ("بوشهر", "بوشهر", 28.9234, 50.8203, "077"),
    ("چهارمحال و بختیاری", "شهرکرد", 32.3256, 50.8644, "038"),
    ("خراسان جنوبی", "بیرجند", 32.8663, 59.2211, "056"),
    ("خراسان شمالی", "بجنورد", 37.4747, 57.3290, "058"),
    ("خوزستان", "اهواز", 31.3183, 48.6706, "061"),
    ("زنجان", "زنجان", 36.6736, 48.4787, "024"),
    ("سمنان", "سمنان", 35.5729, 53.3970, "023"),
    ("سیستان و بلوچستان", "زاهدان", 29.4963, 60.8629, "054"),
    ("قزوین", "قزوین", 36.2797, 50.0049, "028"),
    ("قم", "قم", 34.6416, 50.8746, "025"),
    ("کردستان", "سنندج", 35.3219, 46.9862, "087"),
    ("کرمان", "کرمان", 30.2839, 57.0834, "034"),
    ("کرمانشاه", "کرمانشاه", 34.3142, 47.0650, "083"),
    ("کهگیلویه و بویراحمد", "یاسوج", 30.6684, 51.5879, "074"),
    ("گلستان", "گرگان", 36.8456, 54.4393, "017"),
    ("گیلان", "رشت", 37.2808, 49.5832, "013"),
    ("لرستان", "خرم‌آباد", 33.4878, 48.3558, "066"),
    ("مازندران", "ساری", 36.5633, 53.0601, "011"),
    ("مرکزی", "اراک", 34.0917, 49.6892, "086"),
    ("هرمزگان", "بندرعباس", 27.1865, 56.2808, "076"),
    ("همدان", "همدان", 34.7983, 48.5148, "081"),
    ("یزد", "یزد", 31.8974, 54.3569, "035"),
]


def seed_provinces(db, ref) -> None:
    """یک مرکز + ۳۱ شعبه استانی با موقعیت پیش‌فرض (قابل ویرایش از پنل)."""
    clinic = db.scalar(select(Clinic).where(Clinic.slug == "rosepsy-main"))
    if clinic is None:
        clinic = Clinic(
            name="کلینیک رزپسی — مرکز", slug="rosepsy-main",
            description="شبکه ملی مراکز مشاوره رزپسی — پوشش ۳۱ استان کشور",
            phone="02191008000", website="https://rosepsy.ir",
            created_by=ref["admin"].id,
        )
        db.add(clinic)
        db.flush()
    services = ref["services"]
    for prov, city, lat, lng, area in IRAN_PROVINCES:
        b = db.scalar(select(Branch).where(
            Branch.clinic_id == clinic.id, Branch.province == prov))
        if b is None:
            b = Branch(
                clinic_id=clinic.id, name=f"شعبه {prov}", province=prov, city=city,
                address=f"{prov}، {city}، خیابان اصلی، ساختمان رزپسی",
                phone=f"{area}91000000",
                latitude=lat, longitude=lng, status="published",
                created_by=ref["admin"].id,
            )
            db.add(b)
            db.flush()
        else:
            # تکمیل مختصات/وضعیت شعبه موجود (سازگاری با داده قبلی)
            if b.latitude is None:
                b.latitude = lat
            if b.longitude is None:
                b.longitude = lng
        for s in services[:3]:
            off = db.scalar(select(BranchServiceOffering).where(
                BranchServiceOffering.branch_id == b.id,
                BranchServiceOffering.service_id == s.id))
            if off is None:
                db.add(BranchServiceOffering(branch_id=b.id, service_id=s.id, is_active=True))
    db.flush()


# ---------------------------------------------------------------- فرایندها
PROCESS_SEEDS = [
    # (کد، عنوان، شرح، فایل XML)
    ("RS-PR-00", "گردش کلی خدمات مشاوره",
     "نقشه کلان: از تماس/درخواست تا پذیرش تلفنی، تشکیل پرونده، ارزیابی تخصصی، جلسات درمانی و بستن پرونده — و انشعاب فرایند مورد حاد در صورت شناسایی خطر.",
     "process-00-overall.bpmn"),
    ("RS-PS-01-01", "پذیرش اولیه مراجعان تلفنی",
     "ثبت اطلاعات فردی مراجع تلفنی، ارزیابی اولیه موضوع مراجعه، تشخیص مورد حاد و تعیین مسیر (پذیرش حضوری، اطلاع‌رسانی یا تماس مجدد) با بازبینی نظارت حرفه‌ای.",
     "process-01-telephone-intake.bpmn"),
    ("RS-PS-04-01", "پذیرش و تشکیل پرونده",
     "تشکیل پرونده، رضایت‌نامه آگاهانه، تخصیص مشاور، ارزیابی تخصصی و MSE، چرخه نهایی‌سازی/تأیید مسئول فنی (با برگشت برای اصلاح)، طرح درمان و جلسات تا بستن پرونده.",
     "process-04-case-intake.bpmn"),
    ("RS-PS-08-01", "ارزیابی و مدیریت مورد حاد / پر خطر",
     "ثبت فرم مورد حاد و تعیین سطح فوریت؛ مسیر سطح ۱ (پایش دوره‌ای)، سطح ۲ (ارجاع برنامه‌ریزی‌شده) و سطح ۳ (اقدام فوری و ارجاع اورژانسی)؛ ثبت نتیجه پذیرش مقصد، پیگیری و مختومه‌سازی.",
     "process-08-acute-case.bpmn"),
]
PROCESS_SEED_DIR = Path("process_seed")


def seed_processes(db, ref, reqs, cases) -> None:
    """تعریف ۴ فرایند مستندشده (نسخه ۱ منتشرشده) + نمونه‌های اجرای دمو."""
    from xml.etree import ElementTree as ET

    ref.setdefault("process_defs", {})
    for code, title, desc, fname in PROCESS_SEEDS:
        d = db.scalar(select(ProcessDefinition).where(ProcessDefinition.code == code))
        if d is None:
            d = ProcessDefinition(code=code, title=title, description=desc,
                                  created_by=ref["admin"].id)
            db.add(d)
            db.flush()
        else:
            d.title, d.description = title, desc
        ref["process_defs"][code] = d
        has_v = db.scalar(select(ProcessVersion).where(ProcessVersion.definition_id == d.id))
        if has_v is None and (PROCESS_SEED_DIR / fname).is_file():
            xml = (PROCESS_SEED_DIR / fname).read_text(encoding="utf-8")
            try:
                ET.fromstring(xml)
            except ET.ParseError:
                continue
            db.add(ProcessVersion(definition_id=d.id, version_number=1, bpmn_xml=xml,
                                  changelog="نسخه اولیه مستندسازی‌شده (BPMN 2.0)",
                                  status="published"))
    db.flush()

    # نمونه‌های اجرای دمو برای مانیتورینگ وضعیت درخواست در فرایند
    tel = ref["process_defs"].get("RS-PS-01-01")
    intake = ref["process_defs"].get("RS-PS-04-01")

    def instance_for(defn, version, subject, label, meta, events):
        if defn is None or version is None:
            return
        exists = db.scalar(select(ProcessInstance).where(
            ProcessInstance.definition_id == defn.id,
            ProcessInstance.subject_type == meta["subject_type"],
            ProcessInstance.subject_id == str(subject.id)))
        if exists is not None:
            return
        inst = ProcessInstance(
            definition_id=defn.id, version_id=version.id,
            subject_type=meta["subject_type"], subject_id=str(subject.id),
            subject_label=label, subject_meta={k: v for k, v in meta.items() if k != "subject_type"},
            status=meta["status"], started_by=ref["reception"].id,
        )
        db.add(inst)
        db.flush()
        for name, etype, status in events:
            db.add(ProcessInstanceEvent(instance_id=inst.id, element_name=name,
                                        element_type=etype, status=status,
                                        actor_id=ref["reception"].id))
        if meta["status"] == "completed":
            inst.finished_at = NOW

    v_tel = db.scalar(select(ProcessVersion).where(
        ProcessVersion.definition_id == tel.id, ProcessVersion.status == "published")) if tel else None
    v_int = db.scalar(select(ProcessVersion).where(
        ProcessVersion.definition_id == intake.id, ProcessVersion.status == "published")) if intake else None

    # نمونه‌های اجرای دمو — فقط برای فرایندی که هنوز هیچ نمونه‌ای ندارد
    # (اجرای مجدد seed روی دیتابیس پرشده، نمونه تکراری نمی‌سازد)
    has_inst = set(db.scalars(select(ProcessInstance.definition_id).distinct()).all())

    demo_events_done = [
        ("ثبت تماس ورودی", "task", "done"),
        ("ثبت اطلاعات فردی مراجع", "task", "done"),
        ("ارزیابی اولیه موضوع مراجعه", "task", "done"),
        ("تشخیص مورد حاد", "gateway", "done"),
        ("تعیین مسیر: پذیرش حضوری", "task", "done"),
    ]
    demo_events_running = [
        ("ثبت تماس ورودی", "task", "done"),
        ("ثبت اطلاعات فردی مراجع", "task", "done"),
        ("ارزیابی اولیه موضوع مراجعه", "task", "active"),
    ]
    if tel is not None and tel.id not in has_inst:
        for idx, (req, applicant) in enumerate(reqs[:3]):
            if req is None:
                continue
            label = req.full_name or (applicant.full_name if applicant else "مراجع تلفنی")
            inst_status = "completed" if idx == 2 else "running"
            meta = {
                "subject_type": "consultation_request",
                "topic": req.topic, "mobile": req.mobile, "status": inst_status,
            }
            events = demo_events_done if idx == 2 else demo_events_running
            instance_for(tel, v_tel, req, label, meta, events)

    case_ref = cases[0] if cases else None
    if case_ref is not None and intake is not None and intake.id not in has_inst:
        instance_for(intake, v_int, case_ref, case_ref.case_number, {
            "subject_type": "case", "status": "running",
        }, [
            ("تشکیل پرونده", "task", "done"),
            ("ثبت رضایت‌نامه آگاهانه", "task", "done"),
            ("تخصیص مشاور", "task", "done"),
            ("ارزیابی تخصصی", "task", "active"),
        ])
    db.flush()


def seed_applicants(db, ref) -> list[Applicant]:
    """۱۰۰ متقاضی با مشخصات متنوع + ۲۰ حساب پورتال."""
    used_mobile: set = set()
    # کلیدهای یکتای موجود در دیتابیس (مثلاً از seed قدیمی یا ثبت پنل) در نمونه‌گیری لحاظ می‌شود
    used_nid: set = set(db.scalars(select(Applicant.national_id).where(Applicant.national_id.is_not(None))))
    used_ext: set = set(db.scalars(select(Applicant.external_id).where(Applicant.external_id.is_not(None))))
    used_emp: set = set(db.scalars(select(Applicant.employee_code).where(Applicant.employee_code.is_not(None))))
    applicants: list[Applicant] = []
    for i in range(100):
        female = i % 2 == 0
        fn = rng.choice(FEMALE if female else MALE)
        ln = rng.choice(LAST)
        prov, city = PROVINCE_CITY[i % len(PROVINCE_CITY)]
        status = "active"
        if i in (23, 47, 71, 95):
            status = "inactive"
        elif i in (36, 62, 88):
            status = "archived"
        source = "excel" if i % 4 == 3 else "manual"
        org = ref["orgs"][i % 3] if i % 10 < 6 else None
        contract = ref["contracts"][i % 3] if org else None
        ext = f"EXT-{2001+i}"
        if ext in used_ext:
            ext = unique_numbered(f"EXT-{3001+i}", used_ext)
        else:
            used_ext.add(ext)
        emp = f"E-{1000+i}" if source == "excel" or org else None
        if emp is not None:
            emp = unique_numbered(emp, used_emp)
        a = Applicant(
            external_id=ext,
            employee_code=emp,
            national_id=gen_national_id(used_nid),
            first_name=fn, last_name=ln,
            birth_date=date(1980 + (i % 26), 1 + (i % 12), 1 + (i % 27)),
            gender="female" if female else "male",
            marital_status=rng.choice(["single", "married", "married", "divorced"]),
            education=rng.choice(EDUCATIONS),
            occupation=rng.choice(OCCUPATIONS),
            mobile=gen_mobile(used_mobile),
            unit_id=ref["units"][i % 4].id if org else None,
            organization_id=org.id if org else None,
            service_location_id=ref["locations"][i % 3].id,
            province_code=prov, city=city,
            referral_source=rng.choice(REF_SOURCES),
            referral_description="ثبت‌شده از مسیر پذیرش تلفنی و فرم وب‌سایت",
            status=status, record_source=source,
            created_at=dt_days_ago(60 - int(i * 0.6), 9 + (i % 8)),
        )
        db.add(a)
        applicants.append(a)
    db.flush()

    # ۲۰ حساب پورتال برای ۲۰ متقاضی فعال اول
    applicant_users: list[User] = []
    for i, a in enumerate(applicants[:20]):
        u = make_user(db, f"user{2001+i}", f"{a.first_name} {a.last_name}", "APPLICANT",
                      email=f"user{2001+i}@mail.demo", mobile=a.mobile)
        db.flush()
        a.user_id = u.id
        applicant_users.append(u)
    ref["applicant_users"] = applicant_users

    # دامنه دسترسی نمونه برای دو مشاور
    db.add(UserScope(user_id=ref["counselors"][0].user_id, service_location_id=ref["locations"][0].id))
    db.add(UserScope(user_id=ref["manager"].id, unit_id=ref["units"][0].id))
    db.flush()
    return applicants


def seed_requests(db, ref, applicants) -> list[tuple[ConsultationRequest, Applicant | None]]:
    """۵۸ درخواست مشاوره سایت + ۶ پرسشنامه پذیرش."""
    reqs: list[tuple[ConsultationRequest, Applicant | None]] = []
    plans = ([("new", 0, 5)] * 12 + [("in_review", 3, 12)] * 9 +
             [("converted", 7, 55)] * 27 + [("archived", 20, 58)] * 10)
    rng.shuffle(plans)
    linked_cases_hint: list[Applicant] = []
    for i, (status, lo, hi) in enumerate(plans):
        female = i % 2 == 1
        name = f"{rng.choice(FEMALE if female else MALE)} {rng.choice(LAST)}"
        topic = REQUEST_TOPICS[i % len(REQUEST_TOPICS)]
        created = dt_days_ago(lo + rng.randint(0, max(0, hi - lo)), 8 + (i % 10), rng.choice([0, 15, 30, 45]))
        r = ConsultationRequest(
            full_name=name, mobile=gen_mobile(set()), topic=topic,
            preferred_date=TODAY + timedelta(days=rng.randint(0, 10)),
            preferred_slot=rng.choice(["morning", "afternoon", "evening"]),
            message=rng.choice(REQUEST_MSGS), status=status,
            handled_by=ref["reception"].id if status != "new" else None,
            handled_at=created + timedelta(hours=rng.randint(2, 40)) if status != "new" else None,
            reception_note="تماس اولیه برقرار شد؛ ارزیابی اولیه انجام گردید." if status != "new" else None,
            contact_attempts=0 if status == "new" else rng.randint(1, 3),
            city=PROVINCE_CITY[i % len(PROVINCE_CITY)][1],
            referral_source=rng.choice(REF_SOURCES),
            created_at=created,
        )
        if status == "converted":
            a = applicants[(i * 2) % 90]
            r.applicant_id = a.id
            linked_cases_hint.append(a)
        db.add(r)
        reqs.append((r, r.applicant_id))
    db.flush()

    # ۶ پرسشنامه پذیرش روی درخواست‌های در حال بررسی/تبدیل‌شده
    intake_targets = [r for r, _ in reqs if r.status in ("in_review", "converted")][:6]
    for j, r in enumerate(intake_targets):
        db.add(IntakeQuestionnaire(
            consultation_request_id=r.id, status="final" if j < 5 else "draft",
            filled_by=ref["reception"].id if j < 5 else None,
            data={"main_complaint": r.topic, "duration_months": rng.randint(1, 24),
                  "previous_treatment": rng.choice(["نداشته‌ام", "دارودرمانی قبلی", "روان‌درمانی قبلی"]),
                  "current_medication": rng.choice(["ندارم", "اسرترالین", "فلوکستین"]),
                  "sleep_quality": rng.choice(["ضعیف", "متوسط", "خوب"]),
                  "suicidal_ideation": "خیر", "family_history": rng.choice(["خیر", "بله - درجه یک"])}))
    db.flush()
    return reqs


def seed_cases(db, ref, applicants, reqs):
    """۴۲ پرونده + تخصیص مشاور + رضایت‌ها؛ ۲۷ درخواست تبدیل‌شده به پرونده متصل می‌شود."""
    used_case_no: set = set(db.scalars(select(Case.case_number)))
    converted_requests = [r for r, _ in reqs if r.status == "converted"]
    status_plan = (["new"] * 3 + ["awaiting_assignment"] * 5 + ["active"] * 18 +
                   ["suspended"] * 4 + ["closed"] * 9 + ["archived"] * 3)
    rng.shuffle(status_plan)
    cases: list[Case] = []
    pending_pairs: list[tuple] = []
    for i, st in enumerate(status_plan):
        if i < len(converted_requests) and st not in ("new", "awaiting_assignment"):
            a = applicants[(i * 2) % 90]
            req = converted_requests[i]
        else:
            a = applicants[(i * 2 + 1) % 90]
            req = None
        assigned = st in ("active", "suspended", "closed", "archived")
        created = dt_days_ago(rng.randint(2, 58), 10 + (i % 7))
        accept = (created - timedelta(days=1)).date()
        c = Case(
            case_number=unique_numbered(f"RS-1404-{i + 1:04d}", used_case_no), applicant_id=a.id,
            acceptance_date=accept,
            service_location_id=ref["locations"][i % 3].id,
            service_type=ref["services"][i % len(ref["services"])].title,
            primary_counselor_id=ref["counselors"][i % len(ref["counselors"])].id if assigned else None,
            priority="high" if i % 9 == 0 else ("low" if i % 13 == 0 else "normal"),
            status=st,
            consent_status="granted" if assigned else ("none" if st == "new" else "granted"),
            close_reason="اتمام دوره درمان با رضایت مراجع" if st == "closed" else None,
            close_date=(TODAY - timedelta(days=rng.randint(1, 15))) if st == "closed" else None,
            created_by=ref["reception"].id,
            created_at=created,
        )
        db.add(c)
        cases.append(c)
        if req is not None:
            pending_pairs.append((req, c))
    db.flush()
    for req, c in pending_pairs:
        req.case_id = c.id

    # تخصیص‌ها (اصلی برای همه دارای مشاور + ۳ ثانویه)
    for i, c in enumerate(cases):
        if c.primary_counselor_id is None:
            continue
        start = datetime.combine(c.acceptance_date, datetime.min.time(), TZ) + timedelta(hours=10)
        end = None
        end_reason = None
        if c.status in ("closed", "archived"):
            end = start + timedelta(days=rng.randint(30, 70))
            end_reason = "اتمام دوره درمان"
        db.add(CaseAssignment(case_id=c.id, counselor_id=c.primary_counselor_id, start_at=start,
                              end_at=end, reason="تخصیص بر اساس تخصص و ظرفیت",
                              end_reason=end_reason, role_in_case="primary",
                              assigned_by=ref["manager"].id))
        if i % 12 == 3:
            db.add(CaseAssignment(case_id=c.id, counselor_id=ref["counselors"][(i + 4) % 8].id,
                                  start_at=start + timedelta(days=3), role_in_case="secondary",
                                  reason="مشاوره هم‌زمان تخصصی", assigned_by=ref["manager"].id))
    # رضایت‌ها (نسخه یکتا per case: درمان=1، آزمون=2، ابطال=3)
    for i, c in enumerate(cases):
        if c.status == "new":
            continue
        cdate = c.acceptance_date
        v = 1
        db.add(Consent(case_id=c.id, version=v, status="granted", kind="treatment",
                       note="رضایت آگاهانه درمان ثبت شد", consent_date=cdate,
                       recorded_by=ref["reception"].id))
        if i % 2 == 0:
            v += 1
            db.add(Consent(case_id=c.id, version=v, status="granted", kind="psych_test",
                           note="رضایت اجرای آزمون‌های روان‌سنجی", consent_date=cdate,
                           recorded_by=ref["reception"].id))
        if c.id == cases[8].id:
            v += 1
            db.add(Consent(case_id=c.id, version=v, status="revoked", kind="data_share",
                           note="ابطال رضایت اشتراک داده با سازمان", consent_date=cdate,
                           recorded_by=ref["reception"].id, revoked_at=dt_days_ago(5, 12),
                           revoked_by=ref["admin"].id, revoke_reason="درخواست کتبی مراجع"))
    db.flush()
    return cases


def seed_appointments(db, ref, cases):
    """تقویم ۲۳ روزه: نوبت‌های انجام‌شده/لغو/عدم حضور در گذشته و برنامه‌ریزی‌شده آینده."""
    services = ref["services"]
    counselors = ref["counselors"]
    open_tariff = {}
    for tv in db.scalars(select(TariffVersion).where(TariffVersion.valid_to.is_(None))):
        open_tariff.setdefault(tv.service_id, tv)

    used: set[tuple[uuid_mod.UUID, datetime]] = set()
    appts: list[Appointment] = []
    counters = {"done": 0, "cancelled": 0, "no_show": 0, "scheduled": 0}

    def add_appt(day: date, hour: int, case: Case, status: str) -> None:
        for attempt in range(6):
            csl = counselors[(hour + attempt + day.day) % len(counselors)]
            start = datetime.combine(day, datetime.min.time(), TZ) + timedelta(hours=hour)
            if (csl.id, start) in used:
                hour = hour + 1 if hour < 16 else 9
                start = datetime.combine(day, datetime.min.time(), TZ) + timedelta(hours=hour)
                continue
            used.add((csl.id, start))
            break
        svc = services[(day.day + hour) % len(services)]
        tv = open_tariff[svc.id]
        counters[status] += 1
        note = None
        if status == "cancelled":
            note = "لغو توسط مراجع (حداقل ۲۴ ساعت قبل)"
        elif status == "no_show":
            note = "عدم حضور بدون اطلاع قبلی"
        appts.append(Appointment(
            case_id=case.id, counselor_id=csl.id, scheduled_at=start,
            duration_minutes=svc.duration_minutes,
            location="آنلاین (ویدئوکنفرانس)" if svc.session_type == "online" else
            (case.service_location_id and ref["locations"][(day.day + hour) % 3].title) or "کلینیک مرکزی - ولیعصر",
            status=status, note=note, service_id=svc.id, tariff_version_id=tv.id,
            price_amount=tv.amount, price_currency="IRR",
            created_by=ref["reception"].id,
            created_at=datetime.combine(day - timedelta(days=3), datetime.min.time(), TZ) + timedelta(hours=11),
        ))

    # گذشته: ۲۲ انجام‌شده + ۸ لغو + ۴ عدم حضور
    past_plan = (["done"] * 22 + ["cancelled"] * 8 + ["no_show"] * 4)
    rng.shuffle(past_plan)
    past_days = [workday(-d) for d in range(14, 0, -1)]
    ci = 0
    for i, st in enumerate(past_plan):
        day = past_days[i % len(past_days)]
        hour = 9 + (i * 3) % 8
        case = cases[ci % len(cases)]
        ci += 1
        if case.status in ("new", "awaiting_assignment"):
            case = cases[(ci + 8) % len(cases)]
        add_appt(day, hour, case, st)

    # آینده: ۳۴ برنامه‌ریزی‌شده
    future_days = [workday(d) for d in range(1, 11)]
    fi = 0
    for i in range(34):
        day = future_days[i % len(future_days)]
        hour = 9 + (i * 2 + 1) % 8
        case = cases[(i * 2 + 5) % len(cases)]
        if case.status in ("new", "awaiting_assignment"):
            case = cases[(i + 12) % len(cases)]
        add_appt(day, hour, case, "scheduled")
        fi += 1
    db.add_all(appts)
    db.flush()

    # نگهداشت موقت اسلات (B09): ۲ فعال + ۱ آزادشده
    tomorrow = workday(1)
    for j, hour in enumerate((10, 14)):
        start = datetime.combine(tomorrow, datetime.min.time(), TZ) + timedelta(hours=hour)
        db.add(SlotClaim(counselor_id=counselors[j].id, start_at=start, status="active",
                         hold_token_hash=hashlib.sha256(uuid_mod.uuid4().bytes).hexdigest(),
                         mobile=gen_mobile(set()), expires_at=NOW + timedelta(minutes=20)))
    start = datetime.combine(workday(2), datetime.min.time(), TZ) + timedelta(hours=11)
    db.add(SlotClaim(counselor_id=counselors[3].id, start_at=start, status="released",
                     hold_token_hash=hashlib.sha256(uuid_mod.uuid4().bytes).hexdigest(),
                     expires_at=NOW - timedelta(hours=2), released_at=NOW - timedelta(hours=2)))
    db.flush()
    return appts


def seed_sessions(db, ref, appts):
    """جلسات واقعاً انجام‌شده + یادداشت نسخه‌دار + نظرسنجی رضایت."""
    done_appts = [a for a in appts if a.status == "done"]
    cu = {c.id: c.user_id for c in ref["counselors"]}
    per_case: dict[uuid_mod.UUID, int] = {}
    sessions: list[Session] = []
    for a in sorted(done_appts, key=lambda x: x.scheduled_at):
        n = per_case.get(a.case_id, 0) + 1
        per_case[a.case_id] = n
        s = Session(case_id=a.case_id, appointment_id=a.id, counselor_id=a.counselor_id,
                    occurred_at=a.scheduled_at, session_number=n, created_by=cu.get(a.counselor_id))
        sessions.append(s)
        db.add(s)
    db.flush()
    for i, s in enumerate(sessions):
        subj, obj, ass, plan = NOTE_SOAP[i % len(NOTE_SOAP)]
        db.add(SessionNoteRevision(session_id=s.id, version=1,
                                   content={"soap": {"subjective": subj, "objective": obj,
                                                     "assessment": ass, "plan": plan}},
                                   status="final" if i % 4 != 3 else "draft",
                                   author_user_id=cu.get(s.counselor_id)))
    # نظرسنجی برای جلسات مراجعان دارای حساب پورتال
    users_by_applicant = {}
    for a in db.scalars(select(Applicant).where(Applicant.user_id.isnot(None))):
        users_by_applicant[a.id] = a.user_id
    surveyed = 0
    for s in sessions:
        if surveyed >= 12:
            break
        case = db.get(Case, s.case_id)
        uid = users_by_applicant.get(case.applicant_id)
        if uid is None:
            continue
        db.add(SessionSurvey(session_id=s.id, respondent_user_id=uid,
                             score=rng.choice([3, 4, 4, 5, 5, 5])))
        surveyed += 1
    db.flush()
    return sessions


def seed_clinical(db, ref, cases):
    """تشخیص، طرح درمان، توصیه، ارجاع."""
    active_like = [c for c in cases if c.status in ("active", "suspended", "closed", "archived")]
    cu = {c.id: c.user_id for c in ref["counselors"]}
    for i, c in enumerate(active_like[:24]):
        title, code, st = DIAGNOSES[i % len(DIAGNOSES)]
        db.add(Diagnosis(case_id=c.id, status=st, title=title, code=code,
                         comorbid="اختلال خواب" if i % 4 == 0 else None,
                         note="بر اساس مصاحبه بالینی و ارزیابی‌های استاندارد",
                         recorded_by=cu.get(c.primary_counselor_id)))
    for i, c in enumerate(active_like[:22]):
        db.add(TreatmentPlan(case_id=c.id, version_no=1, status="active" if c.status != "closed" else "archived",
                             goals="کاهش شدت نشانه‌های اضطراب/افسردگی و بهبود عملکرد روزمره؛ تقویت مهارت‌های مقابله‌ای",
                             approach=rng.choice(["cbt", "act", "dbt", "schematherapy"]),
                             approach_note="رویکرد انتخابی بر اساس ارزیابی اولیه و ترجیح مراجع",
                             protocol_name=rng.choice(["پروتکل CBT اضطراب ۱۲ جلسه‌ای", "پروتکل ACT ۸ جلسه‌ای",
                                                       "پروتکل DBT مهارت‌ها", "درمان متمرکز بر شema"]),
                             sessions_count=rng.choice([8, 10, 12, 16]), session_interval="هفتگی",
                             interventions="بازسازی شناختی، مواجهه تدریجی، تمرین تن‌آرامی، تکالیف رفتاری",
                             review_date=TODAY + timedelta(days=rng.randint(5, 40)),
                             remarks="بازنگری طرح پس از جلسه چهارم", recorded_by=cu.get(c.primary_counselor_id)))
    for i, c in enumerate(active_like[:18]):
        pub = i % 4 != 3
        db.add(Recommendation(case_id=c.id,
                              content="ادامه جلسات هفتگی؛ انجام تمرین‌های خانه؛ مراجعه فوری در صورت تشدید نشانه‌ها. "
                                      + rng.choice(["تمرین تنفس دیافراگمی روزی دو بار.", "ثبت روزانه خلق و خواب.",
                                                    "پیاده‌روی روزانه ۳۰ دقیقه."]),
                              is_published=pub, created_by=cu.get(c.primary_counselor_id),
                              published_by=ref["reception"].id if pub else None,
                              published_at=dt_days_ago(rng.randint(1, 10), 13) if pub else None))
    # ارجاع‌ها
    ref_plan = [("internal", "initiated", "نیاز به ارزیابی هم‌زمان روان‌پزشکی"), ("external", "accepted", "ارجاع برای ارزیابی نورولوژیک"),
                ("external", "completed", "انجام ارزیابی و بازگشت با گزارش"), ("internal", "accepted", "انتقال به مشاور نوجوان"),
                ("cross_center", "initiated", "دریافت خدمت در شعبه اصفهان پس از انتقال محل سکونت"),
                ("external", "completed", "ارجاع روان‌پزشکی و شروع دارودرمانی")]
    for i, (direction, status, reason) in enumerate(ref_plan):
        c = active_like[i]
        db.add(Referral(case_id=c.id, direction=direction, status=status,
                        to_counselor_id=ref["counselors"][(i + 2) % 8].id if direction == "internal" else None,
                        to_center_name=None if direction == "internal" else
                        rng.choice(["درمانگاه مهر", "بیمارستان روانی روز", "کلینیک اعصاب و روان آینده"]),
                        reason=reason, notes="هماهنگی تلفنی انجام شد",
                        outcome="گزارش ارزیابی دریافت شد" if status == "completed" else None,
                        referral_date=TODAY - timedelta(days=rng.randint(3, 30)),
                        outcome_date=TODAY - timedelta(days=rng.randint(0, 2)) if status == "completed" else None,
                        requested_by=cu.get(c.primary_counselor_id), row_version=1))
    db.flush()


def seed_forms(db, ref, cases):
    """نسخه‌های فرم + ۳۰ ارزیابی در چرخه پیش‌نویس → نهایی → بازبینی → تأیید/بازگشت."""
    fv: dict[str, FormVersion] = {}
    for code in ("RS-PS-01-01", "RS-PS-04-01", "RS-PS-08-01"):
        d = get_form_definition(code)
        v = FormVersion(form_code=code, version=d["version"], definition=d, is_published=True)
        db.add(v)
        fv[code] = v
    db.flush()

    eligible = [c for c in cases if c.status not in ("new",)]
    assessments: list[Assessment] = []
    ai = 0
    plan = (["RS-PS-04-01"] * 23 + ["RS-PS-01-01"] * 4 + ["RS-PS-08-01"] * 3)
    status_cycle = (["draft"] * 6 + ["finalized"] * 11 + ["pending_review"] * 6 +
                    ["approved"] * 5 + ["returned"] * 2)
    for i, code in enumerate(plan):
        c = eligible[ai % len(eligible)]
        ai += 1
        st = status_cycle[i % len(status_cycle)]
        applicant = db.get(Applicant, c.applicant_id)
        answers = sample_answers(fv[code].definition, applicant)
        cu = {c.id: c.user_id for c in ref["counselors"]}
        a = Assessment(case_id=c.id, form_version_id=fv[code].id, answers=answers, status=st,
                       version_no=1, row_version=1,
                       author_user_id=cu.get(c.primary_counselor_id) or ref["reception"].id,
                       finalized_by=cu.get(c.primary_counselor_id) if st != "draft" else None,
                       finalized_at=dt_days_ago(rng.randint(1, 20), 15) if st != "draft" else None)
        db.add(a)
        assessments.append(a)
    db.flush()
    for a in assessments:
        if a.status == "approved":
            db.add(ReviewAction(assessment_id=a.id, reviewer_user_id=ref["supervisor"].id,
                                decision="approved", comment="فرم کامل و منطبق با پروتکل است؛ تأیید شد."))
        elif a.status == "returned":
            db.add(ReviewAction(assessment_id=a.id, reviewer_user_id=ref["supervisor"].id,
                                decision="returned", comment="بخش ارزیابی خطر تکمیل نشده؛ لطفاً تکمیل و ارسال مجدد شود."))
    db.flush()
    return assessments


def seed_finance(db, ref, appts):
    """سفارش/پرداخت/فاکتور/تخفیف/کیف پول/استرداد + سند حسابداری."""
    reception = ref["reception"]
    applicants_by_id = {a.id: a for a in db.scalars(select(Applicant))}
    org_contract = {o.id: c for o, c in zip(ref["orgs"], ref["contracts"])}
    used_ord: set = set(db.scalars(select(Order.order_number)))
    used_inv: set = set(db.scalars(select(Invoice.invoice_number)))
    orders: list[Order] = []
    num = 1

    def make_order(a: Appointment, status: str) -> Order:
        nonlocal num
        case = db.get(Case, a.case_id)
        applicant = applicants_by_id[case.applicant_id]
        amount = int(a.price_amount or 0)
        org = applicant.organization_id and org_contract.get(applicant.organization_id)
        cov = float(org.coverage_percent) if org and org.status == "active" else None
        org_share = round(amount * cov / 100) if cov else None
        payable = amount - org_share if org_share else amount
        owner = applicant.user_id or reception.id
        o = Order(order_number=unique_numbered(f"ORD-1404-{num:05d}", used_ord), owner_user_id=owner, case_id=case.id,
                  appointment_id=a.id, service_id=a.service_id, tariff_version_id=a.tariff_version_id,
                  title=f"نوبت {db.get(Service, a.service_id).title} - {case.case_number}", amount=amount, currency="IRR",
                  payable_amount=payable, status=status, kind="service", refunded_amount=0,
                  organization_id=applicant.organization_id,
                  contract_id=org.id if org else None,
                  coverage_percent=cov, org_share_amount=org_share,
                  applicant_share_amount=payable if org_share else None,
                  created_by=reception.id,
                  created_at=a.scheduled_at - timedelta(days=2))
        num += 1
        db.add(o)
        return o

    paid_orders: list[Order] = []
    for a in appts:
        if a.status == "done":
            o = make_order(a, "paid")
            paid_orders.append(o)
        elif a.status == "scheduled":
            if num % 9 == 0:
                st = "failed"
            elif num % 4 == 0:
                st = "pending"
            else:
                st = "paid"
            o = make_order(a, st)
            if st == "paid":
                paid_orders.append(o)
        elif a.status == "no_show":
            o = make_order(a, "paid")
            o.refunded_amount = o.payable_amount
            paid_orders.append(o)
        elif a.status == "cancelled":
            make_order(a, "cancelled")
    db.flush()

    # پرداخت‌ها
    for i, o in enumerate(paid_orders):
        db.add(Payment(order_id=o.id, gateway="zarinpal", amount=int(o.amount), currency="IRR",
                       status="success", authority=uuid_mod.uuid4().hex,
                       gateway_ref=f"RG-{rng.randint(100000, 999999)}",
                       card_mask=f"6037-99**-****-{rng.randint(1000, 9999)}",
                       paid_at=o.created_at + timedelta(minutes=9),
                       verify_payload={"ref_id": rng.randint(100000, 999999)}))
    pend_o = [o for o in orders_on(db) if o.status == "pending"]
    if pend_o:
        db.add(Payment(order_id=pend_o[0].id, gateway="zarinpal", amount=int(pend_o[0].amount),
                       status="initiated", authority=uuid_mod.uuid4().hex))
    fail = [o for o in orders_on(db) if o.status == "failed"]
    if fail:
        db.add(Payment(order_id=fail[0].id, gateway="zarinpal", amount=int(fail[0].amount),
                       status="failed", authority=uuid_mod.uuid4().hex,
                       fail_reason="انصراف کاربر در درگاه"))

    # فاکتور برای ۳۰ سفارش پرداخت‌شده
    for i, o in enumerate(paid_orders[:30]):
        inv = Invoice(invoice_number=unique_numbered(f"INV-1404-{i + 1:05d}", used_inv), order_id=o.id, total_amount=int(o.payable_amount),
                      currency="IRR", buyer_name="بایر نمونه", status="issued",
                      issued_at=o.created_at + timedelta(days=1))
        db.add(inv)
        db.flush()
        svc_title = db.get(Service, o.service_id).title if o.service_id else "خدمت مشاوره"
        db.add(InvoiceItem(invoice_id=inv.id, description=f"جلسه {svc_title}", quantity=1,
                           unit_amount=int(o.payable_amount), line_total=int(o.payable_amount)))

    # تخفیف‌ها + بازخرید
    d1 = get_or_create(db, Discount, defaults={"kind": "amount", "value": 200000, "currency": "IRR",
                                               "is_active": True, "min_order_amount": 500000,
                                               "note": "هدیه خوش‌آمدگویی"}, code="WELCOME")
    d2 = get_or_create(db, Discount, defaults={"kind": "percent", "value": 15, "currency": "IRR",
                                               "is_active": True,
                                               "expires_at": datetime.combine(TODAY + timedelta(days=30), datetime.min.time(), TZ),
                                               "note": "تخفیف نوروزی"}, code="NOWRUZ15")
    for i, o in enumerate(paid_orders[:3]):
        disc = d1 if i < 2 else d2
        applied = min(200000, int(o.amount)) if disc.kind == "amount" else round(int(o.amount) * 0.15)
        o.discount_amount = applied
        o.discount_id = disc.id
        o.payable_amount = int(o.amount) - applied
        db.add(DiscountRedemption(discount_id=disc.id, order_id=o.id, user_id=o.owner_user_id,
                                  amount_applied=applied))

    # کیف پول ۸ کاربر پورتال
    for i, u in enumerate(ref["applicant_users"][:8]):
        w = Wallet(user_id=u.id, balance=0, currency="IRR")
        db.add(w)
        db.flush()
        bal = 0
        db.add(WalletEntry(wallet_id=w.id, direction="credit", reason="topup", amount=2000000,
                           balance_after=2000000, currency="IRR", note="شارژ کیف پول - درگاه بانکی",
                           created_by=u.id))
        bal = 2000000
        if i % 2 == 0:
            pay = 1200000
            bal -= pay
            db.add(WalletEntry(wallet_id=w.id, direction="debit", reason="payment", amount=pay,
                               balance_after=bal, currency="IRR", note="پرداخت نوبت مشاوره"))
        w.balance = bal

    # استرداد: ۲ اجراشده + ۱ در انتظار
    refunded = [o for o in paid_orders if o.refunded_amount and o.refunded_amount > 0][:2]
    for i, o in enumerate(refunded):
        rr = RefundRequest(order_id=o.id, requested_by=o.owner_user_id, amount=int(o.refunded_amount),
                           currency="IRR", reason="لغو نوبت پیش از جلسه",
                           status="executed", decided_by=ref["manager"].id,
                           decided_at=dt_days_ago(3, 14), decision_note="تأیید مطابق ضوابط لغو")
        db.add(rr)
        db.flush()
        db.add(Refund(refund_request_id=rr.id, order_id=o.id, amount=int(o.refunded_amount),
                      currency="IRR", channel="gateway", gateway="zarinpal",
                      gateway_ref=f"RF-{rng.randint(100000, 999999)}",
                      note="بازگشت وجه به کارت", executed_by=ref["manager"].id))
    pend = [o for o in paid_orders if not (o.refunded_amount and o.refunded_amount > 0)][:1]
    if pend:
        db.add(RefundRequest(order_id=pend[0].id, requested_by=pend[0].owner_user_id,
                             amount=int(pend[0].payable_amount or pend[0].amount), currency="IRR",
                             reason="درخواست انتقال جلسه؛ مبلغ در کیف پول واریز شود", status="pending"))

    # حسابداری: سرفصل‌ها + ۶ سند پرداخت
    acc_bank = Account(code="1100", name="بانک - حساب جاری مرکزی", type="asset", is_system=True)
    acc_cash = Account(code="1010", name="صندوق", type="asset", is_system=True)
    acc_recv = Account(code="1200", name="حساب‌های دریافتنی", type="asset", is_system=True)
    acc_rev = Account(code="4100", name="درآمد خدمات مشاوره", type="revenue", is_system=True)
    db.add_all([acc_bank, acc_cash, acc_recv, acc_rev])
    db.flush()
    for i, o in enumerate(paid_orders[:6]):
        je = JournalEntry(entry_no=f"JE-1404-{i + 1:04d}", entry_date=o.created_at.date(),
                          description=f"دریافت پرداخت سفارش {o.order_number}", kind="payment_gateway",
                          source_type="payment", created_by=ref["admin"].id)
        db.add(je)
        db.flush()
        amt = int(o.payable_amount or o.amount)
        db.add(JournalLine(entry_id=je.id, account_id=acc_bank.id, debit=amt, credit=0))
        db.add(JournalLine(entry_id=je.id, account_id=acc_rev.id, debit=0, credit=amt))
    db.flush()
    return orders


def orders_on(db):
    return list(db.scalars(select(Order)))


def seed_psych(db, ref):
    """بارگذاری بانک آزمون + ۲۲ اجرای نمونه با نمره و ریزنمره."""
    import seed_psych_tests as spt
    spt.main()

    users = ref["applicant_users"] + [ref["admin"], ref["reception"]]
    tests = list(db.scalars(select(PsychTest).where(PsychTest.status == "published")))
    n = 0
    for t in tests:
        if n >= 22:
            break
        qs = list(db.scalars(select(PsychQuestion).where(PsychQuestion.test_id == t.id)))
        interps = list(db.scalars(select(PsychInterpretation).where(PsychInterpretation.test_id == t.id)))
        if not qs or not interps:
            continue
        for rep in range(2):
            u = users[(n + rep) % len(users)]
            band = interps[rng.randrange(len(interps))]
            score = rng.randint(int(band.score_min), int(band.score_max))
            answers = [rng.randint(0, max(0, len(q.options) - 1)) for q in qs]
            sub = {}
            for q, ans in zip(qs, answers):
                if q.subscale:
                    sub[q.subscale] = sub.get(q.subscale, 0) + (q.options[ans]["score"] if ans < len(q.options) else 0)
            db.add(PsychAttempt(test_id=t.id, user_id=u.id, score=score,
                                interpretation_label=band.label, interpretation_guidance=band.guidance,
                                answers=answers, subscale_scores=sub or None,
                                created_at=dt_days_ago(rng.randint(0, 30), rng.randint(9, 20))))
            n += 1
    db.flush()


def seed_learning(db, ref):
    """محتوا، دوره، جلسات دوره، ثبت‌نام، آزمون، تلاش، گواهی."""
    admin = ref["admin"]
    topics = ref["topics"]
    c1 = get_or_create(db, Content, defaults={"title": "شناخت‌درمانی چیست و به چه کسانی کمک می‌کند؟",
                 "summary": "معرفی ساده ساختار CBT و حوزه‌های اثربخشی آن",
                 "body": "درمان شناختی-رفتاری یکی از پرشواهدترین رویکردهای روان‌درمانی است که رابطه افکار، احساسات و رفتار را هدف می‌گیرد...",
                 "topic_id": topics[1].id, "status": "published", "author_id": admin.id,
                 "published_at": dt_days_ago(20, 10)}, slug="what-is-cbt")
    c2 = get_or_create(db, Content, defaults={"title": "۱۰ نشانه شایع اضطراب و راهکارهای فوری کاهش آن",
                 "summary": "نشانه‌های جسمانی و روانی اضطراب و تمرین‌های کوتاه خودتنظیمی",
                 "body": "اضطراب پاسخی طبیعی بدن به تهدید است؛ اما زمانی که شدت و مدت آن زیاد شود...",
                 "topic_id": topics[0].id, "status": "published", "author_id": admin.id,
                 "published_at": dt_days_ago(12, 10)}, slug="anxiety-signs")
    c3 = get_or_create(db, Content, defaults={"title": "چهار خطای رایج گفت‌وگوی زوج‌ها",
                 "summary": "الگوهای مخرب ارتباطی و جایگزین‌های سالم",
                 "body": "در گفت‌وگوهای پرتنش، چهار الگوی انتقاد، تحقیر، حالت دفاعی و دیوار سنگی رایج است...",
                 "topic_id": topics[2].id, "status": "published", "author_id": ref["counselors"][2].user_id,
                 "published_at": dt_days_ago(6, 10)}, slug="couple-communication")
    c4 = get_or_create(db, Content, defaults={"title": "قواعد طلایی فرزندپروری در سن مدرسه",
                 "summary": "پیامدهای منطقی و تقویت مثبت در عمل",
                 "body": "فرزندپروری مؤثر بر سه ستون قاعده‌گذاری شفاف، پیامد منطقی و رابطه گرم استوار است...",
                 "topic_id": topics[3].id, "status": "draft", "author_id": ref["counselors"][3].user_id}, slug="parenting-rules")

    course1 = get_or_create(db, Course, defaults={"title": "دوره مقدماتی مهارت‌های CBT برای زندگی روزمره",
                     "summary": "۸ جلسه کاربردی برای مدیریت افکار و هیجان‌ها",
                     "description": "این دوره شامل ۸ جلسه ویدئویی و تمرین‌های هفتگی است.",
                     "topic_id": topics[0].id, "status": "published", "price_amount": 3500000,
                     "capacity": 30, "starts_at": NOW + timedelta(days=7), "created_by": admin.id}, slug="cbt-essentials")
    course2 = get_or_create(db, Course, defaults={"title": "کارگاه مدیریت استرس محیط کار",
                     "summary": "۴ جلسه مهارت‌های مقابله با فرسودگی شغلی",
                     "description": "کارگاه آنلاین با رویکرد ACT.",
                     "topic_id": topics[4].id, "status": "published", "price_amount": 0,
                     "capacity": 50, "starts_at": NOW + timedelta(days=3), "created_by": admin.id}, slug="stress-free-work")
    db.flush()
    for i in range(4):
        db.add(CourseSession(course_id=course1.id,
                             title=f"جلسه {i + 1}: " + ("آشنایی و ارزیابی" if i == 0 else "مهارت‌های کاربردی"),
                             session_date=NOW + timedelta(days=7 + i * 7, hours=17),
                             duration_minutes=90, sort_order=i))
        db.add(CourseSession(course_id=course2.id, title=f"جلسه {i + 1}: تمرین حضور ذهنی",
                             session_date=NOW + timedelta(days=3 + i * 5, hours=16),
                             duration_minutes=60, sort_order=i))
    users = ref["applicant_users"]
    for i, u in enumerate(users[:10]):
        db.add(CourseEnrollment(course_id=(course1 if i % 2 == 0 else course2).id, user_id=u.id,
                                status="completed" if i < 2 else "active",
                                activated_at=dt_days_ago(rng.randint(3, 20), 12)))

    exam = get_or_create(db, Exam, defaults={"title": "آزمون آشنایی با مفاهیم پایه CBT",
                "description": "آزمون ۶ سؤالی مفاهیم مقدماتی؛ قبولی با ۶۰ درصد",
                "topic_id": topics[0].id, "status": "published", "duration_minutes": 20,
                "pass_percent": 60, "price_amount": 0, "max_attempts": 2, "created_by": admin.id}, slug="cbt-basics-exam")
    db.flush()
    q_bank = [
        ("در CBT، رابطه اصلی میان چه عناصری بررسی می‌شود؟", ["فکر، هیجان، رفتار", "گذشته و ناخودآگاه", "خواب و تغذیه", "خانواده و مدرسه"], 0),
        ("هدف اصلی بازسازی شناختی چیست؟", ["شناسایی و اصلاح افکار ناکارآمد", "افزایش مصرف دارو", "اجتناب از موقعیت‌ها", "تقویت دفاع‌ها"], 0),
        ("«حالت دفاعی» در گفت‌وگوی زوج‌ها یعنی؟", ["بی‌اعتنایی کامل", "پاسخ توجیهی به‌جای شنیدن", "تمرین تنفس", "ثبت خلق"], 1),
        ("کدام یک تمرین تن‌آرامی است؟", ["مطرح‌سازی پیشرونده عضلانی", "پرخاشگری", "اجتناب", "نشخوار فکری"], 0),
        ("بهترین واکنش به نشانه تشدید اضطراب چیست؟", ["تمرین تنفس و مراجعه به مشاور", "مصرف خودسرانه دارو", "بیدارماندن طولانی", "انزوا"], 0),
        ("ثبت روزانه خلق و خواب به چه هدفی کمک می‌کند؟", ["پایش الگوی نشانه‌ها", "جایگزین درمان", "تشخیص قطعی", "هیچ‌کدام"], 0),
    ]
    for i, (p, opts, ci) in enumerate(q_bank):
        db.add(ExamQuestion(exam_id=exam.id, prompt=p, options=opts, correct_index=ci,
                            points=1, sort_order=i))
    for i in range(6):
        u = users[i % len(users)]
        passed = i < 4
        score = rng.randint(67, 100) if passed else rng.randint(33, 50)
        att = ExamAttempt(exam_id=exam.id, user_id=u.id, status="passed" if passed else "failed",
                          score_percent=score, answers=[rng.randint(0, 3) for _ in q_bank],
                          started_at=dt_days_ago(rng.randint(1, 15), 12),
                          submitted_at=dt_days_ago(rng.randint(0, 14), 12) + timedelta(minutes=18))
        db.add(att)
    db.flush()
    uname = {u.id: u.display_name for u in ref["applicant_users"]}
    used_cert: set = set(db.scalars(select(Certificate.certificate_number)))
    passed_atts = list(db.scalars(select(ExamAttempt).where(ExamAttempt.status == "passed")))[:2]
    for i, att in enumerate(passed_atts):
        if db.scalar(select(Certificate).where(Certificate.attempt_id == att.id)) is not None:
            continue
        db.add(Certificate(certificate_number=unique_numbered(f"CERT-1404-{i + 1:04d}", used_cert), user_id=att.user_id,
                           exam_id=att.exam_id, attempt_id=att.id,
                           title="گواهی قبولی آزمون مفاهیم پایه CBT",
                           holder_name=uname.get(att.user_id), issued_by=admin.id))
    comp = list(db.scalars(select(CourseEnrollment).where(CourseEnrollment.status == "completed")))
    if comp:
        if db.scalar(select(Certificate).where(Certificate.course_id == comp[0].course_id,
                                               Certificate.user_id == comp[0].user_id)) is None:
            db.add(Certificate(certificate_number=unique_numbered("CERT-1404-0003", used_cert), user_id=comp[0].user_id,
                               course_id=comp[0].course_id, title="گواهی تکمیل دوره مهارت‌های CBT",
                               holder_name=uname.get(comp[0].user_id), issued_by=admin.id))
    db.flush()


def seed_support(db, ref):
    """تیکت‌ها، پیام‌ها، شکایت."""
    users = ref["applicant_users"]
    reception = ref["reception"]
    t1 = Ticket(user_id=users[0].id, subject="مشکل در ورود به حساب کاربری", status="closed", priority="normal",
                closed_at=dt_days_ago(4, 15), created_at=dt_days_ago(5, 10))
    t2 = Ticket(user_id=users[1].id, subject="درخواست تغییر وقت جلسه", status="answered", priority="high",
                created_at=dt_days_ago(2, 9))
    t3 = Ticket(user_id=users[2].id, subject="پرسش درباره فاکتور جلسه دوم", status="open", priority="normal",
                created_at=dt_days_ago(1, 11))
    t4 = Ticket(user_id=users[3].id, subject="نمایش نشدن نتیجه آزمون", status="answered", priority="normal",
                created_at=dt_days_ago(3, 16))
    t5 = Ticket(user_id=users[4].id, subject="پیشنهاد: افزودن یادآور پیامکی", status="open", priority="normal",
                created_at=dt_days_ago(1, 17))
    db.add_all([t1, t2, t3, t4, t5])
    db.flush()
    msgs = [
        (t1, users[0], "با رمز درست هم وارد نمی‌شوم و پیغام خطا می‌بینم.", False),
        (t1, reception, "رمز شما بازنشانی شد؛ ایمیل فعال‌سازی را بررسی کنید.", True),
        (t1, users[0], "مشکل حل شد؛ ممنون.", False),
        (t2, users[1], "امکان جابجایی نوبت سه‌شنبه به پنجشنبه هست؟", False),
        (t2, reception, "بله؛ نوبت جدید ثبت شد و نوبت قبلی آزاد گردید.", True),
        (t3, users[2], "فاکتور جلسه دوم هنوز صادر نشده است.", False),
        (t4, users[3], "بعد از تکمیل آزمون، صفحه نتایج خالی می‌ماند.", False),
        (t4, reception, "مشکل گزارش و رفع شد؛ مجدد تلاش کنید.", True),
        (t5, users[4], "یادآور ۲۴ ساعت قبل از جلسه کمک‌کننده است.", False),
    ]
    for t, u, body, staff in msgs:
        db.add(TicketMessage(ticket_id=t.id, sender_user_id=u.id, body=body, is_staff=staff))
    db.add(Complaint(complainant_user_id=users[5].id, subject="تأخیر در تماس پذیرش",
                     body="دو روز است برای هماهنگی جلسه تماسی دریافت نکرده‌ام.", status="in_review",
                     created_at=dt_days_ago(2, 13)))
    db.flush()


def seed_comms(db, ref, cases):
    """اعلان‌ها، ایمیل، پیامک، حسابرسی، ورود اکسل."""
    admin, reception, manager = ref["admin"], ref["reception"], ref["manager"]
    n: list[Notification] = [
        Notification(recipient_user_id=admin.id, category="system", event_code="system.backup.completed",
                     title="پشتیبان‌گیری شبانه کامل شد", severity="info", created_at=dt_days_ago(1, 3)),
        Notification(recipient_user_id=admin.id, category="case", event_code="case.level3.alert",
                     title="۲ مورد ارزیابی سطح ۳ برای بازبینی", severity="warning", entity_type="case",
                     created_at=dt_days_ago(1, 9)),
        Notification(recipient_user_id=reception.id, category="consultation", event_code="consult.new",
                     title="۴ درخواست مشاوره جدید در کارتابل", severity="info", created_at=dt_days_ago(1, 10)),
        Notification(recipient_user_id=reception.id, category="appointment", event_code="appointment.tomorrow",
                     title="۱۲ نوبت برای فردا برنامه‌ریزی شده", severity="info", created_at=dt_days_ago(0, 8)),
        Notification(recipient_user_id=manager.id, category="billing", event_code="payment.summary",
                     title="گزارش روزانه درآمد آماده است", severity="info", read_at=dt_days_ago(0, 9),
                     created_at=dt_days_ago(0, 8)),
    ]
    for i, csl in enumerate(ref["counselors"][:5]):
        n.append(Notification(recipient_user_id=csl.user_id, category="appointment",
                              event_code="appointment.scheduled",
                              title=f"نوبت جدید برای پرونده {cases[i].case_number} ثبت شد",
                              severity="info", entity_type="appointment", created_at=dt_days_ago(0, 8 + i)))
    for i, u in enumerate(ref["applicant_users"][:4]):
        n.append(Notification(recipient_user_id=u.id, category="psych", event_code="psych.attempt.completed",
                              title="نتیجه آزمون شما آماده مشاهده است", severity="info",
                              created_at=dt_days_ago(i, 15)))
    db.add_all(n)

    db.add_all([
        EmailOutbox(recipient_email="admin@rosepsy.demo", subject="خوش آمدید به رزپسی",
                    body_text="حساب شما ایجاد شد.", status="sent", attempts=1,
                    sent_at=dt_days_ago(6, 9), created_at=dt_days_ago(6, 9)),
        EmailOutbox(recipient_email="reception@rosepsy.demo", subject="خلاصه هفتگی کارتابل",
                    body_text="۲۲ درخواست جدید، ۹ در حال بررسی.", status="sent", attempts=1,
                    sent_at=dt_days_ago(2, 7), created_at=dt_days_ago(2, 7)),
        EmailOutbox(recipient_email="manager@rosepsy.demo", subject="گزارش ماهانه مالی",
                    body_text="خلاصه درآمد و تسویه سازمان‌ها پیوست است.", status="sent", attempts=1,
                    sent_at=dt_days_ago(1, 7), created_at=dt_days_ago(1, 7)),
        EmailOutbox(recipient_email="user2003@mail.demo", subject="فعال‌سازی حساب کاربری",
                    body_text="برای فعال‌سازی روی لینک زیر کلیک کنید.", status="pending", attempts=0,
                    created_at=dt_days_ago(0, 8)),
    ])
    db.add_all([
        SmsOutbox(recipient_mobile="09120000001", purpose="notification",
                  body="نوبت شما در کلینیک رز ثبت شد. کد پیگیری: RS-1404", provider="log",
                  status="sent", attempts=1, sent_at=dt_days_ago(1, 10)),
        SmsOutbox(recipient_mobile="09120000002", purpose="notification",
                  body="یادآوری: جلسه مشاوره فردا ساعت ۱۶ برگزار می‌شود.", provider="log",
                  status="sent", attempts=1, sent_at=dt_days_ago(0, 9)),
        SmsOutbox(recipient_mobile="09120000003", purpose="otp",
                  body="کد ورود شما: ۴۸۲۱۹۱", provider="log", status="sent", attempts=1,
                  sent_at=dt_days_ago(0, 11)),
    ])
    audits = [
        ("auth.login", "user", ref["admin"].id, 1), ("case.create", "case", reception.id, 2),
        ("case.assign", "case", manager.id, 3), ("appointment.schedule", "appointment", reception.id, 4),
        ("assessment.finalize", "assessment", ref["counselors"][0].user_id, 5),
        ("payment.capture", "payment", reception.id, 6), ("psych.submit", "psych_attempt", ref["applicant_users"][0].id, 7),
        ("refund.approve", "refund_request", manager.id, 8), ("import.commit", "import_job", reception.id, 9),
        ("user.create", "user", admin.id, 10),
    ]
    for i, (action, etype, actor, d) in enumerate(audits):
        db.add(AuditEvent(actor_user_id=actor, action=action, entity_type=etype,
                          entity_id=str(uuid_mod.uuid4())[:8], result="success",
                          detail={"source": "demo"}, ip="127.0.0.1",
                          created_at=dt_days_ago(d, 9 + i)))
    job = ImportJob(import_type="applicants", status="committed", importer_user_id=reception.id,
                    original_filename="applicants-1404.xlsx", file_size=18432,
                    total_rows=40, valid_rows=36, error_rows=2, duplicate_rows=2,
                    created_rows=36, committed_at=dt_days_ago(25, 14),
                    created_at=dt_days_ago(25, 13))
    db.add(job)
    db.flush()
    for rn in range(1, 9):
        if rn in (3, 7):
            db.add(ImportRow(job_id=job.id, row_number=rn, status="error",
                             error_text="کد ملی تکراری است" if rn == 3 else "قالب شماره موبایل نامعتبر",
                             payload={"first_name": "نمونه", "last_name": "خطا", "national_id": "00"}))
        else:
            db.add(ImportRow(job_id=job.id, row_number=rn, status="valid",
                             payload={"first_name": rng.choice(FEMALE + MALE), "last_name": rng.choice(LAST),
                                      "national_id": gen_national_id(set()),
                                      "mobile": gen_mobile(set()), "unit": "واحد اداری"}))
    db.flush()


def wipe(db) -> None:
    """پاک‌سازی کامل داده‌های دمو (به‌ترتیب وابستگی فرزند → والد)."""
    order = [
        ProcessInstanceEvent, ProcessInstance, ProcessVersion, ProcessDefinition,
        ImportRow, ImportJob, AuditEvent, SmsOutbox, EmailOutbox, Notification,
        TicketMessage, Ticket, Complaint, SessionSurvey, SessionNoteRevision, Session,
        SlotClaim,
        Refund, RefundRequest, Payment, InvoiceItem, Invoice,
        # سفارش‌ها پیش از تخفیف/دوره/آزمون/تعرفه/قرارداد (FKهای RESTRICT)
        Order,
        DiscountRedemption, Discount,
        Certificate, ExamAttempt, ExamQuestion, Exam,
        CourseEnrollment, CourseSession, Course, Content, PsychAttempt,
        JournalLine, JournalEntry, Account,
        WalletEntry, Wallet,
        Appointment,
        ReviewAction, Assessment, FormVersion, Referral, Recommendation, TreatmentPlan, Diagnosis,
        Consent, CaseAssignment, Case, IntakeQuestionnaire, ConsultationRequest, Applicant,
        CounselorCredential, Counselor, UserScope, User,
        ServiceTopic, ContractService, BranchServiceOffering, Branch, Clinic,
        TariffVersion, Service, Topic, Specialty,
        Contract, Organization, ServiceLocation, OrganizationUnit,
    ]
    for model in order:
        db.execute(delete(model))
    db.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="داده نمونه جامع رزپسی")
    parser.add_argument("--reset", action="store_true", help="پاک‌سازی کامل داده‌های دمو")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            wipe(db)
            print("همه داده‌های دمو پاک شد.")
            return 0
        existing = db.scalar(select(func.count(Applicant.id))) or 0
        if existing >= 90:
            # حالت تکمیلی (فاز ۴۹): دیتابیس پرشدهٔ seed قبلی را دست نمی‌زنیم؛
            # فقط بخش‌های جدید (فرایندها، شعب ۳۱ استان، عکس مشاوران) اضافه می‌شود.
            print("داده نمونه قبلی یافت شد؛ اجرای حالت تکمیلی فاز ۴۹ (بدون دست‌زدن به داده موجود)...")
            ref = seed_base(db)
            _reqs = db.scalars(select(ConsultationRequest).order_by(
                ConsultationRequest.created_at.desc()).limit(3)).all()
            reqs = [(r, None) for r in _reqs]
            cases = list(db.scalars(select(Case).order_by(Case.created_at).limit(1)).all())
            print("  فرایندهای سازمانی (BPMN نسخه‌دار) + نمونه‌های مانیتورینگ...")
            seed_processes(db, ref, reqs, cases)
            print("  شعب ۳۱ استان با موقعیت پیش‌فرض...")
            seed_provinces(db, ref)
            print("  عکس پیش‌فرض مشاوران...")
            seed_counselor_photos(list(db.scalars(select(Counselor)).all()))
            db.commit()
            counts = {}
            for label, model in [
                ("فرایند تعریف‌شده", ProcessDefinition), ("نسخه فرایند", ProcessVersion),
                ("نمونه فرایند", ProcessInstance), ("شعب", Branch),
            ]:
                counts[label] = db.scalar(select(func.count(model.id)))
            print("\n✅ تکمیل فاز ۴۹ انجام شد:")
            for k, v in counts.items():
                print(f"   {k}: {v}")
            print("برای بازسازی کامل داده از صفر: --reset")
            return 0

        print("۱/۱۳ ساختار سازمانی، خدمات، مشاوران و کاربران ستاد...")
        ref = seed_base(db)
        print("۲/۱۳ ۱۰۰ متقاضی + ۲۰ حساب پورتال...")
        applicants = seed_applicants(db, ref)
        print("۳/۱۳ درخواست‌های مشاوره سایت...")
        reqs = seed_requests(db, ref, applicants)
        print("۴/۱۳ پرونده‌ها، تخصیص‌ها و رضایت‌ها...")
        cases = seed_cases(db, ref, applicants, reqs)
        print("۵/۱۳ تقویم نوبت‌ها (پر و خالی)...")
        appts = seed_appointments(db, ref, cases)
        print("۶/۱۳ جلسات، یادداشت‌ها و نظرسنجی...")
        seed_sessions(db, ref, appts)
        print("۷/۱۳ تشخیص، طرح درمان، توصیه و ارجاع...")
        seed_clinical(db, ref, cases)
        print("۸/۱۳ فرم‌های بالینی و چرخه بازبینی...")
        seed_forms(db, ref, cases)
        print("۹/۱۳ مالی: سفارش، پرداخت، فاکتور، کیف پول، استرداد، حسابداری...")
        seed_finance(db, ref, appts)
        print("۱۰/۱۳ بانک آزمون‌های روان‌شناسی + اجراهای نمونه...")
        seed_psych(db, ref)
        print("۱۱/۱۳ آموزش، پشتیبانی، اعلان‌ها و حسابرسی...")
        seed_learning(db, ref)
        seed_support(db, ref)
        seed_comms(db, ref, cases)
        print("۱۲/۱۳ فرایندهای سازمانی (BPMN نسخه‌دار) + نمونه‌های مانیتورینگ...")
        seed_processes(db, ref, reqs, cases)
        print("۱۳/۱۳ شعب ۳۱ استان با موقعیت پیش‌فرض...")
        seed_provinces(db, ref)
        db.commit()

        from app.models.people import Applicant as A
        counts = {}
        for label, model in [
            ("متقاضی", A), ("درخواست مشاوره", ConsultationRequest), ("پرونده", Case),
            ("نوبت", Appointment), ("جلسه", Session), ("ارزیابی", Assessment),
            ("سفارش", Order), ("پرداخت", Payment), ("اجرای آزمون", PsychAttempt),
            ("اعلان", Notification), ("کاربر", User),
            ("فرایند تعریف‌شده", ProcessDefinition), ("نسخه فرایند", ProcessVersion),
            ("نمونه فرایند", ProcessInstance), ("شعب", Branch),
        ]:
            counts[label] = db.scalar(select(func.count(model.id)))
        print("\n✅ داده نمونه جامع ایجاد شد:")
        for k, v in counts.items():
            print(f"   {k}: {v}")
        print("\nحساب‌های دمو:")
        print("  admin / Rosepsy@Admin2026   (مدیر سامانه)")
        print("  counselor1..8 / Demo@1234   (مشاوران)")
        print("  reception1 / manager1 / supervisor1 / dpo1 / Demo@1234")
        print("  user2001..user2020 / Demo@1234  (پورتال متقاضی)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
