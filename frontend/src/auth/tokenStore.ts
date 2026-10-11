// بند ۴.۲ سند: Access Token فقط در حافظه برنامه نگهداری می‌شود (نه localStorage)
export const tokenStore: { accessToken: string | null } = { accessToken: null };
