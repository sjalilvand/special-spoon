import { Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Box, CircularProgress } from "@mui/material";
import Layout from "../components/Layout";
import GlobalErrorBoundary from "../components/GlobalErrorBoundary";
import { useAuth } from "../auth/AuthContext";
import ProtectedRoute from "./ProtectedRoute";
import { lazyRetry } from "../utils/lazyRetry";

// فاز ۷۷ — تقسیم کد در سطح مسیر (Route-level code splitting):
// پیش از این، کد هر ۵۰+ صفحه در یک chunk واحد (~۱٫۱ مگابایت) بارگذاری می‌شد و
// در موبایل/اینترنت کند، ورود به پنل بسیار کند بود. اکنون هر صفحه فقط هنگام
// ورود به همان مسیر دانلود می‌شود، در کش مرورگر (Cache-Control immutable)
// می‌ماند و ورود اولیه چند برابر سریع‌تر است.
// LoginPage عمداً eager می‌ماند تا اولین رنگ‌آمیزی صفحهٔ ورود بدون انتظار اضافه باشد.
import LoginPage from "../pages/LoginPage";

const ActivatePage = lazyRetry(() => import("../pages/ActivatePage"));
const AccountingPage = lazyRetry(() => import("../pages/AccountingPage"));
const AdminDashboardPage = lazyRetry(() => import("../pages/AdminDashboardPage"));
const ApplicantsPage = lazyRetry(() => import("../pages/ApplicantsPage"));
const AssessmentFormPage = lazyRetry(() => import("../pages/AssessmentFormPage"));
const AuditEventsPage = lazyRetry(() => import("../pages/AuditEventsPage"));
const BranchMapPage = lazyRetry(() => import("../pages/BranchMapPage"));
const BranchesPage = lazyRetry(() => import("../pages/BranchesPage"));
const CaseDetailPage = lazyRetry(() => import("../pages/CaseDetailPage"));
const CasesPage = lazyRetry(() => import("../pages/CasesPage"));
const ChangePasswordPage = lazyRetry(() => import("../pages/ChangePasswordPage"));
const ConsultationRequestsPage = lazyRetry(() => import("../pages/ConsultationRequestsPage"));
const CounselorWorklistPage = lazyRetry(() => import("../pages/CounselorWorklistPage"));
const CounselorsPage = lazyRetry(() => import("../pages/CounselorsPage"));
const DashboardPage = lazyRetry(() => import("../pages/DashboardPage"));
const DpoReportPage = lazyRetry(() => import("../pages/DpoReportPage"));
const ImportsPage = lazyRetry(() => import("../pages/ImportsPage"));
const InvoicePage = lazyRetry(() => import("../pages/InvoicePage"));
const Level3AlertsPage = lazyRetry(() => import("../pages/Level3AlertsPage"));
const NotificationsPage = lazyRetry(() => import("../pages/NotificationsPage"));
const SupportPage = lazyRetry(() => import("../pages/SupportPage"));
const PsychTestCenterPage = lazyRetry(() => import("../pages/PsychTestCenterPage"));
const PsychAttemptsPage = lazyRetry(() => import("../pages/PsychAttemptsPage"));
const PsychTestBuilderPage = lazyRetry(() => import("../pages/PsychTestBuilderPage"));
const CounselingFilesPage = lazyRetry(() => import("../pages/CounselingFilesPage"));
const PsychTestRunPage = lazyRetry(() => import("../pages/PsychTestRunPage"));
const AssistantPage = lazyRetry(() => import("../pages/AssistantPage"));
const OrganizationsPage = lazyRetry(() => import("../pages/OrganizationsPage"));
const OrgProgramsPage = lazyRetry(() => import("../pages/OrgProgramsPage"));
const OrgProgramWorkdeskPage = lazyRetry(() => import("../pages/OrgProgramWorkdeskPage"));
const OrgExamResultsPage = lazyRetry(() => import("../pages/OrgExamResultsPage"));
const LearningPage = lazyRetry(() => import("../pages/LearningPage"));
const IntegrationsPage = lazyRetry(() => import("../pages/IntegrationsPage"));
const MyAssessmentsPage = lazyRetry(() => import("../pages/MyAssessmentsPage"));
const MyPanelPage = lazyRetry(() => import("../pages/MyPanelPage"));
const OrdersPage = lazyRetry(() => import("../pages/OrdersPage"));
const ProcessesPage = lazyRetry(() => import("../pages/ProcessesPage"));
const ProcessMonitoringPage = lazyRetry(() => import("../pages/ProcessMonitoringPage"));
const ReviewsPage = lazyRetry(() => import("../pages/ReviewsPage"));
const ReportBuilderPage = lazyRetry(() => import("../pages/ReportBuilderPage"));
const ServicesPage = lazyRetry(() => import("../pages/ServicesPage"));
const SupervisorCasesPage = lazyRetry(() => import("../pages/SupervisorCasesPage"));
const TopicsPage = lazyRetry(() => import("../pages/TopicsPage"));
const UsersPage = lazyRetry(() => import("../pages/UsersPage"));
const RolesPermissionsPage = lazyRetry(() => import("../pages/RolesPermissionsPage"));
const ChatPage = lazyRetry(() => import("../pages/ChatPage"));
const PublicChatsPage = lazyRetry(() => import("../pages/PublicChatsPage"));
// فاز ۶۱: فرم‌ساز و نظرسنجی + تماس تلفنی
const FormBuilderPage = lazyRetry(() => import("../pages/FormBuilderPage"));
const FormResponsesPage = lazyRetry(() => import("../pages/FormResponsesPage"));
const MyFormsPage = lazyRetry(() => import("../pages/MyFormsPage"));
const FormFillPage = lazyRetry(() => import("../pages/FormFillPage"));
const VerificationReviewsPage = lazyRetry(() => import("../pages/VerificationReviewsPage"));
const WalletPage = lazyRetry(() => import("../pages/WalletPage"));
const CartablePage = lazyRetry(() => import("../pages/CartablePage"));

const CASE_ROLES = ["ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR"];
const STAFF_ROLES = ["ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "SYSTEM_ADMIN"];
const CLINICAL_ROLES = ["COUNSELOR", "TECHNICAL_SUPERVISOR"];

/** فاز ۷۷: نشانگر بارگذاری هنگام دانلود chunk صفحهٔ جدید */
function PageFallback() {
  return (
    <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", mt: 12 }}>
      <CircularProgress />
    </Box>
  );
}

function RoleRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <CircularProgress sx={{ mx: "auto", display: "block", mt: 10 }} />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.roles.includes("APPLICANT")) return <Navigate to="/me" replace />;
  return <Navigate to="/dashboard" replace />;
}

export default function AppRoutes() {
  return (
    /* فاز ۵۱: مرز خطای سراسری — کرش رندر هر مسیر به‌جای صفحهٔ سفید، پیام فارسی دارد */
    <GlobalErrorBoundary>
    <Suspense fallback={<PageFallback />}>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/activate" element={<ActivatePage />} />
      {/* فاز ۳۲ - B40: نقشه شعب عمومی (بدون احراز هویت، مانند API عمومی) */}
      <Route path="/branch-map" element={<Layout><BranchMapPage /></Layout>} />
      <Route path="/" element={<RoleRedirect />} />
      <Route path="/change-password" element={<ProtectedRoute><Layout><ChangePasswordPage /></Layout></ProtectedRoute>} />
      <Route path="/dashboard" element={
        <ProtectedRoute roles={STAFF_ROLES}><Layout><DashboardPage /></Layout></ProtectedRoute>
      } />
      {/* فاز ۵۹: کارتابل شخصی هر حساب + نمای مدیریتی کارتابل کاربر */}
      <Route path="/cartable" element={
        <ProtectedRoute roles={STAFF_ROLES}><Layout><CartablePage /></Layout></ProtectedRoute>
      } />
      <Route path="/cartable/:userId" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN"]}><Layout><CartablePage /></Layout></ProtectedRoute>
      } />
      <Route path="/admin-dashboard" element={
        <ProtectedRoute roles={["ORG_MANAGER", "SYSTEM_ADMIN"]}><Layout><AdminDashboardPage /></Layout></ProtectedRoute>
      } />
      <Route path="/dpo-report" element={
        <ProtectedRoute roles={["ORG_MANAGER", "SYSTEM_ADMIN", "DPO"]}><Layout><DpoReportPage /></Layout></ProtectedRoute>
      } />
      {/* فاز ۷۶: گزارش‌ساز و داشبوردساز */}
      <Route path="/report-builder" element={
        <ProtectedRoute roles={["ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "SYSTEM_ADMIN", "DPO"]}><Layout><ReportBuilderPage /></Layout></ProtectedRoute>
      } />
      <Route path="/audit-events" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN"]}><Layout><AuditEventsPage /></Layout></ProtectedRoute>
      } />
      <Route path="/users" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN"]}><Layout><UsersPage /></Layout></ProtectedRoute>
      } />
      {/* فاز ۵۲: ماتریس نقش‌ها و دسترسی‌ها (گرافیکی) */}
      <Route path="/roles-permissions" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN"]}><Layout><RolesPermissionsPage /></Layout></ProtectedRoute>
      } />
      {/* فاز ۵۲: چت آنلاین و مشاوره — همهٔ حساب‌های فعال */}
      <Route path="/chat" element={
        <ProtectedRoute><Layout><ChatPage /></Layout></ProtectedRoute>
      } />
      {/* فاز ۵۵: پنل پذیرش/مدیر — گفتگوهای عمومی سایت و امتیازها */}
      <Route path="/public-chats" element={
        <ProtectedRoute roles={["ORG_MANAGER", "RECEPTION", "SYSTEM_ADMIN"]}>
          <Layout><PublicChatsPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۶۱: فرم‌ساز و نظرسنجی — ساخت/مدیریت فرم‌ها توسط مدیر */}
      <Route path="/form-builder" element={
        <ProtectedRoute roles={["ORG_MANAGER", "SYSTEM_ADMIN"]}>
          <Layout><FormBuilderPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/form-responses" element={
        <ProtectedRoute roles={["ORG_MANAGER", "SYSTEM_ADMIN"]}>
          <Layout><FormResponsesPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/form-responses/:templateId" element={
        <ProtectedRoute roles={["ORG_MANAGER", "SYSTEM_ADMIN"]}>
          <Layout><FormResponsesPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۶۱: فرم‌های من (نظرسنجی‌های در انتظار) + تکمیل فرم با لینک مستقیم */}
      <Route path="/my-forms" element={
        <ProtectedRoute><Layout><MyFormsPage /></Layout></ProtectedRoute>
      } />
      <Route path="/forms/:templateId/fill" element={
        <ProtectedRoute><Layout><FormFillPage /></Layout></ProtectedRoute>
      } />
      <Route path="/counselors" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR"]}>
          <Layout><CounselorsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/services" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR"]}>
          <Layout><ServicesPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۳۳ - B32: دسته‌بندی موضوعی */}
      <Route path="/topics" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR"]}>
          <Layout><TopicsPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۳۳ - B21: سازمان‌ها و قراردادها */}
      <Route path="/organizations" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR"]}>
          <Layout><OrganizationsPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۵۸ - پنل آزمون‌های سازمانی: فهرست برنامه‌ها + کارتابل */}
      <Route path="/org-programs" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "APPLICANT"]}>
          <Layout><OrgProgramsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/org-programs/:id" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "APPLICANT"]}>
          <Layout><OrgProgramWorkdeskPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۷۴ - آزمون‌های برگزارشده سازمانی: مدیر سازمان فقط سازمان خودش */}
      <Route path="/org-exam-results" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "APPLICANT"]}>
          <Layout><OrgExamResultsPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۳۴ - B33–B36: محتوا/دوره/آزمون/گواهی */}
      <Route path="/learning" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR"]}>
          <Layout><LearningPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۳۵ - B23: پشتیبانی */}
      <Route path="/support" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "APPLICANT"]}>
          <Layout><SupportPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۳۵ + ۴۷ - B37: مرکز آزمون روان‌شناسی (D08) — همه نقش‌ها می‌توانند آزمون بدهند */}
      <Route path="/psych-tests" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "COUNSELOR", "RECEPTION", "APPLICANT"]}>
          <Layout><PsychTestCenterPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۷۰ - آزمون‌های برگزارشده + پرونده‌های مشاوره کاربران */}
      <Route path="/psych-attempts" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "COUNSELOR", "RECEPTION"]}>
          <Layout><PsychAttemptsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/counseling-files" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "COUNSELOR", "RECEPTION"]}>
          <Layout><CounselingFilesPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/psych-tests/:slug/run" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "COUNSELOR", "RECEPTION", "APPLICANT"]}>
          <Layout><PsychTestRunPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۸۳ - فرم‌ساز گرافیکی ابزار آزمون (مدیر) + پیش‌نمایش قبل از اعمال */}
      <Route path="/psych-tests/:testId/builder" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER"]}>
          <Layout><PsychTestBuilderPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۸۳ج - لانچر فرم‌ساز (بدون شناسه): ورود از منوی «سامانه و پشتیبانی» —
          ابتدا ابزار انتخاب می‌شود، بعد ویرایشگر پنج‌تبی باز می‌شود.
          (React Router مسیر ایستا را بر :testId ترجیح می‌دهد — تداخلی نیست) */}
      <Route path="/psych-tests/builder" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER"]}>
          <Layout><PsychTestBuilderPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۳۵ - B25–B27: دستیار هوشمند (D07) */}
      <Route path="/assistant" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "APPLICANT"]}>
          <Layout><AssistantPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۳۶ - B28: یکپارچه‌سازی‌های بیرونی */}
      <Route path="/integrations" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER"]}>
          <Layout><IntegrationsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/verification-reviews" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR"]}>
          <Layout><VerificationReviewsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/branches" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR"]}>
          <Layout><BranchesPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/orders" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION"]}>
          <Layout><OrdersPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/invoices/:id" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR"]}>
          <Layout><InvoicePage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/wallet" element={
        <ProtectedRoute>
          <Layout><WalletPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/accounting" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER"]}>
          <Layout><AccountingPage /></Layout>
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
        <ProtectedRoute roles={["ORG_MANAGER", "RECEPTION", "SYSTEM_ADMIN", "COUNSELOR"]}>
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
      <Route path="/notifications" element={
        <ProtectedRoute><Layout><NotificationsPage /></Layout></ProtectedRoute>
      } />
      <Route path="/level3-alerts" element={
        <ProtectedRoute roles={["TECHNICAL_SUPERVISOR"]}><Layout><Level3AlertsPage /></Layout></ProtectedRoute>
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
      <Route path="/processes" element={
        <ProtectedRoute roles={STAFF_ROLES}><Layout><ProcessesPage /></Layout></ProtectedRoute>
      } />
      {/* فاز ۴۹ - B42: مانیتورینگ وضعیت درخواست در فرایند */}
      <Route path="/process-monitoring" element={
        <ProtectedRoute roles={STAFF_ROLES}><Layout><ProcessMonitoringPage /></Layout></ProtectedRoute>
      } />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </Suspense>
    </GlobalErrorBoundary>
  );
}
