import {
  Alert, Box, Button, Chip, CircularProgress, Paper, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import PsychologyRoundedIcon from "@mui/icons-material/PsychologyRounded";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import { CASE_STATUS_META, CONSENT_META } from "../api/cases";
import { APPOINTMENT_STATUS_META } from "../api/schedule";
import {
  fetchMyAppointments, fetchMyCases, fetchMyOrgExams, fetchMyProfile, fetchMyRecommendations,
  MyOrgExamProgram,
} from "../api/me";
import { CounselingFileItem, fetchMyCounselingFile } from "../api/counseling";
import { formatJalali, formatJalaliDateTime } from "../utils/jalali";

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

// فاز ۷۰ - خط زمانی پروندهٔ مشاورهٔ من (آزمون‌ها + مشاوره‌ها + نوبت‌ها با زمان)
// فاز ۸۷ - اقلام جدید: پرسشنامهٔ پذیرش + ارزیابی‌های پرونده
function FileTimeline({ items }: { items: CounselingFileItem[] }) {
  const kindMeta: Record<CounselingFileItem["kind"], { label: string; color: "primary" | "secondary" | "info" | "warning" }> = {
    psych_test: { label: "آزمون", color: "primary" },
    consultation: { label: "مشاوره", color: "secondary" },
    appointment: { label: "نوبت", color: "info" },
    intake: { label: "پرسشنامه", color: "warning" },
    assessment: { label: "ارزیابی", color: "info" },
  };
  return (
    <Stack spacing={0.5}>
      {items.map((it) => {
        const m = kindMeta[it.kind];
        return (
          <Box key={`${it.kind}-${it.id}`} sx={{ border: 1, borderColor: "divider", borderRadius: 1.5, p: 1 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Chip size="small" color={m.color} variant="outlined" label={m.label} />
              <Typography variant="body2" fontWeight={700} flexGrow={1}>{it.title}</Typography>
              <Typography variant="caption" color="text.secondary">
                {formatJalaliDateTime(it.at)}
              </Typography>
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
              {it.kind === "psych_test" &&
                `نمره ${(it.score ?? 0).toLocaleString("fa-IR")} — ${it.interpretation_label ?? ""}${it.viewed ? " — دیده‌شده" : ""}`}
              {it.kind === "consultation" &&
                `وضعیت: ${it.status ?? "—"}${it.payment_status === "paid" ? " — پرداخت آنلاین انجام شد" : ""}`}
              {it.kind === "appointment" && `${it.case_number ? `پروندهٔ ${it.case_number}` : ""}${it.location ? ` — ${it.location}` : ""}`}
              {it.kind === "intake" && `${it.request_topic ? `درخواست: ${it.request_topic}` : ""}${it.status ? ` — ${it.status === "final" ? "نهایی‌شده" : "پیش‌نویس"}` : ""}`}
              {it.kind === "assessment" && `${it.case_number ? `پروندهٔ ${it.case_number}` : ""}${it.status ? ` — وضعیت: ${it.status}` : ""}`}
            </Typography>
          </Box>
        );
      })}
    </Stack>
  );
}

export default function MyPanelPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

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

  // فاز ۷۰ - پروندهٔ مشاورهٔ من (برای هر کاربر — مستقل از اتصال متقاضی)
  const { data: myFile } = useQuery({
    queryKey: ["me-counseling-file"],
    queryFn: fetchMyCounselingFile,
  });

  // فاز ۸۷ - آزمون‌های سازمانی من (برنامه‌های فعال سازمانِ من)
  const { data: orgExams } = useQuery({
    queryKey: ["me-org-exams"],
    queryFn: fetchMyOrgExams,
  });
  const orgExamPrograms: MyOrgExamProgram[] = orgExams?.items ?? [];

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

      {/* فاز ۴۷ - دسترسی سریع به مرکز آزمون */}
      <Paper
        onClick={() => navigate("/psych-tests")}
        sx={{ p: 2, cursor: "pointer", border: "1px solid #ede7f6", display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap",
          background: "linear-gradient(135deg,#fdf3f4,#faf6fb)", transition: "box-shadow .2s", "&:hover": { boxShadow: 3 } }}
      >
        <PsychologyRoundedIcon color="primary" sx={{ fontSize: 34 }} />
        <Box flexGrow={1} minWidth={200}>
          <Typography variant="subtitle1" fontWeight={800}>مرکز آزمون روان‌شناسی</Typography>
          <Typography variant="body2" color="text.secondary">
            آزمون‌های استاندارد (افسردگی بک، اضطراب، استرس، هوش، عزت نفس و…) را انجام دهید و نتیجه و ریزنمره‌ها را ببینید.
          </Typography>
        </Box>
        <Button variant="contained">شروع آزمون‌ها</Button>
      </Paper>

      {/* فاز ۸۷ - آزمون‌های سازمانی من: آزمون‌های تعیین‌شده در برنامه‌های فعال سازمانِ من */}
      {orgExamPrograms.length > 0 && (
        <Paper sx={{ p: 2, border: "1px solid #ffe0b2" }}>
          <Typography variant="subtitle1" fontWeight={700} mb={1}>آزمون‌های سازمان من</Typography>
          {orgExamPrograms.map((p) => (
            <Box key={p.id} sx={{ border: 1, borderColor: "divider", borderRadius: 1.5, p: 1.5, mb: 1 }}>
              <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap" useFlexGap>
                <Typography variant="subtitle2" fontWeight={700} flexGrow={1}>{p.title}</Typography>
                {p.due_date && <Typography variant="caption" color="text.secondary">مهلت: {formatJalali(p.due_date)}</Typography>}
              </Stack>
              {p.tests.map((t) => (
                <Box key={t.test_id} sx={{ display: "flex", alignItems: "center", gap: 1, mt: 1, flexWrap: "wrap" }}>
                  <Chip size="small" color={t.done ? "success" : "warning"} variant="outlined"
                    label={t.done ? "انجام شده" : "در انتظار انجام"} />
                  <Typography variant="body2" flexGrow={1}>
                    {t.title}{t.is_required ? " (الزامی)" : ""}
                  </Typography>
                  {t.done && t.score !== null && (
                    <Typography variant="caption" color="text.secondary">
                      نمره: {t.score.toLocaleString("fa-IR")}{t.interpretation_label ? ` — ${t.interpretation_label}` : ""}
                    </Typography>
                  )}
                  <Button size="small" variant={t.done ? "text" : "contained"}
                    onClick={() => navigate(`/psych-tests/${t.test_slug}/run`)}>
                    {t.done ? "انجام مجدد" : "شروع آزمون"}
                  </Button>
                </Box>
              ))}
            </Box>
          ))}
        </Paper>
      )}

      {/* فاز ۷۰ - پروندهٔ مشاورهٔ من: تاریخچهٔ آزمون‌ها و مشاوره‌ها به همراه زمان */}
      {myFile && (
        <Paper sx={{ p: 2 }}>
          <Stack direction="row" alignItems="center" spacing={1} mb={1} flexWrap="wrap" useFlexGap>
            <Typography variant="subtitle1" fontWeight={700} flexGrow={1}>پروندهٔ مشاوره من</Typography>
            <Chip size="small" variant="outlined" dir="ltr" label={myFile.file.file_code} />
            <Typography variant="caption" color="text.secondary">
              {myFile.counts.psych_tests.toLocaleString("fa-IR")} آزمون —{" "}
              {myFile.counts.consultations.toLocaleString("fa-IR")} مشاوره —{" "}
              {myFile.counts.appointments.toLocaleString("fa-IR")} نوبت —{" "}
              {myFile.counts.intakes.toLocaleString("fa-IR")} پرسشنامه —{" "}
              {myFile.counts.assessments.toLocaleString("fa-IR")} ارزیابی
            </Typography>
          </Stack>
          {myFile.items.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              هنوز رخدادی ثبت نشده؛ با اولین آزمون یا رزرو مشاوره، تاریخچه اینجا نگهداری می‌شود.
            </Typography>
          ) : (
            <FileTimeline items={myFile.items} />
          )}
        </Paper>
      )}

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
                    <TableCell>{formatJalali(row.acceptance_date)}</TableCell>
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
                    <TableCell>{formatJalaliDateTime(row.scheduled_at)}</TableCell>
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
              <Typography variant="caption" color="text.secondary">
                پرونده {r.case_number} — {r.published_at ? formatJalaliDateTime(r.published_at) : ""}
              </Typography>
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
