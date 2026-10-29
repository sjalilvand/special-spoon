import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import * as authApi from "../api/auth";
import type { Me } from "../api/auth";
import { tokenStore } from "./tokenStore";
import {
  endImpersonation,
  readImpersonation,
  type ImpersonationInfo,
} from "./impersonation";

interface AuthContextValue {
  user: Me | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<Me>;
  logout: () => Promise<void>;
  /** فاز ۶۰: اطلاعات حالت «ورود با هویت کاربر» (در غیر این صورت null) */
  impersonation: ImpersonationInfo | null;
  /** فاز ۶۰: بازگشت تمیز به حساب مدیر — بدون ورود مجدد (کوکی refresh مدیر سرجاست) */
  exitImpersonation: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [impersonation, setImpersonation] = useState<ImpersonationInfo | null>(() =>
    readImpersonation()
  );

  // بازیابی نشست با Cookie هنگام بارگذاری (بند ۱۰: مجوز صفحات براساس /auth/me)
  // فاز ۶۰: اگر حالت مشاهده فعال باشد، توکن کاربر هدف از sessionStorage
  // بازگردانی می‌شود تا /auth/me با هویت همان کاربر پاسخ دهد.
  useEffect(() => {
    const imp = readImpersonation();
    if (imp && !tokenStore.accessToken) {
      tokenStore.accessToken = imp.token;
    }
    authApi
      .fetchMe()
      .then((me) => setUser(me))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await authApi.login(username, password);
    tokenStore.accessToken = res.access_token;
    const me = await authApi.fetchMe();
    setUser(me);
    return me;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      tokenStore.accessToken = null;
      setUser(null);
    }
  }, []);

  // فاز ۶۰: خروج از حالت مشاهده — کلید sessionStorage پاک و به مسیر بازگشت
  // مدیر reload کامل می‌شود؛ کوکی refresh مدیر دست‌نخورده مانده است.
  const exitImpersonation = useCallback(() => {
    const info = readImpersonation();
    endImpersonation();
    tokenStore.accessToken = null;
    setImpersonation(null);
    const base = import.meta.env.BASE_URL.replace(/\/$/, "");
    window.location.href = info?.returnPath || `${base}/users`;
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, logout, impersonation, exitImpersonation }),
    [user, loading, login, logout, impersonation, exitImpersonation]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
