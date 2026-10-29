"""فاز ۵۳ - آداپتور مدل LLM (الگوی Model Adapter پلاگین‌پذیر dsh).

- هر سرویس OpenAI-سازگار: فقط base_url + api_key + model کافی است؛
  مثال‌ها:
    DeepSeek:  AI_API_BASE_URL=https://api.deepseek.com/v1   AI_MODEL=deepseek-chat
    GLM/Z.ai:  AI_API_BASE_URL=https://open.bigmodel.cn/api/paas/v4  AI_MODEL=glm-4.5-flash
    OpenAI:    AI_API_BASE_URL=https://api.openai.com/v1     AI_MODEL=gpt-4o-mini
    vLLM محلی: AI_API_BASE_URL=http://127.0.0.1:8001/v1
- فراخوانی با urllib استاندارد (بدون وابستگی جدید) + timeout سخت؛
- fail-soft: هر خطا (شبکه/کلید/فرمت) None برمی‌گرداند و حلقهٔ عامل به
  پاسخ‌دهندهٔ قاعده‌محور فاز ۳۵ سقوط می‌کند؛ کلید هرگز لاگ نمی‌شود؛
- tool-calling با قرارداد استاندارد OpenAI (tools / tool_calls) — همان
  قراردادی که dsh در آداپتورهای خود به کار می‌برد.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.core.config import get_settings

_TIMEOUT_SECONDS = 45


class LlmResult:
    __slots__ = ("content", "tool_calls", "finish_reason")

    def __init__(self, content: str | None, tool_calls: list[dict] | None, finish_reason: str | None):
        self.content = content
        self.tool_calls = tool_calls
        self.finish_reason = finish_reason


def is_enabled() -> bool:
    """فقط با کلید فعال است؛ نبود کلید → قاعده‌محور (fail-soft مثل D07)."""
    s = get_settings()
    return bool((getattr(s, "ai_api_key", "") or "").strip())


def _headers() -> dict[str, str]:
    s = get_settings()
    return {
        "Authorization": f"Bearer {s.ai_api_key}",
        "Content-Type": "application/json",
    }


def _payload(messages: list[dict], tools: list[dict] | None) -> dict[str, Any]:
    s = get_settings()
    body: dict[str, Any] = {
        "model": getattr(s, "ai_model", "deepseek-chat") or "deepseek-chat",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1200,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    return body


def chat_completion(messages: list[dict], tools: list[dict] | None = None) -> LlmResult | None:
    """یک فراخوانی chat/completions؛ هر خطا → None (fail-soft)."""
    s = get_settings()
    base = (getattr(s, "ai_api_base_url", "") or "").strip().rstrip("/")
    if not base or not is_enabled():
        return None
    url = f"{base}/chat/completions"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(_payload(messages, tools)).encode("utf-8"),
            headers=_headers(),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        return LlmResult(
            content=msg.get("content"),
            tool_calls=msg.get("tool_calls"),
            finish_reason=choice.get("finish_reason"),
        )
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError):
        # هر خطای شبکه/کلید/فرمت → سقوط به rule (fail-soft)؛ جزئیات خطا لاگ نمی‌شود
        # تا کلید یا آدرس داخلی افشا نشود.
        return None
