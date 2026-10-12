import { Navigate, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import PsychotherapyPage from "./pages/PsychotherapyPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/services/psychotherapy" element={<PsychotherapyPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
