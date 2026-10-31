import { Navigate, Route, Routes } from "react-router-dom";
import BookingPage from "./pages/BookingPage";
import ClinicsPage from "./pages/ClinicsPage";
import HomePage from "./pages/HomePage";
import PsychotherapyPage from "./pages/PsychotherapyPage";
import PublicChatWidget from "./components/PublicChatWidget";

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/booking" element={<BookingPage />} />
        <Route path="/clinics" element={<ClinicsPage />} />
        <Route path="/services/psychotherapy" element={<PsychotherapyPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      {/* فاز ۵۴ - چت آنلاین عمومی روی همهٔ صفحات سایت */}
      <PublicChatWidget />
    </>
  );
}