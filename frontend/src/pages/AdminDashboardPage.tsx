import {
  Alert, Box, Card, CardContent, Chip, CircularProgress, Grid,
  Paper, Stack, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { errDetail } from "../api/client";
import { CASE_STATUS_META } from "../api/cases";
import { fetchAdminDashboard } from "../api/reports";
import { ChartCard, DonutChart, TrendChart } from "../components/charts";
import { formatJalaliDateTime } from "../utils/jalali";

// فاز ۲۶ + ۴۸ - B24 سند جامع: داشبورد مدیر (KPI شفاف، روند، عملکرد مشاوران، نمودارهای تحلیلی)

const STATUS_HEX: Record<string, string> = {
  success: "#2e7d32", error: "#c62828", warning: "#ed8c37", info: "#1565c0",
  primary: "#b04a5a", secondary: "#7a5c8a", default: "#9e8f93",
};

const CONSULT_STATUS_META: Record<string, { label: string; color: "default" | "primary" | "success" | "warning" | "error" | "info" }> = {
  new: { label: "جدید", color: "info" },
  in_review: { label: "در حال بررسی", color: "warning" },
  converted: { label: "تبدیل به پرونده", color: "success" },
  archived: { label: "بایگانی", color: "default" },
};

function StatCard({ label, value, color = "primary.main", suffix = "" }: {
  label: string; value: number | string; color?: string; suffix?: string;
}) {
  return (
    <Card variant="outlined" sx={{ height: "100%" }}>
      <CardContent sx={{ py: 2 }}>
        <Typography variant="caption" color="text.secondary" display="block">
          {label}
        </Typography>
        <Typography variant="h4" fontWeight={800} sx={{ color }}>
          {typeof value === "number" ? value.toLocaleString("fa-IR") : value}{suffix}
        </Typography>
      </CardContent>
    </Card>
  );
}

export default function AdminDashboardPage() {
  const [days, setDays] = useState(30);
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-dashboard", days],
    queryFn: () => fetchAdminDashboard(days),
  });

  const k = data?.kpis;
  const caseEntries = Object.entries(k?.cases_by_status ?? {}).filter(([, n]) => n > 0);
  const consultEntries = Object.entries(k?.consultations_by_status ?? {});

  return (
    <Stack spacing={3}>
      <Paper sx={{ p: 3, borderRadius: 3, background: "linear-gradient(135deg,#3f51b5 0%,#303f9f 100%)", color: "#fff" }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
          <Box>
            <Typography variant="h5" fontWeight={800}>داشبورد مدیر</Typography>
            <Typography variant="body2" sx={{ opacity: 0.85, mt: 0.5 }}>
              شاخص‌های کلیدی عملکرد، روند پرونده و رزرو — B24 سند جامع (تجمیعی و بی‌نام، بند ۱۵)
            </Typography>
          </Box>
          {data && (
            <Typography variant="caption" sx={{ opacity: 0.8 }}>
              به‌روزرسانی: {formatJalaliDateTime(data.generated_at)}
            </Typography>
          )}
        </Stack>
      </Paper>

      <Box display="flex" gap={1.5} alignItems="center" flexWrap="wrap" role="group" aria-label="بازه زمانی داشبورد">
        <Typography variant="subtitle2" color="text.secondary">بازه:</Typography>
        {[7, 30, 90, 365].map((d) => (
          <Chip
            key={d}
            label={d === 365 ? "یک سال" : `${d.toLocaleString("fa-IR")} روز`}
            color={days === d ? "primary" : "default"}
            variant={days === d ? "filled" : "outlined"}
            onClick={() => setDays(d)}
            aria-pressed={days === d}
          />
        ))}
      </Box>

      {error && <Alert severity="error">{errDetail(error)}</Alert>}
      {isLoading && <CircularProgress size={28} sx={{ mx: "auto", display: "block" }} aria-label="در حال بارگذاری داشبورد" />}

      {data && k && (
        <>
          <Grid container spacing={2}>
            <Grid item xs={6} md={3}><StatCard label="کل پرونده‌ها" value={k.cases_total} /></Grid>
            <Grid item xs={6} md={3}>
              <StatCard label="پرونده فعال" value={k.cases_by_status["active"] ?? 0} color="secondary.main" />
            </Grid>
            <Grid item xs={6} md={3}>
              <StatCard label="منتظر بررسی فنی" value={k.assessments_pending_review} color="warning.main" />
            </Grid>
            <Grid item xs={6} md={3}>
              <StatCard label="میانگین زمان بررسی" value={k.avg_review_hours ?? "—"} suffix={k.avg_review_hours ? " ساعت" : ""} color="info.main" />
            </Grid>
            <Grid item xs={6} md={3}><StatCard label="متقاضیان" value={k.applicants_total} /></Grid>
            <Grid item xs={6} md={3}><StatCard label="کاربران فعال" value={k.users_active} /></Grid>
            <Grid item xs={6} md={3}><StatCard label="مشاوران فعال" value={k.counselors_active} /></Grid>
            <Grid item xs={6} md={3}><StatCard label="جلسات انجام‌شده (بازه)" value={k.sessions_count} /></Grid>
          </Grid>

          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <ChartCard title="روند پرونده‌های جدید" accent="#b04a5a">
                <TrendChart data={data.trends.cases} color="#b04a5a" />
              </ChartCard>
            </Grid>
            <Grid item xs={12} md={4}>
              <ChartCard title="روند درخواست‌های رزرو از سایت" accent="#2e7d32">
                <TrendChart data={data.trends.bookings} color="#2e7d32" />
              </ChartCard>
            </Grid>
            <Grid item xs={12} md={4}>
              <ChartCard title="روند جلسات انجام‌شده" accent="#1565c0">
                <TrendChart data={data.trends.sessions ?? []} color="#1565c0" />
              </ChartCard>
            </Grid>
          </Grid>

          <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "1fr 1fr" }} gap={2}>
            <ChartCard title="توزیع وضعیت پرونده‌ها" accent="#b04a5a">
              <DonutChart
                title="پرونده"
                items={caseEntries.map(([status, n]) => ({
                  label: CASE_STATUS_META[status]?.label ?? status,
                  value: n,
                  color: STATUS_HEX[CASE_STATUS_META[status]?.color as string] ?? "#9e8f93",
                }))}
              />
              {caseEntries.length === 0 && (
                <Typography variant="body2" color="text.secondary">پرونده‌ای وجود ندارد.</Typography>
              )}
            </ChartCard>
            <ChartCard title="توزیع وضعیت درخواست‌های سایت (بازه)" accent="#7a5c8a">
              <DonutChart
                title="درخواست"
                items={consultEntries.map(([status, n]) => ({
                  label: CONSULT_STATUS_META[status]?.label ?? status,
                  value: n,
                  color: STATUS_HEX[CONSULT_STATUS_META[status]?.color as string] ?? "#9e8f93",
                }))}
              />
            </ChartCard>
          </Box>

          <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "1fr 1fr" }} gap={2}>
            <Paper sx={{ p: 2 }} aria-label="وضعیت رزرو آنلاین">
              <Typography variant="subtitle1" fontWeight={700} mb={1.5}>رزرو آنلاین (بازه)</Typography>
              <Grid container spacing={1.5}>
                <Grid item xs={6}><StatCard label="درخواست‌های دریافتی" value={k.consultations_total} /></Grid>
                <Grid item xs={6}><StatCard label="با انتخاب نوبت آنلاین" value={k.consultations_with_slot} color="secondary.main" /></Grid>
                <Grid item xs={6}><StatCard label="نگهداشت فعال الان" value={k.booking_active_holds} color="info.main" /></Grid>
                <Grid item xs={6}><StatCard label="نگهداشت تأییدشده (بازه)" value={k.booking_confirmed_holds} /></Grid>
              </Grid>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap mt={2}>
                {consultEntries.map(([status, n]) => {
                  const m = CONSULT_STATUS_META[status] ?? { label: status, color: "default" as const };
                  return <Chip key={status} color={m.color} label={`${m.label}: ${n.toLocaleString("fa-IR")}`} />;
                })}
              </Stack>
            </Paper>

            <Paper sx={{ p: 2 }} aria-label="نوبت‌ها و وضعیت پرونده">
              <Typography variant="subtitle1" fontWeight={700} mb={1.5}>نوبت‌ها (بازه)</Typography>
              <Grid container spacing={1.5}>
                <Grid item xs={6}><StatCard label="نوبت‌های ثبت‌شده" value={k.appointments_window} /></Grid>
                <Grid item xs={6}><StatCard label="انجام‌شده" value={k.appointments_done} color="success.main" /></Grid>
                <Grid item xs={6}><StatCard label="۷ روز آینده" value={k.appointments_upcoming_7d} color="info.main" /></Grid>
                <Grid item xs={6}>
                  <StatCard label="نرخ عدم حضور" value={k.no_show_rate} suffix="٪" color="error.main" />
                </Grid>
              </Grid>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap mt={2}>
                {caseEntries.map(([status, n]) => {
                  const m = CASE_STATUS_META[status] ?? { label: status, color: "default" as const };
                  return <Chip key={status} color={m.color} label={`${m.label}: ${n.toLocaleString("fa-IR")}`} />;
                })}
              </Stack>
            </Paper>

            <Paper sx={{ p: 2 }} aria-label="فروش (B10)">
              <Typography variant="subtitle1" fontWeight={700} mb={1.5}>فروش (بازه) — B10 پس از D02</Typography>
              <Grid container spacing={1.5}>
                <Grid item xs={6}>
                  <StatCard label="سفارش‌های پرداخت‌شده" value={k.sales_paid_orders} color="success.main" />
                </Grid>
                <Grid item xs={6}>
                  <StatCard label="جمع فروش (ریال)" value={Math.round(k.sales_paid_amount).toLocaleString("fa-IR")} color="primary.main" />
                </Grid>
                <Grid item xs={6}>
                  <StatCard label="در انتظار پرداخت" value={k.sales_pending_orders} color="warning.main" />
                </Grid>
                <Grid item xs={6}>
                  <StatCard label="میانگین سفارش (ریال)"
                    value={k.sales_paid_orders ? Math.round(k.sales_paid_amount / k.sales_paid_orders).toLocaleString("fa-IR") : "—"} />
                </Grid>
              </Grid>
              {k.finance && (
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap mt={2}>
                  <Chip size="small" color={k.finance.ledger_balanced ? "success" : "error"}
                    label={k.finance.ledger_balanced ? "دفتر متوازن (B22)" : "دفتر نامتوازن!"} />
                  <Chip size="small" color={k.finance.sales_reconciled ? "success" : "warning"}
                    label={k.finance.sales_reconciled
                      ? `فروش با دفتر تطبیق دارد (${Math.round(k.finance.sales_report_amount).toLocaleString("fa-IR")} ریال)`
                      : `مغایرت فروش/دفتر: ${Math.round(k.finance.sales_report_amount - k.finance.journal_revenue_amount).toLocaleString("fa-IR")} ریال`} />
                  <Chip size="small" color={k.finance.uncovered_events === 0 ? "success" : "error"}
                    label={k.finance.uncovered_events === 0 ? "همه رویدادهای مالی سند دارند" : `${k.finance.uncovered_events} رویداد بدون سند`} />
                </Stack>
              )}
            </Paper>
          </Box>

          <Paper sx={{ p: 2 }} aria-label="بار کاری مشاوران">
            <Typography variant="subtitle1" fontWeight={700} mb={1.5}>عملکرد مشاوران</Typography>
            {data.counselor_workload.length === 0 && (
              <Typography variant="body2" color="text.secondary">مشاوری فعال وجود ندارد.</Typography>
            )}
            <Stack spacing={1.5}>
              {data.counselor_workload.map((row) => {
                const max = Math.max(...data.counselor_workload.map((r) => r.active_cases), 1);
                return (
                  <Box key={row.counselor_id}>
                    <Stack direction="row" justifyContent="space-between" mb={0.5}>
                      <Typography variant="body2" fontWeight={700}>{row.counselor_name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {row.active_cases.toLocaleString("fa-IR")} پرونده فعال — {row.sessions_count.toLocaleString("fa-IR")} جلسه در بازه
                      </Typography>
                    </Stack>
                    <Box sx={{ bgcolor: "#ede7f6", borderRadius: 99, height: 8 }} role="img"
                      aria-label={`${row.counselor_name}: ${row.active_cases} پرونده فعال`}>
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

          <Alert severity="info">
            همه شاخص‌ها تجمیعی است و هیچ محتوای بالینی فردی در داشبورد نمایش داده نمی‌شود (بند ۱۵ سند).
          </Alert>
        </>
      )}
    </Stack>
  );
}
