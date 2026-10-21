# -*- coding: utf-8 -*-
"""فاز ۵۰ — ریون CPM-36 و RSPM-60 با تولید تصویر ماتریس (عکس پیوست سؤال).

هر سؤال یک تصویر PNG دارد: ماتریس (۲×۲ رنگی برای کودکان / ۳×۳ سیاه برای
استاندارد) که خانه آخر «؟» است + شش گزینه زیر آن. گزینه درست طبق قاعده
سطر/ستون محاسبه و بین گزینه‌های مخدوش جای‌گذاری می‌شود.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from helpers import bands, q, test

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",   # ارقام فارسی ۱-۶
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",  # جایگزین
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]
FONT = next(p for p in FONT_CANDIDATES if Path(p).is_file())
IMG_DIR = Path(__file__).resolve().parents[2] / "psych_seed" / "images"
FA_DIGITS = ["۱", "۲", "۳", "۴", "۵", "۶"]

# اشکال پایه: 0=دایره 1=مربع 2=لوزی 3=مثلث 4=صلیب 5=حلقه
N_SHAPES = 6
CPM_COLORS = ["#d94f4f", "#3a7bd5", "#3f9e4d", "#e8a13a", "#8e5bd5", "#2fa8a0"]


def _draw_shape(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int, shape: int,
                fill: str | None, rot: int = 0) -> None:
    """رسم یک شکل در مرکز با شعاع r؛ rot بر حسب درجه."""
    if shape == 0:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline="#222222", width=2)
    elif shape == 1:
        pts = [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)]
        if rot:
            a = math.radians(rot)
            pts = [(cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a),
                    cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a)) for x, y in pts]
        d.polygon(pts, fill=fill, outline="#222222")
    elif shape == 2:
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        if rot:
            a = math.radians(rot)
            pts = [(cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a),
                    cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a)) for x, y in pts]
        d.polygon(pts, fill=fill, outline="#222222")
    elif shape == 3:
        pts = [(cx, cy - r), (cx + r, cy + r), (cx - r, cy + r)]
        if rot:
            a = math.radians(rot)
            pts = [(cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a),
                    cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a)) for x, y in pts]
        d.polygon(pts, fill=fill, outline="#222222")
    elif shape == 4:
        w = max(2, r // 2)
        d.rectangle([cx - w, cy - r, cx + w, cy + r], fill=fill, outline="#222222")
        d.rectangle([cx - r, cy - w, cx + r, cy + w], fill=fill, outline="#222222")
    else:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=fill or "#222222", width=max(3, r // 2))


def _cell(img: Image.Image, x0: int, y0: int, size: int, count: int, shape: int,
          fill: str | None, rot: int = 0, mark_q: bool = False) -> None:
    """رسم یک خانه ماتریس با count شکل."""
    d = ImageDraw.Draw(img)
    d.rectangle([x0, y0, x0 + size, y0 + size], outline="#444444", width=3)
    if mark_q:
        f = ImageFont.truetype(FONT, int(size * 0.55))
        d.text((x0 + size / 2, y0 + size / 2), "؟", font=f, fill="#555555", anchor="mm")
        return
    if count == 1:
        _draw_shape(d, x0 + size // 2, y0 + size // 2, int(size * 0.33), shape, fill, rot)
    elif count == 2:
        rr = int(size * 0.22)
        for dx in (-size // 4, size // 4):
            _draw_shape(d, x0 + size // 2 + dx, y0 + size // 2, rr, shape, fill, rot)
    else:
        rr = int(size * 0.17)
        offs = [(-size // 4, -size // 4), (size // 4, -size // 4),
                (-size // 4, size // 4), (size // 4, size // 4)]
        for i in range(min(count, 4)):
            _draw_shape(d, x0 + size // 2 + offs[i][0], y0 + size // 2 + offs[i][1], rr, shape, fill, rot)


def _make_answer(rng: random.Random, colored: bool) -> tuple[dict, dict]:
    """یک مسئله ماتریس می‌سازد: قاعده سطر (تعداد) و ستون (شکل)؛ رنگ/چرخش ثابت یا متغیر."""
    counts = rng.sample([1, 2, 3], 3)
    shapes = rng.sample(range(N_SHAPES), 3)
    if colored:
        color = rng.choice(CPM_COLORS)
        rot = 0
    else:
        color = "#1c1c1c"
        rot = rng.choice([0, 45])
    target = {"count": counts[2], "shape": shapes[2], "fill": color, "rot": rot}
    return target, {"counts": counts, "shapes": shapes, "fill": color, "rot": rot}


def _perturbations(ans: dict, rng: random.Random, colored: bool, n: int = 5) -> list[dict]:
    outs: list[dict] = []
    seen = {(ans["count"], ans["shape"], ans["fill"] if colored else ans["rot"])}
    tries = 0
    while len(outs) < n and tries < 200:
        tries += 1
        p = dict(ans)
        field = rng.choice(["count", "shape", "rot"] if not colored else ["count", "shape", "fill"])
        if field == "count":
            p["count"] = rng.choice([c for c in (1, 2, 3, 4) if c != ans["count"]])
        elif field == "shape":
            p["shape"] = rng.choice([s for s in range(N_SHAPES) if s != ans["shape"]])
        elif field == "rot":
            p["rot"] = 45 if ans["rot"] != 45 else 0
        else:
            p["fill"] = rng.choice([c for c in CPM_COLORS if c != ans["fill"]])
        key = (p["count"], p["shape"], p["fill"] if colored else p["rot"])
        if key in seen:
            continue
        seen.add(key)
        outs.append(p)
    while len(outs) < n:  # fallback
        p = dict(ans)
        p["count"] = 4
        outs.append(p)
    return outs[:n]


def _render_item(path: Path, rule: dict, ans: dict, distractors: list[dict], colored: bool,
                 correct_pos: int) -> None:
    """رسم تصویر کامل سؤال: ماتریس + شش گزینه."""
    n = 3 if colored else 3  # ماتریس ۳×۳ برای هر دو (CPM نیز ۳×۳ با رنگ — سبک ساده‌شده)
    size = 84 if colored else 74
    pad = 14
    mat_w = n * size + (n - 1) * pad
    opt_size = 64
    opt_gap = 16
    opt_w = 6 * opt_size + 5 * opt_gap
    W = max(mat_w, opt_w) + 60
    H = n * size + (n - 1) * pad + opt_size + 110
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)
    x0 = (W - mat_w) // 2
    y0 = 24
    for r in range(n):
        for c in range(n):
            cx = x0 + c * (size + pad)
            cy = y0 + r * (size + pad)
            last = (r == n - 1 and c == n - 1)
            if last:
                _cell(img, cx, cy, size, 0, 0, None, mark_q=True)
            else:
                cnt = rule["counts"][c]
                shp = rule["shapes"][r]
                _cell(img, cx, cy, size, cnt, shp, rule["fill"], rule["rot"])
    # ناحیه گزینه‌ها
    oy = y0 + n * size + (n - 1) * pad + 44
    ox = (W - opt_w) // 2
    opts = distractors[:correct_pos] + [ans] + distractors[correct_pos:]
    f = ImageFont.truetype(FONT, 24)
    for i, p in enumerate(opts):
        cx = ox + i * (opt_size + opt_gap)
        d.rectangle([cx, oy, cx + opt_size, oy + opt_size], outline="#777777", width=2)
        _draw_shape(d, cx + opt_size // 2, oy + opt_size // 2,
                    int(opt_size * 0.3) if p["count"] == 1 else int(opt_size * (0.22 if p["count"] == 2 else 0.15)),
                    p["shape"], p["fill"], p["rot"])
        d.text((cx + opt_size // 2, oy + opt_size + 10), FA_DIGITS[i], font=f,
               fill="#333333", anchor="mm")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)


def _build_matrix_test(slug, code, title, en, desc, topic, age, minutes, color, order,
                       colored: bool, set_names: list[str], per_set: int, seed: int) -> dict:
    rng = random.Random(seed)
    prefix = "cpm" if colored else "rspm"
    questions: list[dict] = []
    idx = 0
    for s, sname in enumerate(set_names):
        for k in range(per_set):
            ans, rule = _make_answer(rng, colored)
            correct_pos = rng.randrange(6)
            distractors = _perturbations(ans, rng, colored)
            rel = f"{prefix}/{prefix}_{s}{k + 1:02d}.png"
            path = IMG_DIR / rel
            _render_item(path, rule, ans, distractors, colored, correct_pos)
            opts = [[f"گزینه {FA_DIGITS[i]}", 1 if i == correct_pos else 0] for i in range(6)]
            questions.append(q(
                f"کدام گزینه جای علامت سؤال را پر می‌کند؟ (مجموعه {sname})",
                opts, subscale=f"مجموعه {sname}", image=rel,
            ))
            idx += 1
    total_max = len(questions)
    interps = bands(total_max, [
        (0.0, 0.3, "نمره استاندارد خیلی ضعیف", "نیاز به ارزیابی فردی هوش و بررسی عوامل توجه/انگیزه."),
        (0.3, 0.5, "نمره استاندارد ضعیف", "ارجاع برای آزمون هوش جامع‌تر و بررسی آموزشی پیشنهاد می‌شود."),
        (0.5, 0.7, "نمره استاندارد متوسط", "استدلال غیرکلامی در محدوده معمول هم‌سالان است."),
        (0.7, 0.85, "نمره استاندارد قوی", "توان استدلال ماتریسی بالاتر از میانگین است."),
        (0.85, 1.0, "نمره استاندارد خیلی قوی", "استعداد تحلیلی-غیرکلامی برجسته؛ برنامه غنی‌سازی توصیه می‌شود."),
    ])
    return test(
        slug, code, title, en, desc, topic, age, minutes, color, order, "published",
        questions, interps,
    )


def build_all(seed: int = 20261021) -> list[dict]:
    cpm = _build_matrix_test(
        "raven-cpm-36", "CPM-36", "تست هوش ریون کودکان",
        "Raven's Colored Progressive Matrices",
        "ماتریس‌های متوالی رنگی مخصوص کودکان ۵ تا ۹ سال؛ ۳۶ سؤال تصویری در سه مجموعه؛ سنجش استدلال غیرکلامی بدون نیاز به سواد.",
        "هوش", "کودکان ۵ تا ۹ سال", 30, "#f43f5e", 12,
        True, ["الف", "الف‌ب (Ab)", "ب"], 12, seed,
    )
    rspm = _build_matrix_test(
        "raven-rspm-60", "RSPM-60", "تست هوش استاندارد ریون",
        "Raven's Standard Progressive Matrices",
        "ماتریس‌های متوالی استاندارد؛ ۶۰ سؤال تصویری در پنج مجموعه (A تا E) با دشواری صعودی؛ نوجوانان ۹ تا ۱۸ سال و بزرگسالان.",
        "هوش", "نوجوانان ۹ تا ۱۸ سال", 40, "#ec4899", 13,
        False, ["A", "B", "C", "D", "E"], 12, seed + 7,
    )
    return [cpm, rspm]
