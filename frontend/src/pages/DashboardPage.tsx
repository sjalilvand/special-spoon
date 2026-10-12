import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Grid,
  Paper, Stack, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import { CASE_STATUS_META, CONSENT_META, PRIORITY_LABELS } from "../api/cases";
import { fetchCounselorOptions } from "../api/cases";
import { APPOINTMENT_STATUS_META } from "../api/schedule";
import { fetchReportSummary } from "../api/reports";
import type { ReportSummary } from "../api/reports";

const WORKFLOW = [
  { step: "۱", title: "ثبت متقاضی", desc: "ثبت دستی یا ورود اکسل از صفحه «متقاضیان»", link: "/applicants", linkLabel: "متقاضیان" },
  { step: "۲", title: "تشکیل پرونده", desc: "از صفحه «پرونده‌ها» با انتخاب متقاضی و اولویت", link: "/cases", linkLabel: "پرونده‌ها" },
  { step: "۳", title: "تخصیص مشاور", desc: "مشاور اصلی یا همکار پرونده، از جزئیات پرونده", link: "/cases", linkLabel: "پرونده‌ها" },
  { step: "۴", title: "ثبت رضایت", desc: "از جزئیات پرونده — پیش‌نیاز شروع خدمت", link: "/cases", linkLabel: "پرونده‌ها" },
  { step: "۵", title: "ارزیابی RS-PS-04-01", desc: "فرم بالینی نسخه‌دار توسط مشاور تخصیص‌یافته", link: "/cases", linkLabel: "پرونده‌ها" },
  { step: "۶", title: "نوبت و جلسات", desc: "نوبت‌دهی، ثبت جلسه و یادداشت نسخه‌دار", link: "/cases", linkLabel: "پرونده‌ها" },
  { step: "۷", title: "نظارت فنی", desc: "تأیید یا برگشت ارزیابی توسط مسئول فنی", link: "/reviews", linkLabel: "بررسی‌های فنی" },
  { step: "۸", title: "پیگیری و خاتمه", desc: "ارجاع در صورت نیاز و بستن پرونده با علت", link: "/cases", linkLabel: "پرونده‌ها" },
];

function StatCard({ label, value, color = "primary.main" }: { label: string; value: number; color?: string }) {
  return (
    <Card variant="outlined" sx={{ height: "100%" }}>
      <CardContent sx={{ py: 2 }}>
        <Typography variant="caption" color="text.secondary" display="block">
          {label}
        </Typography>
        <Typography variant="h4" fontWeight={800} sx={{ color }}>
          {value.toLocaleString("fa-IR")}
        </Typography>
      </CardContent>
    </Card>
  );
}

function QuickLink({ to, label, desc }: { to: string; label: string; desc: string }) {
  const navigate = useNavigate();
  return (
    <Paper
      className="hover-lift"
      elevation={2}
      onClick={() => navigate(to)}
      sx={{ p: 2, cursor: "pointer", borderRadius: 3, border: "1px solid #ede7f6" }}
    >
      <Typography variant="subtitle2" fontWeight={800} color="primary.main">
        {label} ←
      </Typography>
      <Typography variant="caption" color="text.secondary">{desc}</Typography>
    </Paper>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const roles = user?.roles ?? [];
  const canFilterCounselor =
    roles.includes("ORG_MANAGER") || roles.includes("TECHNICAL_SUPERVISOR");

  const [days, setDays] = useState(30);
  const [counselorId, setCounselorId] = useState("");

  const { data: counselors } = useQuery({
    queryKey: ["counselor-options"],
    queryFn: fetchCounselorOptions,
    enabled: canFilterCounselor,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["report-summary", days, counselorId],
    queryFn: () => fetchReportSummary({ days, counselor_id: counselorId || undefined }),
  });

  const isStaff = data?.view === "staff";
  const caseEntries = Object.entries(data?.cases_by_status ?? {}).filter(([, n]) => n > 0);
  const apptEntries = Object.entries(data?.appointments_by_status ?? {}).filter(([, n]) => n > 0);

  return (
    <Stack spacing={3}>
      {/* کارت خوش‌آمد */}
      <Paper sx={{ p: 3, borderRadius: 3, background: "linear-gradient(135deg,#5b4b8a 0%,#4a3d73 100%)", color: "#fff" }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
          <Box>
            <Typography variant="h5" fontWeight={800}>
              خوش آمدید، {user?.display_name}
            </Typography>
            <Typography variant="body2" sx={{ opacity: 0.85, mt: 0.5 }}>
              نمای کلی سامانه در بازه انتخابی — {user?.roles.includes("COUNSELOR") ? "نمای عملکرد خودتان" : "نمای سازمانی"}
            </Typography>
          </Box>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {user?.roles.map((r) => (
              <Chip key={r} size="small" sx={{ bgcolor: "rgba(255,255,255,.2)", color: "#fff" }} label={r} />
            ))}
          </Stack>
        </Stack>
      </Paper>

      {/* فیلترها */}
      <Box display="flex" gap={2} flexWrap="wrap" alignItems="center">
        <Typography variant="subtitle2" color="text.secondary">بازه گزارش:</Typography>
        {[7, 30, 90, 365].map((d) => (
          <Chip
            key={d}
            label={d === 365 ? "یک سال" : `${d.toLocaleString("fa-IR")} روز`}
            color={days === d ? "primary" : "default"}
            variant={days === d ? "filled" : "outlined"}
            onClick={() => setDays(d)}
          />
        ))}
        {canFilterCounselor && (
          <Box sx={{ minWidth: 220 }}>
            <Select
              size="small"
              fullWidth
              value={counselorId}
              displayEmpty
              onChange={(e) => setCounselorId(e.target.value)}
            >
              <MenuItem value="">همه مشاوران</MenuItem>
              {counselors?.items.map((o) => (
                <MenuItem key={o.id} value={o.id}>{o.label}</MenuItem>
              ))}
            </Select>
          </Box>
        )}
      </Box>

      {error && <Alert severity="error">{errDetail(error)}</Alert>}
      {isLoading && <CircularProgress size={28} sx={{ mx: "auto", display: "block" }} />}

      {data && (
        <>
          {/* کارت‌های آماری */}
          <Grid container spacing={2}>
            {isStaff && (
              <>
                <Grid item xs={6} md={3}><StatCard label="متقاضیان" value={data.applicants_total} /></Grid>
                <Grid item xs={6} md={3}><StatCard label="حساب‌های فعال" value={data.users_active} color="info.main" /></Grid>
                <Grid item xs={6} md={3}><StatCard label="مشاوران فعال" value={data.counselors_active} color="secondary.main" /></Grid>
                <Grid item xs={6} md={3}><StatCard label="منتظر تخصیص" value={data.cases_by_status["awaiting_assignment"] ?? 0} color="warning.main" /></Grid>
              </>
            )}
            <Grid item xs={6} md={3}><StatCard label="نوبت‌های انجام‌شده" value={data.appointments_by_status["done"] ?? 0} /></Grid>
            <Grid item xs={6} md={3}>
              <StatCard label="لغو / عدم حضور"
                value={(data.appointments_by_status["cancelled"] ?? 0) + (data.appointments_by_status["no_show"] ?? 0)}
                color="error.main" />
            </Grid>
            <Grid item xs={6} md={3}><StatCard label="جلسات انجام‌شده" value={data.sessions_count} /></Grid>
            <Grid item xs={6} md={3}><StatCard label="ارزیابی‌های منتظر بررسی" value={data.assessments_pending_review} color="warning.main" /></Grid>
          </Grid>

          {/* وضعیت پرونده‌ها و نوبت‌ها */}
          <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "1fr 1fr" }} gap={2}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" fontWeight={700} mb={1.5}>وضعیت پرونده‌ها</Typography>
              {caseEntries.length === 0 && (
                <Typography variant="body2" color="text.secondary">پرونده‌ای وجود ندارد.</Typography>
              )}
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {caseEntries.map(([status, n]) => {
                  const m = CASE_STATUS_META[status] ?? { label: status, color: "default" as const };
                  return <Chip key={status} color={m.color} label={`${m.label}: ${n.toLocaleString("fa-IR")}`} />;
                })}
              </Stack>
              <Typography variant="caption" color="text.secondary" display="block" mt={1.5}>
                رضایت‌نامه‌ها: {Object.entries(data.appointments_by_status).length > 0 || isStaff
                  ? "از جزئیات هر پرونده قابل مشاهده است"
                  : "—"}
              </Typography>
            </Paper>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" fontWeight={700} mb={1.5}>وضعیت نوبت‌ها (بازه)</Typography>
              {apptEntries.length === 0 && (
                <Typography variant="body2" color="text.secondary">نوبتی در این بازه ثبت نشده است.</Typography>
              )}
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {apptEntries.map(([status, n]) => {
                  const m = APPOINTMENT_STATUS_META[status] ?? { label: status, color: "default" as const };
                  return <Chip key={status} color={m.color} label={`${m.label}: ${n.toLocaleString("fa-IR")}`} />;
                })}
              </Stack>
            </Paper>
          </Box>

          {/* حجم کار مشاوران */}
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={700} mb={1.5}>حجم کار مشاوران</Typography>
            {data.counselor_workload.length === 0 && (
              <Typography variant="body2" color="text.secondary">موردی وجود ندارد.</Typography>
            )}
            <Stack spacing={1.5}>
              {data.counselor_workload.map((row) => {
                const max = Math.max(...data.counselor_workload.map((r) => r.active_cases), 1);
                return (
                  <Box key={row.counselor_id}>
                    <Stack direction="row" justifyContent="space-between" mb={0.5}>
                      <Typography variant="body2" fontWeight={700}>{row.counselor_name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {row.active_cases.toLocaleString("fa-IR")} پرونده فعال — {row.sessions_count.toLocaleString("fa-IR")} جلسه
                      </Typography>
                    </Stack>
                    <Box sx={{ bgcolor: "#ede7f6", borderRadius: 99, height: 8 }}>
                      <Box sx={{
                        width: `${(row.active_cases / max) * 100}%`,
                        bgcolor: "primary.main", borderRadius: 99, height: 8,
                        transition: "width .4s",
                      }} />
                    </Box>
                  </Box>
                );
              })}
            </Stack>
          </Paper>

          {/* ورودهای اکسل اخیر */}
          {isStaff && data.recent_imports.length > 0 && (
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>نتیجه ورودهای اکسل (۵ مورد اخیر)</Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {data.recent_imports.map((row, idx) => (
                  <Chip key={idx}
                    color={row.error_rows > 0 ? "warning" : "success"}
                    variant="outlined"
                    label={`${row.import_type}: ${row.created_rows.toLocaleString("fa-IR")} ایجاد / ${row.error_rows.toLocaleString("fa-IR")} خطا`} />
                ))}
              </Stack>
            </Paper>
          )}

          <Alert severity="info">
            گزارش‌ها تجمیعی است؛ فهرست تشخیص افراد یا متن درمان در گزارش مدیریتی ارائه نمی‌شود (بند ۱۵).
          </Alert>
        </>
      )}

      {/* لینک‌های سریع */}
      <Box>
        <Typography variant="subtitle1" fontWeight={700} mb={1.5}>دسترسی سریع</Typography>
        <Box display="grid" gridTemplateColumns={{ xs: "1fr 1fr", md: "repeat(4, 1fr)" }} gap={2}>
          {(roles.includes("ORG_MANAGER") || roles.includes("RECEPTION") || roles.includes("SYSTEM_ADMIN")) && (
            <>
              <QuickLink to="/applicants" label="متقاضیان" desc="ثبت و جست‌وجوی متقاضیان خدمات" />
              <QuickLink to="/imports" label="ورود اکسل" desc="ورود گروهی متقاضیان، مشاوران، کاربران" />
            </>
          )}
          {roles.includes("ORG_MANAGER") && (
            <QuickLink to="/consultation-requests" label="درخواست‌های سایت" desc="پیگیری و تبدیل درخواست‌های عمومی" />
          )}
          {roles.includes("COUNSELOR") && (
            <QuickLink to="/worklist" label="کارتابل من" desc="نوبت‌های امروز و آینده" />
          )}
          {roles.includes("TECHNICAL_SUPERVISOR") && (
            <QuickLink to="/reviews" label="بررسی‌های فنی" desc="ارزیابی‌های منتظر تأیید" />
          )}
          {roles.includes("ORG_MANAGER", ) === false && null}
        </Box>
      </Box>

      {/* راهنمای گردش‌کار */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="subtitle1" fontWeight={700} mb={2}>
          راهنمای گردش‌کار سامانه (بند ۷ سند)
        </Typography>
        <Box display="grid" gridTemplateColumns={{ xs: "1fr", sm: "1fr 1fr", md: "1fr 1fr 1fr 1fr" }} gap={2}>
          {WORKFLOW.map((w) => (
            <Paper key={w.step} variant="outlined" sx={{ p: 2, borderRadius: 3 }}>
              <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
                <Box sx={{
                  width: 28, height: 28, borderRadius: "50%", bgcolor: "primary.main",
                  color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
                  fontWeight: 800, fontSize: 14,
                }}>
                  {w.step}
                </Box>
                <Typography variant="subtitle2" fontWeight={700}>{w.title}</Typography>
              </Stack>
              <Typography variant="caption" color="text.secondary" display="block" mb={1}>
                {w.desc}
              </Typography>
              <Button size="small" onClick={() => window.location.assign(w.link)}>
                {w.linkLabel} ←
              </Button>
            </Paper>
          ))}
        </Box>
      </Paper>
    </Stack>
  );
}
