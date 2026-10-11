import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControl, InputLabel, MenuItem, Paper, Select, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TablePagination, TableRow, TextField, Typography,
} from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { errDetail } from "../api/client";
import {
  CASE_STATUS_META, CONSENT_META, PRIORITY_LABELS,
  createCase, fetchApplicantOptions, fetchCases, fetchCounselorOptions,
} from "../api/cases";
import { fetchServiceLocations } from "../api/people";

export default function CasesPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["cases", page, search, status],
    queryFn: () => fetchCases({ page: page + 1, search: search || undefined, status: status || undefined }),
  });

  return (
    <Stack spacing={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center" gap={2} flexWrap="wrap">
        <Typography variant="h6" fontWeight={700}>پرونده‌ها</Typography>
        <TextField size="small" label="جست‌وجو (شماره پرونده یا نام متقاضی)" value={search}
          onChange={(e) => { setPage(0); setSearch(e.target.value); }} sx={{ width: 300 }} />
        <FormControl size="small" sx={{ minWidth: 170 }}>
          <InputLabel>وضعیت</InputLabel>
          <Select value={status} label="وضعیت" onChange={(e) => { setPage(0); setStatus(e.target.value); }}>
            <MenuItem value="">همه</MenuItem>
            {Object.entries(CASE_STATUS_META).map(([k, v]) => (
              <MenuItem key={k} value={k}>{v.label}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button variant="contained" onClick={() => setOpen(true)}>پرونده جدید</Button>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>شماره پرونده</TableCell>
              <TableCell>متقاضی</TableCell>
              <TableCell>تاریخ پذیرش</TableCell>
              <TableCell>مشاور اصلی</TableCell>
              <TableCell>اولویت</TableCell>
              <TableCell>رضایت</TableCell>
              <TableCell>وضعیت</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={7} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.map((row) => {
              const st = CASE_STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
              const cs = CONSENT_META[row.consent_status] ?? { label: row.consent_status, color: "default" as const };
              return (
                <TableRow key={row.id} hover sx={{ cursor: "pointer" }}
                  onClick={() => navigate(`/cases/${row.id}`)}>
                  <TableCell>{row.case_number}</TableCell>
                  <TableCell>{row.applicant_name ?? "—"}</TableCell>
                  <TableCell>{new Date(row.acceptance_date).toLocaleDateString("fa-IR")}</TableCell>
                  <TableCell>{row.primary_counselor_name ?? "—"}</TableCell>
                  <TableCell>{PRIORITY_LABELS[row.priority] ?? row.priority}</TableCell>
                  <TableCell><Chip size="small" color={cs.color} label={cs.label} /></TableCell>
                  <TableCell><Chip size="small" color={st.color} label={st.label} /></TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <TablePagination component="div" count={data?.total ?? 0} page={page}
          onPageChange={(_, p) => setPage(p)} rowsPerPage={10} rowsPerPageOptions={[10]}
          labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`} />
      </TableContainer>

      {open && <CreateCaseDialog open={open} onClose={() => setOpen(false)} onError={setError} />}
    </Stack>
  );
}

function CreateCaseDialog({ open, onClose, onError }: { open: boolean; onClose: () => void; onError: (m: string) => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const { data: applicants } = useQuery({ queryKey: ["applicant-options"], queryFn: () => fetchApplicantOptions(), enabled: open });
  const { data: counselors } = useQuery({ queryKey: ["counselor-options"], queryFn: fetchCounselorOptions, enabled: open });
  const { data: locations } = useQuery({ queryKey: ["locations"], queryFn: fetchServiceLocations, enabled: open });

  useEffect(() => {
    if (open) { setForm({}); setFormError(null); }
  }, [open]);

  const set = (k: string) => (e: { target: { value: string } }) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!form.applicant_id) {
      setFormError("انتخاب متقاضی الزامی است");
      return;
    }
    setBusy(true);
    try {
      await createCase({
        applicant_id: form.applicant_id,
        service_location_id: form.service_location_id || undefined,
        service_type: form.service_type?.trim() || undefined,
        priority: form.priority || "normal",
        counselor_id: form.counselor_id || undefined,
        assignment_reason: form.counselor_id ? (form.assignment_reason?.trim() || undefined) : undefined,
      });
      await queryClient.invalidateQueries({ queryKey: ["cases"] });
      onClose();
    } catch (err) {
      setFormError(errDetail(err));
      onError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>تشکیل پرونده جدید</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            تاریخ پذیرش به‌صورت خودکار امروز ثبت می‌شود و شماره پرونده در سرور تولید می‌گردد.
          </Typography>
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          <Stack spacing={2} mt={2}>
            <FormControl size="small" required>
              <InputLabel>متقاضی *</InputLabel>
              <Select value={form.applicant_id ?? ""} onChange={set("applicant_id")} label="متقاضی *">
                <MenuItem value="">— انتخاب کنید —</MenuItem>
                {applicants?.items.map((o) => <MenuItem key={o.id} value={o.id}>{o.label}</MenuItem>)}
              </Select>
            </FormControl>
            <Stack direction="row" spacing={2}>
              <FormControl fullWidth size="small">
                <InputLabel>اولویت</InputLabel>
                <Select value={form.priority ?? "normal"} onChange={set("priority")} label="اولویت">
                  <MenuItem value="low">کم</MenuItem>
                  <MenuItem value="normal">عادی</MenuItem>
                  <MenuItem value="high">فوری</MenuItem>
                </Select>
              </FormControl>
              <TextField fullWidth size="small" label="نوع خدمت" value={form.service_type ?? ""} onChange={set("service_type")} />
            </Stack>
            <FormControl fullWidth size="small">
              <InputLabel>محل ارائه خدمت</InputLabel>
              <Select value={form.service_location_id ?? ""} onChange={set("service_location_id")} label="محل ارائه خدمت">
                <MenuItem value="">—</MenuItem>
                {locations?.map((l) => <MenuItem key={l.id} value={l.id}>{l.title} ({l.code})</MenuItem>)}
              </Select>
            </FormControl>
            <FormControl fullWidth size="small">
              <InputLabel>مشاور اصلی (اختیاری)</InputLabel>
              <Select value={form.counselor_id ?? ""} onChange={set("counselor_id")} label="مشاور اصلی (اختیاری)">
                <MenuItem value="">— بعداً تخصیص داده می‌شود —</MenuItem>
                {counselors?.items.map((o) => <MenuItem key={o.id} value={o.id}>{o.label}</MenuItem>)}
              </Select>
            </FormControl>
            {form.counselor_id && (
              <TextField size="small" label="علت تخصیص (اختیاری در تخصیص اولیه)"
                value={form.assignment_reason ?? ""} onChange={set("assignment_reason")} />
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>{busy ? "در حال ثبت…" : "تشکیل پرونده"}</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
