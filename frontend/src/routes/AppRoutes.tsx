import { Navigate, Route, Routes } from "react-router-dom";
import { CircularProgress } from "@mui/material";
import Layout from "../components/Layout";
import { useAuth } from "../auth/AuthContext";
import ActivatePage from "../pages/ActivatePage";
import ApplicantsPage from "../pages/ApplicantsPage";
import AssessmentFormPage from "../pages/AssessmentFormPage";
import AuditEventsPage from "../pages/AuditEventsPage";
import CaseDetailPage from "../pages/CaseDetailPage";
import CasesPage from "../pages/CasesPage";
import ChangePasswordPage from "../pages/ChangePasswordPage";
import ConsultationRequestsPage from "../pages/ConsultationRequestsPage";
import CounselorWorklistPage from "../pages/CounselorWorklistPage";
import CounselorsPage from "../pages/CounselorsPage";
import DashboardPage from "../pages/DashboardPage";
import ImportsPage from "../pages/ImportsPage";
import LoginPage from "../pages/LoginPage";
import MyAssessmentsPage from "../pages/MyAssessmentsPage";
import MyPanelPage from "../pages/MyPanelPage";
import ReviewsPage from "../pages/ReviewsPage";
import SupervisorCasesPage from "../pages/SupervisorCasesPage";
import UsersPage from "../pages/UsersPage";
import ProtectedRoute from "./ProtectedRoute";

const CASE_ROLES = ["ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR"];
const STAFF_ROLES = ["ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR"];
const CLINICAL_ROLES = ["COUNSELOR", "TECHNICAL_SUPERVISOR"];

function RoleRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <CircularProgress sx={{ mx: "auto", display: "block", mt: 10 }} />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.roles.includes("APPLICANT")) return <Navigate to="/me" replace />;
  return <Navigate to="/dashboard" replace />;
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/activate" element={<ActivatePage />} />
      <Route path="/" element={<RoleRedirect />} />
      <Route path="/change-password" element={<ProtectedRoute><Layout><ChangePasswordPage /></Layout></ProtectedRoute>} />
      <Route path="/dashboard" element={
        <ProtectedRoute roles={STAFF_ROLES}><Layout><DashboardPage /></Layout></ProtectedRoute>
      } />
      <Route path="/audit-events" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN"]}><Layout><AuditEventsPage /></Layout></ProtectedRoute>
      } />
      <Route path="/users" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN"]}><Layout><UsersPage /></Layout></ProtectedRoute>
      } />
      <Route path="/counselors" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR"]}>
          <Layout><CounselorsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/applicants" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION"]}>
          <Layout><ApplicantsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/imports" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION"]}>
          <Layout><ImportsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/consultation-requests" element={
        <ProtectedRoute roles={["ORG_MANAGER", "RECEPTION"]}>
          <Layout><ConsultationRequestsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/cases" element={
        <ProtectedRoute roles={CASE_ROLES}><Layout><CasesPage /></Layout></ProtectedRoute>
      } />
      <Route path="/cases/:id" element={
        <ProtectedRoute roles={CASE_ROLES}><Layout><CaseDetailPage /></Layout></ProtectedRoute>
      } />
      <Route path="/cases/:caseId/assessments/new" element={
        <ProtectedRoute roles={CLINICAL_ROLES}><Layout><AssessmentFormPage /></Layout></ProtectedRoute>
      } />
      <Route path="/assessments/:id" element={
        <ProtectedRoute roles={CLINICAL_ROLES}><Layout><AssessmentFormPage /></Layout></ProtectedRoute>
      } />
      <Route path="/reviews" element={
        <ProtectedRoute roles={["TECHNICAL_SUPERVISOR"]}><Layout><ReviewsPage /></Layout></ProtectedRoute>
      } />
      <Route path="/supervised-cases" element={
        <ProtectedRoute roles={["TECHNICAL_SUPERVISOR"]}><Layout><SupervisorCasesPage /></Layout></ProtectedRoute>
      } />
      <Route path="/my-assessments" element={
        <ProtectedRoute roles={["COUNSELOR"]}><Layout><MyAssessmentsPage /></Layout></ProtectedRoute>
      } />
      <Route path="/worklist" element={
        <ProtectedRoute roles={["COUNSELOR"]}><Layout><CounselorWorklistPage /></Layout></ProtectedRoute>
      } />
      <Route path="/me" element={
        <ProtectedRoute roles={["APPLICANT"]}><Layout><MyPanelPage /></Layout></ProtectedRoute>
      } />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
