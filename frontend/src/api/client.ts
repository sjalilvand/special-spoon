import axios from "axios";

// بند ۴.۲ سند: Access Token فقط در حافظه برنامه نگهداری می‌شود (نه localStorage)
// پیاده‌سازی کامل توکن‌ها در فاز ۲ انجام می‌شود.
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api/v1",
  headers: { "Content-Type": "application/json" },
});
