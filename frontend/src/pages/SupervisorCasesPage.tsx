import {
  Alert, Button, Chip, CircularProgress, Paper, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { errDetail } from "../api/client";
import { CASE_STATUS_META } from "../api/cases";
import { fetchSupervisedCases } from "../api/supervisor";
import { formatJalali } from "../utils/jalali";

export default function SupervisorCasesPage() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ["supervised-cases"],
    queryFn: fetchSupervisedCases,
  });

  return (
    <Stack spacing={2}>
      <Typography variant="h6" fontWeight={700}>پرونده‌های محدوده نظارت (بند ۹.۴)</Typography>
      {error && <Alert severity="error">{errDetail(error)}</Alert>}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>پرونده</TableCell>
              <TableCell>متقاضی</TableCell>
              <TableCell>مشاور</TableCell>
              <TableCell>تاریخ پذیرش</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={6} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.length === 0 && (
              <TableRow><TableCell colSpan={6}>پرونده فعالی در محدوده نظارت وجود ندارد.</TableCell></TableRow>
            )}
            {data?.items.map((row) => {
              const st = CASE_STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
              return (
                <TableRow key={row.id}>
                  <TableCell>{row.case_number}</TableCell>
                  <TableCell>{row.applicant_name}</TableCell>
                  <TableCell>{row.counselor_name ?? "—"}</TableCell>
                  <TableCell>{formatJalali(row.acceptance_date)}</TableCell>
                  <TableCell><Chip size="small" color={st.color} label={st.label} /></TableCell>
                  <TableCell>
                    <Button size="small" onClick={() => navigate(`/cases/${row.id}`)}>باز کردن</Button>
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
