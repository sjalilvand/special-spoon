import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Box, CircularProgress } from "@mui/material";
import HomePage from "./pages/HomePage";
import PublicChatWidget from "./components/PublicChatWidget";

// فاز ۷۶ (v0.59.0) - تقسیم کد (code-splitting): هر صفحه در chunk جداگانه
// ساخته می‌شود تا حجم بار اول در موبایل به‌شدت کم شود و ورود به سایت سریع‌تر باشد.
const BookingPage = lazy(() => import("./pages/BookingPage"));
const BookingResultPage = lazy(() => import("./pages/BookingResultPage"));
const ClinicsPage = lazy(() => import("./pages/ClinicsPage"));
const PsychotherapyPage = lazy(() => import("./pages/PsychotherapyPage"));
const SpecialistPage = lazy(() => import("./pages/SpecialistPage"));
const PaymentRulesPage = lazy(() => import("./pages/PaymentRulesPage"));

function PageFallback() {
  return (
    <Box sx={{ display: "flex", justifyContent: "center", py: 14 }} role="status" aria-label="در حال بارگذاری صفحه">
      <CircularProgress sx={{ color: "primary.main" }} />
    </Box>
  );
}

export default function App() {
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
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      {/* فاز ۵۴ - چت آنلاین عمومی روی همهٔ صفحات سایت */}
      <PublicChatWidget />
    </>
  );
}
