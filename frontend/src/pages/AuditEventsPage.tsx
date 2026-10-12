import {
  Alert, Chip, CircularProgress, Paper, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TablePagination, TableRow, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { errDetail } from "../api/client";
import { fetchAuditEvents } from "../api/reports";

export default function AuditEventsPage() {
  const [page, setPage] = useState(0);
  const { data, isLoading, error } = useQuery({
    queryKey: ["audit-events", page],
    queryFn: () => fetchAuditEvents({ page: page + 1 }),
  });

  return (
    <Stack spacing={2}>
      <Typography variant="h6" fontWeight={700}>رخدادهای سامانه</Typography>
      {error && <Alert severity="error">{errDetail(error)}</Alert>}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>زمان</TableCell>
              <TableCell>عامل</TableCell>
              <TableCell>عملیات</TableCell>
              <TableCell>موجودیت</TableCell>
              <TableCell>نتیجه</TableCell>
              <TableCell>IP</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={6} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.length === 0 && (
              <TableRow><TableCell colSpan={6}>رخدادی ثبت نشده است.</TableCell></TableRow>
            )}
            {data?.items.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.created_at ? new Date(row.created_at).toLocaleString("fa-IR") : "—"}</TableCell>
                <TableCell>{row.actor_name ?? "سیستم"}</TableCell>
                <TableCell>{row.action}</TableCell>
                <TableCell>
                  {row.entity_type ? `${row.entity_type}${row.entity_id ? ` (${row.entity_id.slice(0, 8)}…)` : ""}` : "—"}
                </TableCell>
                <TableCell>
                  <Chip size="small" color={row.result === "success" ? "success" : "error"}
                    label={row.result === "success" ? "موفق" : row.result} />
                </TableCell>
                <TableCell>{row.ip ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <TablePagination component="div" count={data?.total ?? 0} page={page}
          onPageChange={(_, p) => setPage(p)} rowsPerPage={30} rowsPerPageOptions={[30]}
          labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`} />
      </TableContainer>
    </Stack>
  );
}
