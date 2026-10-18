import {
  Alert, Box, Card, CardContent, Chip, CircularProgress, Divider,
  Grid, Paper, Stack, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { errDetail } from "../api/client";
import { fetchDpoReport } from "../api/reports";
import { formatJalaliDateTime } from "../utils/jalali";

// فاز ۲۷ - B41+ سند جامع: گزارش انطباق رضایت/دسترسی برای حسابرس حفاظت داده (DPO)
// همه داده‌ها تجمیعی و بی‌نام هستند (بند ۱۵ سند)

const CONSENT_KIND_LABEL: Record<string, string> = {
  treatment: "درمان",
  psych_test: "آزمون روان‌شناختی",
  data_share: "اشتراک داده",
  marketing: "اطلاع‌رسانی/بازاریابی",
};

const SCAN_STATUS_META: Record<string, { label: string; color: "success" | "warning" | "error" | "default" }> = {
  clean: { label: "تمیز", color: "success" },
  pending: { label: "در انتظار اسکن", color: "default" },
  quarantined: { label: "قرنطینه", color: "error" },
  failed: { label: "اسکن ناموفق", color: "warning" },
};

const OUTBOX_STATUS_META: Record<string, { label: string; color: "success" | "warning" | "error" | "info" }> = {
  pending: { label: "در صف", color: "info" },
  sent: { label: "ارسال‌شده", color: "success" },
  failed: { label: "ناموفق", color: "error" },
  disabled: { label: "غیرفعال (SMTP)", color: "warning" },
};

const TRACKED_ACTION_LABEL: Record<string, string> = {
  "auth.login": "ورود موفق",
  "auth.login_failed": "ورود ناموفق",
  "auth.password_changed": "تغییر رمز",
  "assessment.viewed": "مشاهده ارزیابی",
  "assessment.printed": "چاپ ارزیابی",
  "file.upload": "آپلود فایل",
  "file.download_ticket": "صدور بلیت دانلود",
  "file.rescan": "اسکن مجدد فایل",
  "consent_version.published": "انتشار نسخه رضایت",
  "case.consent_recorded": "ثبت رضایت",
  "consent.revoked": "ابطال رضایت",
  "email.outbox_processed": "پردازش صف ایمیل",
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

function CountTable({ rows, emptyText }: {
  rows: { label: string; count: number; chip?: { label: string; color: string } }[];
  emptyText: string;
}) {
  if (rows.length === 0) {
    return <Typography variant="body2" color="text.secondary">{emptyText}</Typography>;
  }
  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>مورد</TableCell>
            <TableCell align="left">تعداد</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.label}>
              <TableCell>{r.label}</TableCell>
              <TableCell align="left">{r.count.toLocaleString("fa-IR")}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export default function DpoReportPage() {
  const [days, setDays] = useState(30);
  const { data, isLoading, error } = useQuery({
    queryKey: ["dpo-report", days],
    queryFn: () => fetchDpoReport(days),
  });

  const consentRows = Object.entries(data?.consents.by_kind ?? {}).map(([kind, v]) => ({
    label: CONSENT_KIND_LABEL[kind] ?? kind,
    active: v.granted_active,
    revoked: v.revoked,
  }));
  const actionRows = Object.entries(data?.access.actions_by_count ?? {}).map(([a, n]) => ({
    label: TRACKED_ACTION_LABEL[a] ?? a,
    count: n,
  }));
  const scanRows = Object.entries(data?.files.scan_status ?? {}).map(([s, n]) => ({
    label: SCAN_STATUS_META[s]?.label ?? s,
    count: n,
  }));
  const outboxRows = Object.entries(data?.email_outbox.by_status ?? {}).map(([s, n]) => ({
    label: OUTBOX_STATUS_META[s]?.label ?? s,
    count: n,
  }));
  const backends = data?.files.scan_backends;
  const scannerActive = backends?.clamd_reachable || backends?.clamscan_available;

  return (
    <Stack spacing={3}>
      <Paper sx={{ p: 3, borderRadius: 3, background: "linear-gradient(135deg,#00695c 0%,#004d40 100%)", color: "#fff" }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
          <Box>
            <Typography variant="h5" fontWeight={800}>گزارش انطباق حفاظت داده (DPO)</Typography>
            <Typography variant="body2" sx={{ opacity: 0.85, mt: 0.5 }}>
              رضایت، دسترسی، امنیت فایل و کانال ایمیل — B41+ فاز ۲۷ (تجمیعی و بی‌نام، بند ۱۵)
            </Typography>
          </Box>
          {data && (
            <Typography variant="caption" sx={{ opacity: 0.8 }}>
              تولید: {formatJalaliDateTime(data.generated_at)} — توسط {data.generated_by}
            </Typography>
          )}
        </Stack>
      </Paper>

      <Box display="flex" gap={1.5} alignItems="center" flexWrap="wrap" role="group" aria-label="بازه زمانی گزارش">
        <Typography variant="subtitle2" color="text.secondary">بازه:</Typography>
        {[7, 30, 90, 365].map((d) => (
          <Chip
            key={d} label={`${d} روز`} clickable
            color={days === d ? "primary" : "default"}
            variant={days === d ? "filled" : "outlined"}
            onClick={() => setDays(d)}
            aria-pressed={days === d}
          />
        ))}
      </Box>

      {isLoading && <CircularProgress sx={{ mx: "auto", display: "block", mt: 4 }} />}
      {error && (
        <Alert severity="error">
          دریافت گزارش ناموفق بود: {errDetail(error)}
        </Alert>
      )}

      {data && (
        <>
          <Grid container spacing={2}>
            <Grid item xs={6} md={3}><StatCard label="رضایت فعال" value={consentRows.reduce((s, r) => s + r.active, 0)} color="success.main" /></Grid>
            <Grid item xs={6} md={3}><StatCard label="ابطال در بازه" value={data.consents.revocations_in_window} color="warning.main" /></Grid>
            <Grid item xs={6} md={3}><StatCard label="فایل قرنطینه" value={data.files.scan_status.quarantined ?? 0} color="error.main" /></Grid>
            <Grid item xs={6} md={3}><StatCard label="ورود ناموفق" value={data.access.login_failed} color="error.main" /></Grid>
          </Grid>

          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3, height: "100%" }}>
                <Typography variant="subtitle1" fontWeight={700}>رضایت‌نامه‌ها (B41)</Typography>
                <Divider sx={{ my: 1.5 }} />
                {consentRows.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">رکوردی ثبت نشده است</Typography>
                ) : (
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>نوع رضایت</TableCell>
                          <TableCell align="left">فعال</TableCell>
                          <TableCell align="left">ابطال‌شده</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {consentRows.map((r) => (
                          <TableRow key={r.label}>
                            <TableCell>{r.label}</TableCell>
                            <TableCell align="left">{r.active.toLocaleString("fa-IR")}</TableCell>
                            <TableCell align="left">{r.revoked.toLocaleString("fa-IR")}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
                <Stack direction="row" spacing={1} mt={1.5} flexWrap="wrap" useFlexGap>
                  <Chip size="small" label={`ثبت در بازه: ${data.consents.grants_in_window.toLocaleString("fa-IR")}`} variant="outlined" />
                  <Chip size="small" label={`بدون نسخه متن: ${data.consents.grants_without_version.toLocaleString("fa-IR")}`} variant="outlined" />
                  {Object.entries(data.consents.versions).map(([kind, v]) => (
                    <Chip key={kind} size="small" variant="outlined"
                      label={`${CONSENT_KIND_LABEL[kind] ?? kind}: نسخه v${v.latest}`} />
                  ))}
                </Stack>
              </Paper>
            </Grid>

            <Grid item xs={12} md={6}>
              <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3, height: "100%" }}>
                <Typography variant="subtitle1" fontWeight={700}>دسترسی و رخدادها (بند ۱۱/۱۴)</Typography>
                <Divider sx={{ my: 1.5 }} />
                <CountTable rows={actionRows} emptyText="رخدادی در بازه ثبت نشده است" />
                <Stack direction="row" spacing={1} mt={1.5} flexWrap="wrap" useFlexGap>
                  <Chip size="small" variant="outlined" label={`کاربران فعال در رخدادها: ${data.access.distinct_actors.toLocaleString("fa-IR")}`} />
                </Stack>
              </Paper>
            </Grid>

            <Grid item xs={12} md={6}>
              <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3, height: "100%" }}>
                <Typography variant="subtitle1" fontWeight={700}>امنیت فایل (B39/B39-plus)</Typography>
                <Divider sx={{ my: 1.5 }} />
                <CountTable rows={scanRows} emptyText="فایلی آپلود نشده است" />
                <Stack direction="row" spacing={1} mt={1.5} flexWrap="wrap" useFlexGap>
                  <Chip size="small" variant="outlined"
                    label={`آپلود در بازه: ${data.files.uploads_in_window.toLocaleString("fa-IR")}`} />
                  {backends && (
                    <Chip size="small"
                      color={scannerActive ? "success" : "warning"}
                      label={scannerActive ? "آنتی‌ویروس واقعی فعال" : "قواعد پایه (ClamAV در دسترس نیست)"} />
                  )}
                  {backends?.clamd_reachable && <Chip size="small" color="success" label="clamd متصل" />}
                  {backends && !backends.clamd_reachable && backends.clamd_configured && (
                    <Chip size="small" color="warning" label="clamd پیکربندی ولی غیرقابل‌دسترس" />
                  )}
                </Stack>
                <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                  اسکنرهای استفاده‌شده: {Object.entries(data.files.scanner_usage).map(([k, v]) => `${k} (${v.toLocaleString("fa-IR")})`).join("، ") || "—"}
                </Typography>
              </Paper>
            </Grid>

            <Grid item xs={12} md={6}>
              <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3, height: "100%" }}>
                <Typography variant="subtitle1" fontWeight={700}>کانال ایمیل اعلان‌ها (B12+)</Typography>
                <Divider sx={{ my: 1.5 }} />
                <CountTable rows={outboxRows} emptyText="ایمیلی در صف نیست" />
                <Stack direction="row" spacing={1} mt={1.5} flexWrap="wrap" useFlexGap>
                  <Chip size="small" color={data.email_outbox.smtp_enabled ? "success" : "default"}
                    label={data.email_outbox.smtp_enabled ? "SMTP فعال" : "SMTP غیرفعال"} />
                </Stack>
              </Paper>
            </Grid>

            <Grid item xs={12}>
              <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3 }}>
                <Typography variant="subtitle1" fontWeight={700}>حساب‌ها و نشست‌ها</Typography>
                <Divider sx={{ my: 1.5 }} />
                <Grid container spacing={2}>
                  <Grid item xs={6} md={3}><StatCard label="کاربران فعال" value={data.accounts.users_active} /></Grid>
                  <Grid item xs={6} md={3}><StatCard label="غیرفعال‌شده" value={data.accounts.users_disabled} color="text.secondary" /></Grid>
                  <Grid item xs={6} md={3}><StatCard label="در انتظار فعال‌سازی" value={data.accounts.users_pending} color="warning.main" /></Grid>
                  <Grid item xs={6} md={3}><StatCard label="نشست فعال" value={data.accounts.active_sessions} color="info.main" /></Grid>
                </Grid>
              </Paper>
            </Grid>
          </Grid>
        </>
      )}
    </Stack>
  );
}
