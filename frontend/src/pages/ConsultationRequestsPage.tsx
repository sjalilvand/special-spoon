import {
  Alert, Box, Chip, CircularProgress, FormControl, InputLabel, MenuItem, Paper, Select,
  Stack, Table, TableBody, TableCell, TableContainer, TableHead, TablePagination,
  TableRow, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { errDetail } from "../api/client";
import { CONSULT_STATUS_META, fetchConsultationRequests, updateConsultationRequest } from "../api/siteops";

export default function ConsultationRequestsPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(0);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["consultations", page, status],
    queryFn: () => fetchConsultationRequests({ page: page + 1, status: status || undefined }),
  });

  const changeStatus = useMutation({
    mutationFn: (p: { id: string; status: string }) => updateConsultationRequest(p.id, p.status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["consultations"] }),
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Stack spacing={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center" gap={2} flexWrap="wrap">
        <Typography variant="h6" fontWeight={700}>درخواست‌های مشاوره (سایت عمومی)</Typography>
        <FormControl size="small" sx={{ minWidth: 170 }}>
          <InputLabel>وضعیت</InputLabel>
          <Select value={status} label="وضعیت" onChange={(e) => { setPage(0); setStatus(e.target.value); }}>
            <MenuItem value="">همه</MenuItem>
            {Object.entries(CONSULT_STATUS_META).map(([k, v]) => (
              <MenuItem key={k} value={k}>{v.label}</MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>نام</TableCell>
              <TableCell>موبایل</TableCell>
              <TableCell>موضوع</TableCell>
              <TableCell>تاریخ ترجیحی</TableCell>
              <TableCell>بازه</TableCell>
              <TableCell>زمان ثبت</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={8} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.length === 0 && (
              <TableRow><TableCell colSpan={8}>درخواستی ثبت نشده است.</TableCell></TableRow>
            )}
            {data?.items.map((row) => {
              const m = CONSULT_STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
              return (
                <TableRow key={row.id}>
                  <TableCell>{row.full_name}</TableCell>
                  <TableCell>{row.mobile}</TableCell>
                  <TableCell>{row.topic}</TableCell>
                  <TableCell>
                    {row.preferred_date ? new Date(row.preferred_date).toLocaleDateString("fa-IR") : "—"}
                  </TableCell>
                  <TableCell>{row.preferred_slot ?? "—"}</TableCell>
                  <TableCell>
                    {row.created_at ? new Date(row.created_at).toLocaleString("fa-IR") : "—"}
                  </TableCell>
                  <TableCell><Chip size="small" color={m.color} label={m.label} /></TableCell>
                  <TableCell>
                    <FormControl size="small" sx={{ minWidth: 150 }}>
                      <Select
                        value={row.status}
                        onChange={(e) => changeStatus.mutate({ id: row.id, status: e.target.value })}
                      >
                        {Object.entries(CONSULT_STATUS_META).map(([k, v]) => (
                          <MenuItem key={k} value={k}>{v.label}</MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <TablePagination component="div" count={data?.total ?? 0} page={page}
          onPageChange={(_, p) => setPage(p)} rowsPerPage={20} rowsPerPageOptions={[20]}
          labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`} />
      </TableContainer>
    </Stack>
  );
}
