// فاز ۸۴ — Provider محتوای عمومی: واکشی یک‌بارهٔ سندهای منتشرشده از API و
// bump کردن نسخه تا اپ با متن‌های ویرایش‌شدهٔ ادمین دوباره رندر شود.
// اگر API در دسترس نبود یا سندی منتشر نشده بود، نسخه bump نمی‌شود (بدون فلش).
import { createContext, useContext, useEffect, useState } from "react";
import { fetchAndApplySiteContent } from "./content/override";

const SiteContentVersion = createContext(0);

export function SiteContentProvider({ children }: { children: React.ReactNode }) {
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let alive = true;
    fetchAndApplySiteContent().then((changed) => {
      if (alive && changed) setVersion((v) => v + 1);
    });
    return () => {
      alive = false;
    };
  }, []);
  return <SiteContentVersion.Provider value={version}>{children}</SiteContentVersion.Provider>;
}

/** نسخهٔ فعلی محتوا — مصرف‌کننده‌ها فقط برای رندر مجدد به آن گوش می‌دهند */
export function useSiteContentVersion(): number {
  return useContext(SiteContentVersion);
}
