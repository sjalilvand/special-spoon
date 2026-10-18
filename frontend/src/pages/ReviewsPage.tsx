import {
  Alert, Button, Chip, CircularProgress, Paper, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ASSESSMENT_STATUS_META, fetchSupervisorWorklist } from "../api/assessments";
import { formatJalaliDateTime } from "../utils/jalali";

export default function ReviewsPage() {
  const navigate = useNavigate();
  const [error] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["worklist-supervisor"],
    queryFn: fetchSupervisorWorklist,
  });

  return (
    <Stack spacing={2}>
      <Typography variant="h6" fontWeight={700}>بررسی‌های فنی (کارتابل مسئول فنی)</Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>پرونده</TableCell>
              <TableCell>متقاضی</TableCell>
              <TableCell>نسخه</TableCell>
              <TableCell>نویسنده</TableCell>
              <TableCell>زمان نهایی‌سازی</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={7} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.length === 0 && (
              <TableRow><TableCell colSpan={7}>صف بررسی خالی است.</TableCell></TableRow>
            )}
            {data?.items.map((row) => {
              const st = ASSESSMENT_STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
              return (
                <TableRow key={row.id}>
                  <TableCell>{row.case_number}</TableCell>
                  <TableCell>{row.applicant_name ?? "—"}</TableCell>
                  <TableCell>{row.version_no}</TableCell>
                  <TableCell>{row.author_name ?? "—"}</TableCell>
                  <TableCell>
                    {row.finalized_at ? formatJalaliDateTime(row.finalized_at) : "—"}
                  </TableCell>
                  <TableCell><Chip size="small" color={st.color} label={st.label} /></TableCell>
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
