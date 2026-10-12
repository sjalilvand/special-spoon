import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControl, InputLabel, MenuItem, Paper, Select, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TablePagination, TableRow, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { errDetail } from "../api/client";
import { createCounselor, fetchCounselors, fetchServiceLocations, updateCounselor } from "../api/people";
import { uploadCounselorPhoto } from "../api/siteops";
import type { Counselor } from "../api/people";
import JalaliDateField from "../components/JalaliDateField";

const STATUS: Record<string, { label: string; color: "success" | "default" | "warning" }> = {
  active: { label: "فعال", color: "success" },
  inactive: { label: "غیرفعال", color: "default" },
  suspended: { label: "تعلیق", color: "warning" },
};

export default function CounselorsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [photoRow, setPhotoRow] = useState<Counselor | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["counselors", page, search],
    queryFn: () => fetchCounselors({ page: page + 1, search: search || undefined }),
  });

  const toggleStatus = useMutation({
    mutationFn: (row: Counselor) =>
      updateCounselor(row.id, { status: row.status === "active" ? "inactive" : "active" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["counselors"] }),
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Stack spacing={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center" gap={2} flexWrap="wrap">
        <Typography variant="h6" fontWeight={700}>مشاوران</Typography>
        <TextField size="small" label="جست‌وجو (کد یا نام)" value={search}
          onChange={(e) => { setPage(0); setSearch(e.target.value); }} sx={{ width: 280 }} />
        <Button variant="contained" onClick={() => setOpen(true)}>مشاور جدید</Button>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>کد</TableCell>
              <TableCell>نام</TableCell>
              <TableCell>تخصص</TableCell>
              <TableCell>شماره مجوز</TableCell>
              <TableCell>محل خدمت</TableCell>
              <TableCell>ظرفیت</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>حساب</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={9} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.map((row) => {
              const st = STATUS[row.status] ?? { label: row.status, color: "default" as const };
              return (
                <TableRow key={row.id}>
                  <TableCell>{row.counselor_code}</TableCell>
                  <TableCell>{row.first_name} {row.last_name}</TableCell>
                  <TableCell>{row.specialty ?? "—"}</TableCell>
                  <TableCell>{row.license_number ?? "—"}</TableCell>
                  <TableCell>{row.service_location_title ?? "—"}</TableCell>
                  <TableCell>{row.capacity ?? "—"}</TableCell>
                  <TableCell><Chip label={st.label} color={st.color} size="small" /></TableCell>
                  <TableCell>
                    <Chip size="small" variant="outlined" label={row.has_account ? "دارد" : "ندارد"} />
                  </TableCell>
                  <TableCell>
                    <Button size="small" onClick={() => {
                      if (window.confirm("تغییر وضعیت این مشاور؟")) toggleStatus.mutate(row);
                    }}>
                      {row.status === "active" ? "غیرفعال" : "فعال"}
                    </Button>
                    <Button size="small" onClick={() => setPhotoRow(row)}>عکس</Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <TablePagination component="div" count={data?.total ?? 0} page={page}
          onPageChange={(_, p) => setPage(p)} rowsPerPage={10} rowsPerPageOptions={[10]}
          labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`} />
      </TableContainer>

      <CreateDialog open={open} onClose={() => setOpen(false)} onError={setError} />
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        style={{ display: "none" }}
        onChange={async (e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (!f || !photoRow) return;
          if (f.size > 2 * 1024 * 1024) { setError("حجم عکس باید کمتر از ۲ مگابایت باشد"); setPhotoRow(null); return; }
          try {
            await uploadCounselorPhoto(photoRow.id, f);
            setError(null);
            alert("عکس مشاور ذخیره شد و در سایت عمومی نمایش داده می‌شود.");
            queryClient.invalidateQueries({ queryKey: ["counselors"] });
          } catch (err) {
            setError(errDetail(err));
          } finally {
            setPhotoRow(null);
          }
        }}
      />
    </Stack>
  );
}

function CreateDialog({ open, onClose, onError }: { open: boolean; onClose: () => void; onError: (m: string) => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({});
  const [createAccount, setCreateAccount] = useState(false);
  const [licenseExpiry, setLicenseExpiry] = useState<string | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const { data: locations } = useQuery({ queryKey: ["locations"], queryFn: fetchServiceLocations, enabled: open });

  useEffect(() => {
    if (open) { setForm({}); setCreateAccount(false); setFormError(null); setLicenseExpiry(undefined); }
  }, [open]);

  const set = (k: string) => (e: { target: { value: string } }) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await createCounselor({
        counselor_code: form.counselor_code?.trim(),
        first_name: form.first_name?.trim(),
        last_name: form.last_name?.trim(),
        national_id: form.national_id?.trim() || undefined,
        professional_title: form.professional_title?.trim() || undefined,
        degree: form.degree?.trim() || undefined,
        specialty: form.specialty?.trim() || undefined,
        license_number: form.license_number?.trim() || undefined,
        license_expiry_date: licenseExpiry,
        work_mobile: form.work_mobile?.trim() || undefined,
        email: form.email?.trim() || undefined,
        capacity: form.capacity ? Number(form.capacity) : undefined,
        service_location_id: form.service_location_id || undefined,
        create_account: createAccount,
        username: createAccount ? form.username?.trim() : undefined,
      });
      await queryClient.invalidateQueries({ queryKey: ["counselors"] });
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
        <DialogTitle>مشاور جدید</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mb: 2 }}>{formError}</Alert>}
          <Stack spacing={2} mt={1}>
            <TextField label="کد مشاور *" value={form.counselor_code ?? ""} onChange={set("counselor_code")} required />
            <Stack direction="row" spacing={2} alignItems="center">
              <TextField label="نام *" fullWidth value={form.first_name ?? ""} onChange={set("first_name")} required />
              <TextField label="نام خانوادگی *" fullWidth value={form.last_name ?? ""} onChange={set("last_name")} required />
            </Stack>
            <TextField label="کد ملی (متن، ۱۰ رقم)" value={form.national_id ?? ""} onChange={set("national_id")} />
            <Stack direction="row" spacing={2} alignItems="center">
              <TextField label="عنوان حرفه‌ای" fullWidth value={form.professional_title ?? ""} onChange={set("professional_title")} />
              <TextField label="تخصص" fullWidth value={form.specialty ?? ""} onChange={set("specialty")} />
            </Stack>
            <Stack direction="row" spacing={2} alignItems="center">
              <TextField label="شماره مجوز" fullWidth value={form.license_number ?? ""} onChange={set("license_number")} />
              <TextField label="ظرفیت" type="number" fullWidth value={form.capacity ?? ""} onChange={set("capacity")} />
            </Stack>
            <JalaliDateField
              label="تاریخ اعتبار مجوز"
              value={undefined}
              onChange={(iso) => setLicenseExpiry(iso)}
            />
            </Stack>
            <TextField label="تماس کاری (متن)" value={form.work_mobile ?? ""} onChange={set("work_mobile")} />
            <FormControl fullWidth size="small">
              <InputLabel>محل خدمت</InputLabel>
              <Select value={form.service_location_id ?? ""} onChange={set("service_location_id")} label="محل خدمت">
                <MenuItem value="">—</MenuItem>
                {locations?.map((l) => <MenuItem key={l.id} value={l.id}>{l.title} ({l.code})</MenuItem>)}
              </Select>
            </FormControl>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input type="checkbox" checked={createAccount} onChange={(e) => setCreateAccount(e.target.checked)} />
              ایجاد حساب ورود (نقش ثابت مشاور — حساب «در انتظار فعال‌سازی» ساخته می‌شود)
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
