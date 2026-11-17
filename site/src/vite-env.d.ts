/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** فاز ۹۵ — مبدأ پشتیبان ثبت فراخوان (IP مستقیم سرور) وقتی CDN بدنهٔ POST را می‌شکند */
  readonly VITE_API_FALLBACK_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
