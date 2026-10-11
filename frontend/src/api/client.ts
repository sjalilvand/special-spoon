import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import { tokenStore } from "../auth/tokenStore";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api/v1",
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
    return res.data.access_token as string;
  } catch {
    return null;
  }
}

apiClient.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
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
  }
);

export function errDetail(e: unknown): string {
  const anyE = e as { response?: { data?: { detail?: unknown } } };
  const d = anyE?.response?.data?.detail;
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
