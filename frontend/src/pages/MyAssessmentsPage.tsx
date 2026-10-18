import {
  Alert, Button, Chip, CircularProgress, Paper, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ASSESSMENT_STATUS_META, fetchCounselorWorklist } from "../api/assessments";
import { formatJalaliDateTime } from "../utils/jalali";

export default function MyAssessmentsPage() {
  const navigate = useNavigate();
  const [error] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["worklist-counselor"],
    queryFn: fetchCounselorWorklist,
  });

  return (
    <Stack spacing={2}>
      <Typography variant="h6" fontWeight={700}>ارزیابی‌های من (پیش‌نویس و برگشتی)</Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>پرونده</TableCell>
              <TableCell>متقاضی</TableCell>
              <TableCell>نسخه</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>آخرین تغییر</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={6} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.length === 0 && (
              <TableRow><TableCell colSpan={6}>موردی وجود ندارد.</TableCell></TableRow>
            )}
            {data?.items.map((row) => {
              const st = ASSESSMENT_STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
              return (
                <TableRow key={row.id}>
                  <TableCell>{row.case_number}</TableCell>
                  <TableCell>{row.applicant_name ?? "—"}</TableCell>
                  <TableCell>{row.version_no}</TableCell>
                  <TableCell><Chip size="small" color={st.color} label={st.label} /></TableCell>
                  <TableCell>
                    {row.updated_at ? formatJalaliDateTime(row.updated_at) : "—"}
                  </TableCell>
                  <TableCell>
                    <Button size="small" variant="outlined" onClick={() => navigate(`/assessments/${row.id}`)}>
                      باز کردن
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}
