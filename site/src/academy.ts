// فاز ۸۶ - آکادمی رز: کلاینت ویترین دوره + ورود OTP + سبد خرید + پرداخت
// (الگوی همان api.ts سایت؛ توکن در localStorage با انقضای ۳۰ روزه سمت سرور)

const TOKEN_KEY = "rosepsy_academy_token";
const USER_KEY = "rosepsy_academy_user";
const CART_KEY = "rosepsy_academy_cart";
export const CART_EVENT = "rosepsy-cart-changed";

// ---------------------------------------------------------------- انواع
export interface AcademyUser {
  id: string;
  display_name: string;
  mobile: string;
}

export interface AcademySession {
  access_token: string;
  user: AcademyUser;
}

export interface AcademyEpisode {
  id: string;
  title: string;
  description: string | null;
  duration_minutes: number;
  sort_order: number;
  is_free: boolean;
  release_after_days: number;
  has_video: boolean;
  session_date: string | null;
}

export interface AcademyCourseSummary {
  id: string;
  slug: string;
  title: string;
  summary: string | null;
  topic_name: string | null;
  price_amount: number;
  currency: string;
  is_free: boolean;
  cover_image_url: string | null;
  episodes_count: number;
  free_episodes_count: number;
  total_minutes: number;
}

export interface AcademyCourseDetail extends AcademyCourseSummary {
  description: string | null;
  trailer_url: string | null;
  starts_at: string | null;
  episodes: AcademyEpisode[];
}

export interface AcademyMyCourse {
  enrollment_id: string;
  status: "pending" | "active" | "completed" | "cancelled";
  activated_at: string | null;
  course: {
    id: string;
    slug: string;
    title: string;
    summary: string | null;
    cover_image_url: string | null;
    price_amount: number;
    is_free: boolean;
    episodes_count: number;
  };
  watched_count: number;
  order: { id: string; order_number: string; status: string; payable_amount: number } | null;
}

export interface MyCourseDetail extends AcademyCourseSummary {
  description: string | null;
  trailer_url: string | null;
  enrollment_status: string;
  activated_at: string | null;
  episodes: (AcademyEpisode & { watched?: boolean; access?: string })[];
}

// ---------------------------------------------------------------- نشست (OTP)
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): AcademyUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveSession(s: AcademySession): void {
  localStorage.setItem(TOKEN_KEY, s.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(s.user));
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function detail(r: Response, fallback: string): Promise<never> {
  const d = await r.json().catch(() => null);
  throw new Error((d && d.detail) || fallback);
}

// ---------------------------------------------------------------- OTP
export async function academyRequestCode(
  mobile: string,
): Promise<{ status: string; expires_in: number; dev_code?: string; dev_notice?: string }> {
  const r = await fetch("/api/v1/academy/auth/request-code", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mobile }),
  });
  if (!r.ok) await detail(r, "خطا در ارسال کد تأیید");
  return r.json();
}

export async function academyVerifyCode(
  mobile: string,
  code: string,
  fullName?: string,
): Promise<AcademySession> {
  const r = await fetch("/api/v1/academy/auth/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mobile, code, full_name: fullName || undefined }),
  });
  if (!r.ok) await detail(r, "کد وارد شده نادرست است");
  return r.json();
}

// ---------------------------------------------------------------- ویترین عمومی
export async function fetchAcademyCourses(): Promise<AcademyCourseSummary[]> {
  const r = await fetch("/api/v1/academy/courses");
  if (!r.ok) throw new Error("خطا در دریافت دوره‌ها");
  return (await r.json()).items;
}

export async function fetchAcademyCourse(slug: string): Promise<AcademyCourseDetail> {
  const r = await fetch(`/api/v1/academy/courses/${encodeURIComponent(slug)}`);
  if (r.status === 404) throw new Error("دوره یافت نشد یا منتشر نشده است");
  if (!r.ok) throw new Error("خطا در دریافت دوره");
  return r.json();
}

// ---------------------------------------------------------------- سبد خرید
export function getCart(): string[] {
  try {
    const raw = localStorage.getItem(CART_KEY);
    const arr = raw ? (JSON.parse(raw) as string[]) : [];
    return Array.isArray(arr) ? arr.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function addToCart(courseId: string): void {
  const cur = getCart();
  if (!cur.includes(courseId)) {
    localStorage.setItem(CART_KEY, JSON.stringify([...cur, courseId]));
    window.dispatchEvent(new CustomEvent(CART_EVENT));
  }
}

export function removeFromCart(courseId: string): void {
  localStorage.setItem(CART_KEY, JSON.stringify(getCart().filter((id) => id !== courseId)));
  window.dispatchEvent(new CustomEvent(CART_EVENT));
}

export function clearCart(): void {
  localStorage.removeItem(CART_KEY);
  window.dispatchEvent(new CustomEvent(CART_EVENT));
}

export function cartCount(): number {
  return getCart().length;
}

// ---------------------------------------------------------------- پرداخت
export interface CheckoutResult {
  order: {
    id: string;
    order_number: string;
    payable_amount: number;
    courses: { id: string; title: string; price: number }[];
  } | null;
  enrolled_free: { course_id: string; title: string; status: string }[];
}

export async function academyCheckout(courseIds: string[]): Promise<CheckoutResult> {
  const r = await fetch("/api/v1/academy/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ course_ids: courseIds }),
  });
  if (!r.ok) await detail(r, "خطا در ثبت سفارش");
  return r.json();
}

export interface PayResult {
  redirect_url: string;
  authority: string;
  gateway: string;
  order_number: string;
  amount: number;
  currency: string;
}

export async function academyPay(orderId: string): Promise<PayResult> {
  const r = await fetch(`/api/v1/academy/orders/${orderId}/pay`, {
    method: "POST",
    headers: { ...authHeaders() },
  });
  if (!r.ok) await detail(r, "خطا در آغاز پرداخت");
  return r.json();
}

export interface AcademyOrderStatus {
  id: string;
  order_number: string;
  status: "pending" | "paid" | "cancelled" | "failed";
  payable_amount: number;
  currency: string;
  items: { course_id: string; title: string; price_amount: number }[];
  payment: { gateway: string; status: string; fail_reason: string | null; paid_at: string | null } | null;
}

export async function academyOrderStatus(orderId: string): Promise<AcademyOrderStatus> {
  const r = await fetch(`/api/v1/academy/orders/${orderId}`, { headers: { ...authHeaders() } });
  if (!r.ok) await detail(r, "خطا در بررسی وضعیت سفارش");
  return r.json();
}

// ---------------------------------------------------------------- دوره‌های من
export async function fetchAcademyMe(): Promise<{ user: AcademyUser; courses: AcademyMyCourse[] }> {
  const r = await fetch("/api/v1/academy/me", { headers: { ...authHeaders() } });
  if (r.status === 401) throw new Error("unauthorized");
  if (!r.ok) throw new Error("خطا در دریافت دوره‌های من");
  return r.json();
}

export async function fetchAcademyMyCourse(courseId: string): Promise<MyCourseDetail> {
  const r = await fetch(`/api/v1/academy/me/courses/${courseId}`, { headers: { ...authHeaders() } });
  if (!r.ok) await detail(r, "دسترسی به این دوره مجاز نیست");
  return r.json();
}

// ---------------------------------------------------------------- پخش ویدیو
export async function fetchVideoAccess(
  sessionId: string,
): Promise<{ kind: "mp4" | "embed"; url: string; title: string }> {
  const r = await fetch(`/api/v1/academy/videos/${sessionId}`, { headers: { ...authHeaders() } });
  if (!r.ok) await detail(r, "دسترسی به این ویدیو مجاز نیست");
  return r.json();
}

export async function markWatched(sessionId: string, watched = true): Promise<void> {
  await fetch(`/api/v1/academy/videos/${sessionId}/watched`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ watched }),
  }).catch(() => undefined);
}
