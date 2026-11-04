/*
  رزپسی — سرویس‌ورکر PWA (فاز ۸۰)
  ---------------------------------------------------------------------------
  وظایف:
    1) ناوبری‌ها (صفحه‌های HTML): «شبکه‌اول» — اگر شبکه در دسترس نبود از کش،
       و در نبودِ هر دو، صفحهٔ برند‌شدهٔ /offline.html نشان داده می‌شود.
       برای اینکه شبکهٔ کند کاربر را معطل نکند، وقتی نسخهٔ کش‌شده داریم حداکثر
       ۶ ثانیه منتظر شبکه می‌مانیم (بدون کش: ۳۰ ثانیه).
    2) دارایی‌های هم‌مبدأ (باندل‌های hashدار، فونت‌ها، عکس‌ها): «کش‌اول» +
       به‌روزرسانی پس‌زمینه (Stale-While-Revalidate) — بارِ دوم به‌شدت سریع‌تر.
    3) /api/ هرگز کش نمی‌شود (نوبت، پرداخت، ورود، چت) — همیشه شبکه.
    4) درخواست‌های غیر GET و مبدأهای دیگر (درگاه پرداخت و...) دست‌نخورده رد می‌شوند.

  انتشار نسخهٔ جدید: کافی است VERSION بالا برود (مثلاً rosepsy-v2)؛
  کش‌های نسخهٔ قبل در activate خودکار پاک می‌شوند.
*/
const VERSION = 'rosepsy-v1';
const STATIC_CACHE = VERSION + '-static';
const RUNTIME_CACHE = VERSION + '-runtime';

// پُلِ کش اولیه (app-shell): حداقل‌های لازم برای باز شدن آفلاین
const PRECACHE_URLS = [
  '/',
  '/offline.html',
  '/manifest.webmanifest',
  '/app-icon-192.png',
  '/app-icon-512.png',
];

// ناوبری‌ها: با کش، حداکثر ۶ ثانیه انتظار شبکه؛ بدون کش، ۳۰ ثانیه
function fetchNavigation(req, hasCache) {
  const timeoutMs = hasCache ? 6000 : 30000;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('network-timeout')), timeoutMs);
    fetch(req).then(
      (res) => { clearTimeout(timer); resolve(res); },
      (err) => { clearTimeout(timer); reject(err); }
    );
  });
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(STATIC_CACHE);
      // هر مورد جداگانه؛ شکست یکی (مثلاً '/' هنوز نسازی‌نشده) نصب را نمی‌اندازد
      await Promise.allSettled(
        PRECACHE_URLS.map((u) => cache.add(new Request(u, { cache: 'reload' })))
      );
      await self.skipWaiting();
    })()
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(
        names
          .filter((n) => n !== STATIC_CACHE && n !== RUNTIME_CACHE)
          .map((n) => caches.delete(n))
      );
      // کنترل صفحه‌های باز را همین حالا بگیر تا اولین بار هم فعال باشد
      await self.clients.claim();
    })()
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;

  // فقط GET هم‌مبدأ — درگاه پرداخت، SSO و فرم‌ها دست‌نخورده بروند
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // API (نوبت/پرداخت/ورود/چت) همیشه از شبکه
  if (url.pathname.startsWith('/api/')) return;

  // --- ناوبری‌ها (HTML) ---
  if (req.mode === 'navigate') {
    event.respondWith(
      (async () => {
        const cached = await caches.match(req, { ignoreSearch: false });
        try {
          const fresh = await fetchNavigation(req, Boolean(cached));
          if (fresh && fresh.status === 200 && fresh.type === 'basic') {
            const copy = fresh.clone();
            const cache = await caches.open(RUNTIME_CACHE);
            cache.put(req, copy);
          }
          return fresh;
        } catch (err) {
          if (cached) return cached;
          const offline = await caches.match('/offline.html');
          if (offline) return offline;
          throw err;
        }
      })()
    );
    return;
  }

  // --- بقیهٔ دارایی‌های هم‌مبدأ: کش‌اول + به‌روزرسانی پس‌زمینه ---
  event.respondWith(
    (async () => {
      const cached = await caches.match(req);
      // به‌روزرسانی پس‌زمینه همیشه شروع می‌شود تا دفعهٔ بعد تازه باشد
      const refresh = fetch(req)
        .then((res) => {
          if (res && res.status === 200 && res.type === 'basic') {
            const copy = res.clone();
            caches.open(RUNTIME_CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => undefined);
      return cached || (await refresh) || Response.error();
    })()
  );
});
