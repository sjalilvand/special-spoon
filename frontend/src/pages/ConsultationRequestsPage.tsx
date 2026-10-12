import {
  Alert, Box, Button, Checkbox, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, FormControl, FormControlLabel, InputLabel, MenuItem,
  Paper, Select, Stack, Table, TableBody, TableCell, TableContainer, TableHead,
  TablePagination, TableRow, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { errDetail } from "../api/client";
import { CONSULT_STATUS_META, fetchConsultationRequests, updateConsultationRequest } from "../api/siteops";
import type { ConsultationRow } from "../api/siteops";
import { convertConsultationRequest } from "../api/referrals";
import { fetchCounselorOptions, fetchServiceLocations } from "../api/people";
import type { IdName } from "../api/people";

export default function ConsultationRequestsPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(0);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [convertRow, setConvertRow] = useState<ConsultationRow | null>(null);

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
              <TableCell>زمان ثبت</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={7} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.length === 0 && (
              <TableRow><TableCell colSpan={7}>درخواستی ثبت نشده است.</TableCell></TableRow>
            )}
            {data?.items.map((row) => {
              const m = CONSULT_STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
              const canConvert = row.status === "new" || row.status === "in_review";
              return (
                <TableRow key={row.id}>
                  <TableCell>{row.full_name}</TableCell>
                  <TableCell>{row.mobile}</TableCell>
                  <TableCell>{row.topic}</TableCell>
                  <TableCell>
                    {row.preferred_date ? new Date(row.preferred_date).toLocaleDateString("fa-IR") : "—"}
                  </TableCell>
                  <TableCell>
                    {row.created_at ? new Date(row.created_at).toLocaleString("fa-IR") : "—"}
                  </TableCell>
                  <TableCell><Chip size="small" color={m.color} label={m.label} /></TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5} alignItems="center">
                      {canConvert && (
                        <Button size="small" variant="outlined" onClick={() => setConvertRow(row)}>
                          تبدیل
                        </Button>
                      )}
                      <FormControl size="small" sx={{ minWidth: 130 }}>
                        <Select
                          value={row.status}
                          onChange={(e) => changeStatus.mutate({ id: row.id, status: e.target.value })}
                        >
                          {Object.entries(CONSULT_STATUS_META).map(([k, v]) => (
                            <MenuItem key={k} value={k}>{v.label}</MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </Stack>
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

      <ConvertDialog
        row={convertRow}
        onClose={() => setConvertRow(null)}
        invalidate={() => qc.invalidateQueries({ queryKey: ["consultations"] })}
        onError={setError}
      />
    </Stack>
  );
}

function ConvertDialog({ row, onClose, invalidate, onError }: {
  row: ConsultationRow | null;
  onClose: () => void;
  invalidate: () => void;
  onError: (m: string) => void;
}) {
  const [createCase, setCreateCase] = useState(true);
  const [counselorId, setCounselorId] = useState("");
  const [serviceLocationId, setServiceLocationId] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const { data: counselors } = useQuery({
    queryKey: ["counselor-options"],
    queryFn: fetchCounselorOptions,
    enabled: Boolean(row) && createCase,
  });
  const { data: locations } = useQuery({
    queryKey: ["locations"],
    queryFn: fetchServiceLocations,
    enabled: Boolean(row) && createCase,
  });

  useEffect(() => {
    if (row) {
      setCreateCase(true);
      setCounselorId("");
      setServiceLocationId("");
      setFormError(null);
      setSuccess(null);
    }
  }, [row]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!row) return;
    setFormError(null);
    setBusy(true);
    try {
      const res = await convertConsultationRequest(row.id, {
        create_case: createCase,
        counselor_id: createCase && counselorId ? counselorId : undefined,
        service_location_id: createCase && serviceLocationId ? serviceLocationId : undefined,
      });
      setSuccess(
        `متقاضی ${res.applicant_created ? "ایجاد" : "یافت"} شد${res.case_number ? ` و پرونده ${res.case_number} تشکیل شد` : ""}.`
      );
      invalidate();
    } catch (err) {
      setFormError(errDetail(err));
      onError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={row !== null} onClose={onClose} maxWidth="xs" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>تبدیل به متقاضی</DialogTitle>
        <DialogContent>
          {success && (
            <Alert severity="success" sx={{ mt: 2 }}>
              {success}
              <Button size="small" sx={{ display: "block", mt: 1 }} onClick={onClose}>بستن</Button>
            </Alert>
          )}
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          {row && !success && (
            <Stack spacing={2} mt={2}>
              <Typography variant="body2" color="text.secondary">
                نام: <b>{row.full_name}</b> | موبایل: <b>{row.mobile}</b> | موضوع: <b>{row.topic}</b>
              </Typography>
              <FormControlLabel
                control={<Checkbox checked={createCase} onChange={(e) => setCreateCase(e.target.checked)} />}
                label="تشکیل پرونده جدید"
              />
              {createCase && (
                <>
                  <FormControl size="small" fullWidth>
                    <InputLabel>مشاور (اختیاری — تخصیص فوری)</InputLabel>
                    <Select
                      value={counselorId}
                      label="مشاور (اختیاری)"
                      onChange={(e) => setCounselorId(e.target.value)}
                    >
                      <MenuItem value="">— بعداً تخصیص می‌شود —</MenuItem>
                      {counselors?.items.map((o: IdName) => (
                        <MenuItem key={o.id} value={o.id}>{o.label}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <FormControl size="small" fullWidth>
                    <InputLabel>مرکز ارائه خدمت</InputLabel>
                    <Select
                      value={serviceLocationId}
                      label="مرکز ارائه خدمت"
                      onChange={(e) => setServiceLocationId(e.target.value)}
                    >
                      <MenuItem value="">—</MenuItem>
                      {locations?.map((l) => (
                        <MenuItem key={l.id} value={l.id}>{l.title} ({l.code})</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </>
              )}
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>بستن</Button>
          {row && !success && (
            <Button type="submit" variant="contained" disabled={busy}>
              {busy ? "در حال تبدیل…" : "تبدیل"}
            </Button>
          )}
        </DialogActions>
      </form>
    </Dialog>
  );
}
