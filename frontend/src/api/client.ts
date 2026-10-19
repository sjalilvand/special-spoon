import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from "axios";
import { tokenStore } from "../auth/tokenStore";

/**
 * فاز ۳۹ - مهاجرت فرانت‌اند به قرارداد ADR-03 (/api/v2):
 *
 * سیم (wire) نسخه v2 پاسخ‌ها را در پاکت استاندارد
 *   موفقیت: {"data": ..., "meta": {...}, "errors": null}
 *   خطا:    {"data": null, "meta": {...}, "errors": [{code, message, details?}]}
 * برمی‌گرداند. این ماژول تنها نقطه سازگاری (adapter) بین سیم v2 و شکل مصرف
 * داخلی برنامه است:
 *
 * - interceptor موفقیت، `res.data` را به payload واقعی (data) می‌کاهد و
 *   `meta` پاکت را روی `res.meta` (augmentation تایپ axios) در دسترس می‌گذارد؛
 * - پاسخ‌های صفحه‌بندی‌شده، اطلاعات total/page/... را در `res.meta.pagination`
 *   دارند — helper `paginationOf` برای بازچینی شکل‌های Paged در لایه api؛
 * - پاسخ‌های غیر JSON (دانلود فایل B39، blob قالب import) دست‌نخورده عبور
 *   می‌کنند؛
 * - `errDetail` خطا را از `errors[0].message` پاکت می‌خواند و شکل قدیمی
 *   `{detail}` را هم به‌عنوان fallback پشتیبانی می‌کند.
 */

export interface EnvelopeMeta {
  request_id: string;
  timestamp: string;
  version: string;
  duration_ms: number;
  idempotency_key?: string;
  pagination?: Record<string, unknown>;
}

interface EnvelopeBody {
  data: unknown;
  meta?: EnvelopeMeta;
  errors: unknown;
}

declare module "axios" {
  export interface AxiosResponse<T = any, D = any> {
    /** متادیتای پاکت v2 (ADR-03) — پس از گشودن پاکت در interceptor */
    meta?: EnvelopeMeta;
  }
}

function isEnvelope(x: unknown): x is EnvelopeBody {
  return (
    typeof x === "object" &&
    x !== null &&
    "data" in x &&
    "meta" in x &&
    "errors" in x &&
    typeof (x as EnvelopeBody).meta === "object" &&
    (x as EnvelopeBody).meta !== null &&
    typeof (x as EnvelopeBody).meta!.version === "string"
  );
}

/** اطلاعات صفحه‌بندی پاسخ‌های فهرست v2 ({items,...} → data + meta.pagination) */
export function paginationOf(res: AxiosResponse): Record<string, unknown> {
  return res.meta?.pagination ?? {};
}

function unwrapEnvelope(res: AxiosResponse): AxiosResponse {
  const rt = res.config.responseType;
  if (rt && rt !== "json" && rt !== "text") return res; // blob/arraybuffer — دانلود B39
  if (isEnvelope(res.data)) {
    const envelope = res.data as EnvelopeBody;
    res.data = envelope.data;
    res.meta = envelope.meta;
  }
  return res;
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api/v2",
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  if (tokenStore.accessToken) {
    config.headers.Authorization = `Bearer ${tokenStore.accessToken}`;
  }
  return config;
});

const NO_REFRESH_PATHS = ["/auth/login", "/auth/refresh", "/auth/activate"];

let refreshPromise: Promise<string | null> | null = null;

async function callRefresh(): Promise<string | null> {
  try {
    const res = await axios.post(`${apiClient.defaults.baseURL}/auth/refresh`, {}, { withCredentials: true });
    const payload = isEnvelope(res.data) ? res.data.data : res.data;
    return (payload as { access_token?: string })?.access_token ?? null;
  } catch {
    return null;
  }
}

apiClient.interceptors.response.use(unwrapEnvelope, async (error: AxiosError) => {
  const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
  const url = original?.url ?? "";
  const shouldTryRefresh =
    error.response?.status === 401 &&
    original &&
    !original._retry &&
    !NO_REFRESH_PATHS.some((p) => url.includes(p));

  if (shouldTryRefresh) {
    original!._retry = true;
    refreshPromise = refreshPromise ?? callRefresh();
    const newToken = await refreshPromise;
    refreshPromise = null;
    if (newToken) {
      tokenStore.accessToken = newToken;
      return apiClient(original!);
    }
    tokenStore.accessToken = null;
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }
  return Promise.reject(error);
});

export function errDetail(e: unknown): string {
  const anyE = e as { response?: { data?: unknown } };
  const body = anyE?.response?.data;

  // پاکت v2: errors: [{code, message, details?}]
  if (body && typeof body === "object" && Array.isArray((body as EnvelopeBody).errors)) {
    const errs = ((body as EnvelopeBody).errors ?? []) as { code?: string; message?: string }[];
    const msg = errs
      .map((x) => x.message || x.code || "")
      .filter(Boolean)
      .join(" — ");
    if (msg) return msg;
  }

  // قرارداد v1 (fallback) و پاسخ‌های بدون پاکت
  const d = (body as { detail?: unknown } | undefined)?.detail;
  if (typeof d === "string") return d;
  if (d && typeof d === "object") {
    const obj = d as { message?: string; errors?: { label?: string; error?: string }[] };
    const errs = (obj.errors ?? [])
      .map((x) => `${x.label ?? ""}: ${x.error ?? ""}`.trim())
      .filter(Boolean);
    return [obj.message, ...errs].filter(Boolean).join(" — ");
  }
  return "خطای نامشخص رخ داد";
}
