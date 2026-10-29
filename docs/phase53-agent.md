# فاز ۵۳ — عامل هوشمند Rosepsy (الهام از DeepSeek Harness)

## منبع الهام

پروژهٔ متن‌باز [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)
(`dsh`) یک «چارچوب عامل» با معماری *همه‌چیز-یک-پلاگین* (بر پایهٔ Cordis) است.
از سند معماری آن (`docs/architecture.md` و `docs/agent-lifecycle.md`) این
چهار الگو برداشت و به‌صورت بومی در FastAPI پیاده شد — بدون وابستگی جدید و
بدون اجرای کد بیرونیِ آن پروژه:

| الگو در dsh | پیاده‌سازی Rosepsy (فاز ۵۳) |
|---|---|
| Agent Turn/Step Lifecycle (حلقهٔ مدل↔ابزار با سقف گام) | `backend/app/services/agent/engine.py` — `run_turn` با سقف `AI_AGENT_MAX_STEPS` (پیش‌فرض ۴، حداکثر ۸) |
| Tool Registry با شِمای تایپ‌دار (`ctx.tools`) | `backend/app/services/agent/tools.py` — ۹ ابزار فقط‌خواندنی با شِمای JSON-Schema و سیاست نقش |
| Session append-only (`ctx.sessions` / SessionEvent) | جداول `agent_sessions` / `agent_messages` (مایگریشن 0031) + بازپخش با `GET /ai/agent/sessions/{id}/messages` |
| Model Adapter پلاگین‌پذیر و fail-soft (`ctx.llm`) | `backend/app/services/agent/provider.py` — هر سرویس OpenAI-سازگار با `AI_API_BASE_URL` + `AI_API_KEY`؛ هر خطا → سقوط به پاسخ‌دهندهٔ قاعده‌محور فاز ۳۵ |

## ابزارهای عامل (فاز ۵۳)

عمومی (هر کاربر واردشده؛ فقط دادهٔ خودش یا دادهٔ عمومی):

- `search_services` — جست‌وجوی خدمات فعال با کلیدواژه
- `list_branches` — شعب منتشرشده (فیلتر شهر)
- `my_orders` — سفارش‌های اخیر خود کاربر
- `my_appointments` — نوبت‌های آیندهٔ خود کاربر
- `wallet_balance` — مانده کیف پول خود کاربر
- `service_topics` — دسته‌بندی موضوعی خدمات

کارکنان (داخل اجرا دوباره چک نقش می‌شود — defense in depth):

- `cases_summary` — شمار پرونده‌ها به تفکیک وضعیت (بدون محتوای بالینی)
- `no_show_risk` — شمار نوبت‌های پرریسک عدم‌حضور (منطق B27)
- `upcoming_appointments_staff` — نوبت‌های پیش‌روی سامانه

## API

| مسیر | توضیح |
|---|---|
| `GET /ai/agent/config` | آمادگی LLM + کاتالوگ ابزارهای مجاز همان کاربر |
| `POST /ai/agent/chat` | یک Turn عامل؛ `session_id` اختیاری؛ خروجی شامل `steps` (رد ابزارها) |
| `GET /ai/agent/sessions` | نشست‌های کاربر |
| `GET /ai/agent/sessions/{id}/messages` | بازپخش نشست (فقط مالک) |
| `DELETE /ai/agent/sessions/{id}` | حذف نشست خود (آبشاری) |

همهٔ مسیرها زیر `/api/v1` و `/api/v2` (پاکت‌بندی‌شده) سرو می‌شوند و از
سقف نرخ ۳۰ پیام در دقیقهٔ فاز ۳۵ پیروی می‌کنند.

## فعال‌سازی مدل زبانی (اختیاری)

در `C:\rosepsy\app\.env` (سپس ری‌استارت rosepsy-api):

```
AI_API_KEY=sk-...
AI_API_BASE_URL=https://api.deepseek.com/v1
AI_MODEL=deepseek-chat
# AI_AGENT_MAX_STEPS=4
```

نمونه‌های سازگار دیگر: GLM (`https://open.bigmodel.cn/api/paas/v4` +
`glm-4.5-flash`)، OpenAI، یا vLLM محلی (`http://127.0.0.1:8001/v1`).

بدون کلید: عامل به همان پاسخ‌دهندهٔ قاعده‌محور فاز ۳۵ سقوط می‌کند
(fail-soft) و سامانه بدون وقفه کار می‌کند.

## مرزهای امنیتی (تداوم فاز ۳۵)

- کلید سرویس هرگز به کلاینت، لاگ یا نشست نمی‌رود؛
- ابزارها «فقط‌خواندنی»اند؛ هیچ ابزاری داده می‌نویسد؛
- محتوای بالینی پرونده‌ها به مدل ارسال نمی‌شود (ابزارها فقط شمارش/وضعیت)؛
- دیسکلیمر «جایگزین مشاوره حرفه‌ای نیست» روی هر پاسخ می‌ماند؛
- خطای ابزار/مدل هرگز Turn را نمی‌شکند (دیکشنری خطا → ادامهٔ مکالمه).
