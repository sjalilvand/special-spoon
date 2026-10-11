import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControl, InputLabel, MenuItem, Paper, Select, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TablePagination, TableRow, TextField, Typography,
} from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { errDetail } from "../api/client";
import { createApplicant, fetchApplicants, fetchOrgUnits, fetchServiceLocations } from "../api/people";

export default function ApplicantsPage() {
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["applicants", page, search],
    queryFn: () => fetchApplicants({ page: page + 1, search: search || undefined }),
  });

  return (
    <Stack spacing={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center" gap={2} flexWrap="wrap">
        <Typography variant="h6" fontWeight={700}>متقاضیان</Typography>
        <TextField size="small" label="جست‌وجو (نام، کد ملی، پرسنلی، شناسه)" value={search}
          onChange={(e) => { setPage(0); setSearch(e.target.value); }} sx={{ width: 320 }} />
        <Button variant="contained" onClick={() => setOpen(true)}>متقاضی جدید</Button>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>شناسه</TableCell>
              <TableCell>پرسنلی</TableCell>
              <TableCell>کد ملی</TableCell>
              <TableCell>نام</TableCell>
              <TableCell>موبایل</TableCell>
              <TableCell>واحد</TableCell>
              <TableCell>منبع</TableCell>
              <TableCell>وضعیت</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={8} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.external_id ?? "—"}</TableCell>
                <TableCell>{row.employee_code ?? "—"}</TableCell>
                <TableCell>{row.national_id ?? "—"}</TableCell>
                <TableCell>{row.first_name} {row.last_name}</TableCell>
                <TableCell>{row.mobile ?? "—"}</TableCell>
                <TableCell>{row.unit_title ?? "—"}</TableCell>
                <TableCell><Chip size="small" variant="outlined" label={row.record_source === "excel" ? "اکسل" : "دستی"} /></TableCell>
                <TableCell>
                  <Chip size="small" color={row.status === "active" ? "success" : "default"}
                    label={row.status === "active" ? "فعال" : row.status === "archived" ? "بایگانی" : "غیرفعال"} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <TablePagination component="div" count={data?.total ?? 0} page={page}
          onPageChange={(_, p) => setPage(p)} rowsPerPage={10} rowsPerPageOptions={[10]}
          labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`} />
      </TableContainer>

      <CreateDialog open={open} onClose={() => setOpen(false)} onError={setError} />
    </Stack>
  );
}

function CreateDialog({ open, onClose, onError }: { open: boolean; onClose: () => void; onError: (m: string) => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({});
  const [createAccount, setCreateAccount] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const { data: units } = useQuery({ queryKey: ["units"], queryFn: fetchOrgUnits, enabled: open });
  const { data: locations } = useQuery({ queryKey: ["locations"], queryFn: fetchServiceLocations, enabled: open });

  useEffect(() => {
    if (open) { setForm({}); setCreateAccount(false); setFormError(null); }
  }, [open]);

  const set = (k: string) => (e: { target: { value: string } }) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await createApplicant({
        first_name: form.first_name?.trim(),
        last_name: form.last_name?.trim(),
        external_id: form.external_id?.trim() || undefined,
        employee_code: form.employee_code?.trim() || undefined,
        national_id: form.national_id?.trim() || undefined,
        birth_date: form.birth_date?.trim() || undefined,
        gender: form.gender || undefined,
        mobile: form.mobile?.trim() || undefined,
        unit_id: form.unit_id || undefined,
        service_location_id: form.service_location_id || undefined,
        referral_source: form.referral_source?.trim() || undefined,
        create_account: createAccount,
        username: createAccount ? form.username?.trim() : undefined,
      });
      await queryClient.invalidateQueries({ queryKey: ["applicants"] });
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
        <DialogTitle>متقاضی جدید</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            حداقل یکی از شناسه‌ها (شناسه جایگزین / پرسنلی / کد ملی) الزامی است.
          </Typography>
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          <Stack spacing={2} mt={1}>
            <Stack direction="row" spacing={2}>
              <TextField label="نام *" fullWidth value={form.first_name ?? ""} onChange={set("first_name")} required />
              <TextField label="نام خانوادگی *" fullWidth value={form.last_name ?? ""} onChange={set("last_name")} required />
            </Stack>
            <Stack direction="row" spacing={2}>
              <TextField label="شناسه جایگزین (متن)" fullWidth value={form.external_id ?? ""} onChange={set("external_id")} />
              <TextField label="شماره پرسنلی (متن)" fullWidth value={form.employee_code ?? ""} onChange={set("employee_code")} />
            </Stack>
            <Stack direction="row" spacing={2}>
              <TextField label="کد ملی (متن، ۱۰ رقم)" fullWidth value={form.national_id ?? ""} onChange={set("national_id")} />
              <TextField label="تاریخ تولد (۱۳۷۰/۰۳/۲۱)" fullWidth value={form.birth_date ?? ""} onChange={set("birth_date")} />
            </Stack>
            <Stack direction="row" spacing={2}>
              <TextField label="موبایل (متن)" fullWidth value={form.mobile ?? ""} onChange={set("mobile")} />
              <FormControl fullWidth size="small">
                <InputLabel>جنسیت</InputLabel>
                <Select value={form.gender ?? ""} onChange={set("gender")} label="جنسیت">
                  <MenuItem value="">—</MenuItem>
                  <MenuItem value="male">مرد</MenuItem>
                  <MenuItem value="female">زن</MenuItem>
                </Select>
              </FormControl>
            </Stack>
            <Stack direction="row" spacing={2}>
              <FormControl fullWidth size="small">
                <InputLabel>واحد سازمانی</InputLabel>
                <Select value={form.unit_id ?? ""} onChange={set("unit_id")} label="واحد سازمانی">
                  <MenuItem value="">—</MenuItem>
                  {units?.map((u) => <MenuItem key={u.id} value={u.id}>{u.title} ({u.code})</MenuItem>)}
                </Select>
              </FormControl>
              <FormControl fullWidth size="small">
                <InputLabel>محل خدمت</InputLabel>
                <Select value={form.service_location_id ?? ""} onChange={set("service_location_id")} label="محل خدمت">
                  <MenuItem value="">—</MenuItem>
                  {locations?.map((l) => <MenuItem key={l.id} value={l.id}>{l.title} ({l.code})</MenuItem>)}
                </Select>
              </FormControl>
            </Stack>
            <TextField label="منبع ارجاع" value={form.referral_source ?? ""} onChange={set("referral_source")} />
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input type="checkbox" checked={createAccount} onChange={(e) => setCreateAccount(e.target.checked)} />
              ایجاد حساب ورود (نقش ثابت متقاضی)
            </label>
            {createAccount && (
              <TextField label="نام کاربری حساب *" value={form.username ?? ""} onChange={set("username")} required />
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>{busy ? "در حال ثبت…" : "ایجاد"}</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
