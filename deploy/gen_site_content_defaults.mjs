// فاز ۸۴ — تولید app/data/site_content_defaults.json از فایل‌های محتوای site
//
// «متن‌های پیش‌فرض» صفحات عمومی فقط در site/src/content/*.ts زندگی می‌کنند
// (تک‌منبع حقیقت). این اسکریپت آن‌ها را می‌خواند و سند JSON پیش‌فرض را برای
// backend تولید می‌کند تا ویرایشگر پنل، متنِ فعلی سایت را به‌عنوان پایهٔ ویرایش
// نشان دهد. هر بار متن‌های پیش‌فرض در site/src/content تغییر کرد، یک‌بار اجرا
// شود:
//   node deploy/gen_site_content_defaults.mjs
//
// روش خواندن: فایل‌های texts.ts / psycho.ts / payRules.ts ماژول‌های «دادهٔ
// خالص» (بدون import) هستند؛ Node ۲۴+ با strip-types آن‌ها را مستقیم می‌خواند.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const siteContent = resolve(root, "site", "src", "content");
const outPath = resolve(root, "backend", "app", "data", "site_content_defaults.json");

const { texts } = await import(`${siteContent}/texts.ts`);
const { psycho } = await import(`${siteContent}/psycho.ts`);
const { payRules } = await import(`${siteContent}/payRules.ts`);
const { clinics } = await import(`${siteContent}/clinics.ts`);
const { specialist } = await import(`${siteContent}/specialist.ts`);

const doc = {
  _readme:
    "متن‌های پیش‌فرض صفحات عمومی — تولید خودکار از site/src/content (تغییر ندهید؛ deploy/gen_site_content_defaults.mjs را اجرا کنید)",
  home: texts,
  psycho: psycho,
  "payment-rules": payRules,
  clinics: clinics,
  specialist: specialist,
};

mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, JSON.stringify(doc, null, 2) + "\n", "utf8");
console.log("WROTE", outPath, `${Math.round(JSON.stringify(doc).length / 1024)}KB`);
