// فاز ۳۹ - آزمون بار (Load) — رشد پله‌ای کاربران مجازی روی قرارداد v2
// اجرا: k6 run -e BASE_URL=http://127.0.0.1:8000 -e E2E_USER=... -e E2E_PASS=... perf/load.js
//
// سناریو: ورود + خواندن فهرست‌های پرتکرار (کاربران/اعلان‌ها/پرونده‌ها/تخصص‌ها).
// آستانه‌ها براساس SLO پیشنهادی ADR-02/سند جامع (p95<800ms، نرخ خطا<2%).
import http from "k6/http";
import { check, group, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const USER = __ENV.E2E_USER || "";
const PASS = __ENV.E2E_PASS || "";

export const options = {
  scenarios: {
    load: {
      executor: "ramping-vus",
      startVUs: 1,
      stages: [
        { duration: "20s", target: 5 },
        { duration: "30s", target: 10 },
        { duration: "20s", target: 20 },
        { duration: "20s", target: 20 },
        { duration: "10s", target: 0 },
      ],
      gracefulRampDown: "5s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.02"],
    http_req_duration: ["p(95)<800", "p(99)<1500"],
  },
};

export function setup() {
  if (!USER || !PASS) {
    console.error("E2E_USER/E2E_PASS تنظیم نشده است — بار بدون احراز هویت بی‌معناست");
    return { token: "" };
  }
  const res = http.post(
    `${BASE_URL}/api/v2/auth/login`,
    JSON.stringify({ username: USER, password: PASS }),
    { headers: { "Content-Type": "application/json" } }
  );
  return { token: res.json("data.access_token") || "" };
}

export default function (data) {
  if (!data.token) return;
  const auth = { headers: { Authorization: `Bearer ${data.token}` } };

  group("پیمایش فهرست‌های پرتکرار", () => {
    const users = http.get(`${BASE_URL}/api/v2/users?page_size=10`, auth);
    check(users, { "users 200": (r) => r.status === 200 });

    const notifs = http.get(`${BASE_URL}/api/v2/notifications`, auth);
    check(notifs, { "notifications 200": (r) => r.status === 200 });

    const me = http.get(`${BASE_URL}/api/v2/auth/me`, auth);
    check(me, { "me 200": (r) => r.status === 200 });

    const specialties = http.get(`${BASE_URL}/api/v2/specialties`, auth);
    check(specialties, { "specialties 200": (r) => r.status === 200 });
  });
  sleep(0.6);
}
