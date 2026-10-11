import {
  Alert, Box, Button, Chip, CircularProgress, Paper, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import { ASSESSMENT_STATUS_META, fetchCaseAssessments } from "../api/assessments";

export default function CaseAssessments({ caseId }: { caseId: string }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const roles = user?.roles ?? [];
  const clinical = roles.includes("COUNSELOR") || roles.includes("TECHNICAL_SUPERVISOR");
  const isCounselor = roles.includes("COUNSELOR");

  const { data, isLoading, error } = useQuery({
    queryKey: ["case-assessments", caseId],
    queryFn: () => fetchCaseAssessments(caseId),
    enabled: clinical,
  });

  if (!clinical) return null;

  return (
    <Paper sx={{ p: 2 }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
        <Typography variant="subtitle1" fontWeight={700}>ارزیابی‌ها (محتوای بالینی)</Typography>
        {isCounselor && (
          <Button size="small" variant="contained"
            onClick={() => navigate(`/cases/${caseId}/assessments/new`)}>
            ارزیابی جدید
          </Button>
        )}
      </Box>
      {error && <Alert severity="error">{errDetail(error)}</Alert>}
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>نسخه</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>نویسنده</TableCell>
              <TableCell>آخرین تغییر</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={5} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.length === 0 && (
              <TableRow><TableCell colSpan={5}>ارزیابی‌ای ثبت نشده است.</TableCell></TableRow>
            )}
            {data?.items.map((row) => {
              const st = ASSESSMENT_STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
              return (
                <TableRow key={row.id}>
                  <TableCell>{row.version_no}</TableCell>
                  <TableCell><Chip size="small" color={st.color} label={st.label} /></TableCell>
                  <TableCell>{row.author_name ?? "—"}</TableCell>
                  <TableCell>
                    {row.updated_at ? new Date(row.updated_at).toLocaleString("fa-IR") : "—"}
                  </TableCell>
                  <TableCell>
                    <Button size="small" onClick={() => navigate(`/assessments/${row.id}`)}>
                      باز کردن
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}
