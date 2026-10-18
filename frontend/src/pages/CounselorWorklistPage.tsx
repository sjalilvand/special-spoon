import {
  Alert, Box, Button, CircularProgress, Paper, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { errDetail } from "../api/client";
import { fetchCounselorAppointments } from "../api/schedule";
import type { CounselorAppointmentRow } from "../api/schedule";
import { formatJalaliDateTime } from "../utils/jalali";

export default function CounselorWorklistPage() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ["worklist-counselor-appointments"],
    queryFn: fetchCounselorAppointments,
  });
  const rows: CounselorAppointmentRow[] = data?.items ?? [];

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1}>
        <Typography variant="h6" fontWeight={700}>کارتابل مشاور — نوبت‌های امروز و آینده</Typography>
        <Button variant="outlined" onClick={() => navigate("/my-assessments")}>
          ارزیابی‌های من (پیش‌نویس/برگشتی)
        </Button>
      </Box>
      {error && <Alert severity="error">{errDetail(error)}</Alert>}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>پرونده</TableCell>
              <TableCell>متقاضی</TableCell>
              <TableCell>زمان</TableCell>
              <TableCell>مدت (دقیقه)</TableCell>
              <TableCell>محل</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={6} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {rows.length === 0 && (
              <TableRow><TableCell colSpan={6}>نوبتی در امروز و آینده وجود ندارد.</TableCell></TableRow>
            )}
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.case_number}</TableCell>
                <TableCell>{row.applicant_name}</TableCell>
                <TableCell>{formatJalaliDateTime(row.scheduled_at)}</TableCell>
                <TableCell>{row.duration_minutes ?? "—"}</TableCell>
                <TableCell>{row.location ?? "—"}</TableCell>
                <TableCell>
                  <Button size="small" onClick={() => navigate(`/cases/${row.case_id}`)}>باز کردن پرونده</Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}
