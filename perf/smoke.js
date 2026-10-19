// فاز ۳۹ - آزمون Performance (دود) — مسیرهای حیاتی روی قرارداد v2
// اجرا: k6 run -e BASE_URL=http://127.0.0.1:8000 -e E2E_USER=... -e E2E_PASS=... perf/smoke.js
import http from "k6/http";
import { check, group, sleep } from "k6";
import { Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const USER = __ENV.E2E_USER || "";
const PASS = __ENV.E2E_PASS || "";

const v2Login = new Trend("rosepsy_v2_login_duration");
const v2ListUsers = new Trend("rosepsy_v2_users_duration");
const v2Notifications = new Trend("rosepsy_v2_notifications_duration");
const v2Cases = new Trend("rosepsy_v2_cases_duration");

export const options = {
  vus: 1,
  iterations: 12,
  thresholds: {
    "http_req_failed{scenario:default}": ["rate<0.01"],
    "http_req_duration{scenario:default}": ["p(95)<500"],
    rosepsy_v2_login_duration: ["p(95)<400"],
    rosepsy_v2_users_duration: ["p(95)<400"],
  },
};

export function setup() {
  if (!USER || !PASS) {
    console.error("E2E_USER/E2E_PASS تنظیم نشده است — فقط health آزموده می‌شود");
    return { token: "" };
  }
  const res = http.post(
    `${BASE_URL}/api/v2/auth/login`,
    JSON.stringify({ username: USER, password: PASS }),
    { headers: { "Content-Type": "application/json" } }
  );
  const body = res.json();
  // قرارداد ADR-03: پاکت {data, meta, errors}
  const token = body?.data?.access_token || "";
  check(res, {
    "login 200": (r) => r.status === 200,
    "پاکت v2": () => body?.meta?.version === "v2" && body?.errors === null,
  });
  return { token };
}

export default function (data) {
  group("سلامت", () => {
    const h = http.get(`${BASE_URL}/api/v1/health`);
    check(h, { "health 200": (r) => r.status === 200 && r.json("status") === "ok" });
  });

  group("ورود v2", () => {
    const res = http.post(
      `${BASE_URL}/api/v2/auth/login`,
      JSON.stringify({ username: USER, password: PASS }),
      { headers: { "Content-Type": "application/json" } }
    );
    v2Login.add(res.timings.duration);
    check(res, {
      "login 200": (r) => r.status === 200,
      "پاکت v2 با access_token": (r) => r.json("data.access_token") !== undefined,
    });
  });

  if (data.token) {
    const auth = { headers: { Authorization: `Bearer ${data.token}` } };
    group("فهرست کاربران v2 (صفحه‌بندی)", () => {
      const res = http.get(`${BASE_URL}/api/v2/users?page_size=5`, auth);
      v2ListUsers.add(res.timings.duration);
      check(res, {
        "users 200": (r) => r.status === 200,
        "items → data آرایه": (r) => Array.isArray(r.json("data")),
        "meta.pagination.total": (r) => r.json("meta.pagination.total") !== undefined,
      });
    });
    group("اعلان‌ها v2 (پاسخ intact)", () => {
      const res = http.get(`${BASE_URL}/api/v2/notifications`, auth);
      v2Notifications.add(res.timings.duration);
      check(res, {
        "notifications 200": (r) => r.status === 200,
        "{items,unread} حفظ شده": (r) => r.json("data.items") !== undefined,
      });
    });
    group("پروفایل کاربر v2 (پاسخ intact)", () => {
      const res = http.get(`${BASE_URL}/api/v2/auth/me`, auth);
      v2Cases.add(res.timings.duration);
      check(res, {
        "me 200": (r) => r.status === 200,
        "شیء دست‌نخورده": (r) => r.json("data.username") !== undefined,
      });
    });
  }
  sleep(0.4);
}
