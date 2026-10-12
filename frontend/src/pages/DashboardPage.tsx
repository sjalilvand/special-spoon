import {
  Alert, Box, Card, CardContent, Chip, CircularProgress, FormControl, InputLabel,
  MenuItem, Paper, Select, Stack, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import { CASE_STATUS_META } from "../api/cases";
import { APPOINTMENT_STATUS_META } from "../api/schedule";
import { fetchCounselorOptions } from "../api/cases";
import { fetchReportSummary } from "../api/reports";

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="caption" color="text.secondary">{label}</Typography>
        <Typography variant="h5" fontWeight={700}>{value.toLocaleString("fa-IR")}</Typography>
      </CardContent>
    </Card>
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
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={2} flexWrap="wrap">
        <Typography variant="h6" fontWeight={700}>داشبورد و گزارش‌ها</Typography>
        <Box flexGrow={1} />
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel>بازه</InputLabel>
          <Select value={days} label="بازه" onChange={(e) => setDays(Number(e.target.value))}>
            <MenuItem value={7}>۷ روز اخیر</MenuItem>
            <MenuItem value={30}>۳۰ روز اخیر</MenuItem>
            <MenuItem value={90}>۹۰ روز اخیر</MenuItem>
            <MenuItem value={365}>یک سال اخیر</MenuItem>
          </Select>
        </FormControl>
        {canFilterCounselor && (
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>مشاور</InputLabel>
            <Select value={counselorId} label="مشاور"
              onChange={(e) => setCounselorId(e.target.value)}>
              <MenuItem value="">همه مشاوران</MenuItem>
              {counselors?.items.map((o) => (
                <MenuItem key={o.id} value={o.id}>{o.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
      </Box>

      {error && <Alert severity="error">{errDetail(error)}</Alert>}
      {isLoading && <CircularProgress size={28} />}

      {data && (
        <>
          {isStaff && (
            <Box display="grid" gridTemplateColumns={{ xs: "1fr 1fr", md: "repeat(4, 1fr)" }} gap={2}>
              <StatCard label="متقاضیان" value={data.applicants_total} />
              <StatCard label="حساب‌های فعال" value={data.users_active} />
              <StatCard label="مشاوران فعال" value={data.counselors_active} />
              <StatCard label="پرونده‌های منتظر تخصیص" value={data.cases_by_status["awaiting_assignment"] ?? 0} />
              <StatCard label="ارزیابی‌های منتظر بررسی" value={data.assessments_pending_review} />
              <StatCard label="نوبت‌های انجام‌شده" value={data.appointments_by_status["done"] ?? 0} />
              <StatCard label="لغو / عدم حضور" value={(data.appointments_by_status["cancelled"] ?? 0) + (data.appointments_by_status["no_show"] ?? 0)} />
              <StatCard label="جلسات انجام‌شده" value={data.sessions_count} />
            </Box>
          )}
          {!isStaff && (
            <Box display="grid" gridTemplateColumns={{ xs: "1fr 1fr", md: "repeat(4, 1fr)" }} gap={2}>
              <StatCard label="نوبت‌های انجام‌شده" value={data.appointments_by_status["done"] ?? 0} />
              <StatCard label="لغو / عدم حضور" value={(data.appointments_by_status["cancelled"] ?? 0) + (data.appointments_by_status["no_show"] ?? 0)} />
              <StatCard label="جلسات انجام‌شده" value={data.sessions_count} />
              <StatCard label="ارزیابی‌های منتظر بررسی" value={data.assessments_pending_review} />
            </Box>
          )}

          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={700} mb={1}>وضعیت پرونده‌ها</Typography>
            {caseEntries.length === 0 && (
              <Typography variant="body2" color="text.secondary">پرونده‌ای وجود ندارد.</Typography>
            )}
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {caseEntries.map(([status, n]) => {
                const m = CASE_STATUS_META[status] ?? { label: status, color: "default" as const };
                return <Chip key={status} color={m.color} label={`${m.label}: ${n.toLocaleString("fa-IR")}`} />;
              })}
            </Stack>
          </Paper>

          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={700} mb={1}>وضعیت نوبت‌ها (بازه انتخابی)</Typography>
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

          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" fontWeight={700} mb={1}>حجم کار مشاوران</Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>مشاور</TableCell>
                    <TableCell>پرونده‌های فعال</TableCell>
                    <TableCell>جلسات (بازه)</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.counselor_workload.length === 0 && (
                    <TableRow><TableCell colSpan={3}>موردی وجود ندارد.</TableCell></TableRow>
                  )}
                  {data.counselor_workload.map((row) => (
                    <TableRow key={row.counselor_id}>
                      <TableCell>{row.counselor_name}</TableCell>
                      <TableCell>{row.active_cases.toLocaleString("fa-IR")}</TableCell>
                      <TableCell>{row.sessions_count.toLocaleString("fa-IR")}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>

          {isStaff && (
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>نتیجه ورودهای اکسل (۵ مورد اخیر)</Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>نوع</TableCell>
                      <TableCell>وضعیت</TableCell>
                      <TableCell>ایجاد</TableCell>
                      <TableCell>خطا</TableCell>
                      <TableCell>زمان</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.recent_imports.length === 0 && (
                      <TableRow><TableCell colSpan={5}>ورودی ثبت نشده است.</TableCell></TableRow>
                    )}
                    {data.recent_imports.map((row, idx) => (
                      <TableRow key={idx}>
                        <TableCell>{row.import_type}</TableCell>
                        <TableCell>
                          <Chip size="small" color={row.status === "committed" ? "success" : "warning"}
                            label={row.status === "committed" ? "ثبت‌شده" : "پیش‌نویس"} />
                        </TableCell>
                        <TableCell>{row.created_rows.toLocaleString("fa-IR")}</TableCell>
                        <TableCell>{row.error_rows.toLocaleString("fa-IR")}</TableCell>
                        <TableCell>
                          {row.created_at ? new Date(row.created_at).toLocaleString("fa-IR") : "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          )}

          <Alert severity="info">
            گزارش‌ها تجمیعی است؛ فهرست تشخیص افراد یا متن درمان در گزارش مدیریتی ارائه نمی‌شود (بند ۱۵).
          </Alert>
        </>
      )}
    </Stack>
  );
}
