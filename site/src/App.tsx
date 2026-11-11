import { Suspense, lazy, useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Box, CircularProgress } from "@mui/material";
import HomePage from "./pages/HomePage";
import MobileTabBar from "./components/MobileTabBar";
import PublicChatWidget from "./components/PublicChatWidget";
import { SiteContentProvider, useSiteContentVersion } from "./SiteContentProvider";

// فاز ۷۶ (v0.59.0) - تقسیم کد (code-splitting): هر صفحه در chunk جداگانه
// ساخته می‌شود تا حجم بار اول در موبایل به‌شدت کم شود و ورود به سایت سریع‌تر باشد.
const BookingPage = lazy(() => import("./pages/BookingPage"));
const BookingResultPage = lazy(() => import("./pages/BookingResultPage"));
const ClinicsPage = lazy(() => import("./pages/ClinicsPage"));
const PsychotherapyPage = lazy(() => import("./pages/PsychotherapyPage"));
const SpecialistPage = lazy(() => import("./pages/SpecialistPage"));
const PaymentRulesPage = lazy(() => import("./pages/PaymentRulesPage"));
// فاز ۸۶ - آکادمی رز: ویترین فروش دوره + سبد خرید + درگاه بانکی + پخش ویدیو
const AcademyPage = lazy(() => import("./pages/AcademyPage"));
const AcademyCoursePage = lazy(() => import("./pages/AcademyCoursePage"));
const AcademyCartPage = lazy(() => import("./pages/AcademyCartPage"));
const AcademyPayResultPage = lazy(() => import("./pages/AcademyPayResultPage"));
const AcademyMyPage = lazy(() => import("./pages/AcademyMyPage"));

function PageFallback() {
  return (
    <Box sx={{ display: "flex", justifyContent: "center", py: 14 }} role="status" aria-label="در حال بارگذاری صفحه">
      <CircularProgress sx={{ color: "primary.main" }} />
    </Box>
  );
}

export default function App() {
  return (
    // فاز ۸۴ — محتوای ویرایش‌شدهٔ ادمین (ویرایشگر صفحات عمومی) بعد از اولین
    // رندر واکشی و در جا اعمال می‌شود؛ Provider فقط در صورت تغییرِ واقعی،
    // درخت را دوباره رندر می‌کند (بدون فلش، بدون remount).
    <SiteContentProvider>
      <SiteShell />
    </SiteContentProvider>
  );
}

function SiteShell() {
  const location = useLocation();
  // اشتراک در نسخهٔ محتوا: با bump شدن نسخه، این کامپوننت و کل درخت زیرین
  // دوباره رندر می‌شوند و متن‌های جدید از همان اشیاء ماژول خوانده می‌شود.
  useSiteContentVersion();

  // فاز ۷۹ - اسکرول به بخش‌ها برای لینک‌های # (مثل «خدمات» تب‌بار موبایل /#services).
  // چون صفحات lazy هستند، چند بار تلاش می‌کنیم تا المان بعد از لود چانک پیدا شود.
  useEffect(() => {
    if (!location.hash) return;
    let tries = 0;
    const iv = setInterval(() => {
      const el = document.getElementById(location.hash.slice(1));
      tries++;
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
        clearInterval(iv);
      } else if (tries > 20) {
        clearInterval(iv);
      }
    }, 120);
    return () => clearInterval(iv);
  }, [location]);

  return (
    <>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/booking" element={<BookingPage />} />
          {/* فاز ۶۹ - پروفایل متخصص با تقویم نوبت + پرداخت آنلاین + نظرات */}
          <Route path="/specialist/:id" element={<SpecialistPage />} />
          <Route path="/booking/result" element={<BookingResultPage />} />
          <Route path="/clinics" element={<ClinicsPage />} />
          <Route path="/services/psychotherapy" element={<PsychotherapyPage />} />
          {/* فاز ۷۶ - قوانین پرداخت و استرداد وجه */}
          <Route path="/payment-rules" element={<PaymentRulesPage />} />
          {/* فاز ۸۶ - آکادمی رز */}
          <Route path="/academy" element={<AcademyPage />} />
          <Route path="/academy/c/:slug" element={<AcademyCoursePage />} />
          <Route path="/academy/cart" element={<AcademyCartPage />} />
          <Route path="/academy/pay/result" element={<AcademyPayResultPage />} />
          <Route path="/academy/my" element={<AcademyMyPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      {/* فاز ۷۹ - فضای خالی زیر تب‌بار موبایل تا فوتر زیر آن نرود */}
      <Box
        aria-hidden
        sx={{ display: { xs: "block", lg: "none" }, height: "calc(86px + env(safe-area-inset-bottom))" }}
      />
      {/* فاز ۷۹ - نوار ناوبری اپی موبایل (PWA) */}
      <MobileTabBar />
      {/* فاز ۵۴ - چت آنلاین عمومی روی همهٔ صفحات سایت */}
      <PublicChatWidget />
    </>
  );
}
