import {
  Alert, Box, Chip, CircularProgress, Paper, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import { CASE_STATUS_META, CONSENT_META } from "../api/cases";
import { APPOINTMENT_STATUS_META } from "../api/schedule";
import {
  fetchMyAppointments, fetchMyCases, fetchMyProfile, fetchMyRecommendations,
} from "../api/me";
import type { MyProfile } from "../api/me";

function isNotFound(e: unknown): boolean {
  const anyE = e as { response?: { status?: number } };
  return anyE?.response?.status === 404;
}

function InfoRow({ label, value }: { label: string; value: string | null }) {
  return (
    <Stack direction="row" spacing={1}>
      <Typography variant="body2" sx={{ minWidth: 150, color: "text.secondary" }}>{label}:</Typography>
      <Typography variant="body2">{value ?? "—"}</Typography>
    </Stack>
  );
}

export default function MyPanelPage() {
  const { user } = useAuth();

  const { data: profile, isLoading, error } = useQuery({
    queryKey: ["me-profile"],
    queryFn: fetchMyProfile,
    retry: false,
  });

  const { data: cases } = useQuery({
    queryKey: ["me-cases"],
    queryFn: fetchMyCases,
    enabled: Boolean(profile),
  });

  const { data: appts } = useQuery({
    queryKey: ["me-appointments"],
    queryFn: fetchMyAppointments,
    enabled: Boolean(profile),
  });

  const { data: recs } = useQuery({
    queryKey: ["me-recommendations"],
    queryFn: fetchMyRecommendations,
    enabled: Boolean(profile),
  });

  if (isLoading) return <CircularProgress />;

  if (error) {
    return isNotFound(error) ? (
      <Alert severity="warning">
        حساب شما به پروفایل متقاضی متصل نیست؛ از پذیرش سازمان پیگیری کنید.
      </Alert>
    ) : (
      <Alert severity="error">{errDetail(error)}</Alert>
    );
  }

  return (
    <Stack spacing={2}>
      <Typography variant="h6" fontWeight={700}>پنل شخصی — {user?.display_name}</Typography>

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle1" fontWeight={700} mb={1}>اطلاعات پایه من</Typography>
        <Stack spacing={0.5}>
          <InfoRow label="نام و نام خانوادگی" value={profile ? `${profile.first_name} ${profile.last_name}` : null} />
          <InfoRow label="کد ملی" value={profile?.national_id ?? null} />
          <InfoRow label="شماره پرسنلی" value={profile?.employee_code ?? null} />
          <InfoRow label="موبایل" value={profile?.mobile ?? null} />
          <InfoRow label="واحد سازمانی" value={profile?.unit_title ?? null} />
          <InfoRow label="محل خدمت" value={profile?.service_location_title ?? null} />
        </Stack>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle1" fontWeight={700} mb={1}>پرونده‌های من (وضعیت کلی)</Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>شماره پرونده</TableCell>
                <TableCell>تاریخ پذیرش</TableCell>
                <TableCell>مشاور</TableCell>
                <TableCell>رضایت‌نامه</TableCell>
                <TableCell>وضعیت</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {cases?.items.length === 0 && (
                <TableRow><TableCell colSpan={5}>پرونده‌ای برای شما ثبت نشده است.</TableCell></TableRow>
              )}
              {cases?.items.map((row) => {
                const st = CASE_STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
                const cs = CONSENT_META[row.consent_status] ?? { label: row.consent_status, color: "default" as const };
                return (
                  <TableRow key={row.id}>
                    <TableCell>{row.case_number}</TableCell>
                    <TableCell>{new Date(row.acceptance_date).toLocaleDateString("fa-IR")}</TableCell>
                    <TableCell>{row.counselor_name ?? "—"}</TableCell>
                    <TableCell><Chip size="small" color={cs.color} label={cs.label} /></TableCell>
                    <TableCell><Chip size="small" color={st.color} label={st.label} /></TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle1" fontWeight={700} mb={1}>نوبت‌های من</Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>پرونده</TableCell>
                <TableCell>زمان</TableCell>
                <TableCell>محل</TableCell>
                <TableCell>وضعیت</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {appts?.items.length === 0 && (
                <TableRow><TableCell colSpan={4}>نوبتی ثبت نشده است.</TableCell></TableRow>
              )}
              {appts?.items.map((row) => {
                const m = APPOINTMENT_STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
                return (
                  <TableRow key={row.id}>
                    <TableCell>{row.case_number}</TableCell>
                    <TableCell>{new Date(row.scheduled_at).toLocaleString("fa-IR")}</TableCell>
                    <TableCell>{row.location ?? "—"}</TableCell>
                    <TableCell><Chip size="small" color={m.color} label={m.label} /></TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle1" fontWeight={700} mb={1}>توصیه‌های منتشرشده مشاور</Typography>
        <Stack spacing={1}>
          {recs?.items.length === 0 && (
            <Typography variant="body2" color="text.secondary">توصیه‌ای منتشر نشده است.</Typography>
          )}
          {recs?.items.map((r) => (
            <Box key={r.id} sx={{ border: 1, borderColor: "divider", borderRadius: 1, p: 1.5 }}>
              <Stack direction="row" justifyContent="space-between" flexWrap="wrap" useFlexGap>
                <Typography variant="caption" color="text.secondary">
                  پرونده {r.case_number} — {r.published_at ? new Date(r.published_at).toLocaleString("fa-IR") : ""}
                </Typography>
              </Stack>
              <Typography variant="body2" sx={{ mt: 0.5, whiteSpace: "pre-wrap" }}>{r.content}</Typography>
            </Box>
          ))}
        </Stack>
      </Paper>

      <Alert severity="info">
        یادداشت‌های داخلی، ارزیابی خطر و تشخیص در این پنل نمایش داده نمی‌شود.
        برای دسترسی به سوابق کامل، درخواست خود را از فرایند مصوب سازمان پیگیری کنید (بند ۹.۳).
      </Alert>
    </Stack>
  );
}
