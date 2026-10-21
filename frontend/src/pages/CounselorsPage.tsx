import {
  Alert, Avatar, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, FormControl, InputLabel, MenuItem, Paper, Select, Stack, Table, TableBody,
  TableCell, TableContainer, TableHead, TablePagination, TableRow, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { errDetail } from "../api/client";
import { createCounselor, fetchCounselors, fetchServiceLocations, updateCounselor } from "../api/people";
import type { Counselor } from "../api/people";
import { addCredential, fetchCredentials } from "../api/catalog";
import type { CounselorCredential } from "../api/catalog";
import { uploadCounselorPhoto } from "../api/siteops";
import JalaliDateField from "../components/JalaliDateField";
import { formatJalali } from "../utils/jalali";

const STATUS: Record<string, { label: string; color: "success" | "default" | "warning" }> = {
  active: { label: "فعال", color: "success" },
  inactive: { label: "غیرفعال", color: "default" },
  suspended: { label: "تعلیق", color: "warning" },
};

// فاز ۴۹: گرید واکنش‌گرای یکسان برای همه فرم‌های دیالوگ — در عرض کم،
// فیلدها تک‌ستونه می‌شوند و هیچ فیلدی (از جمله تاریخ) از کادر بیرون نمی‌زند.
export function FormGrid({ children, cols = 2 }: { children: React.ReactNode; cols?: 1 | 2 }) {
  return (
    <Box
      display="grid"
      gap={2}
      gridTemplateColumns={cols === 1 ? { xs: "1fr" } : { xs: "1fr", sm: "1fr 1fr" }}
      sx={{ "& > .full": { gridColumn: "1 / -1" } }}
    >
      {children}
    </Box>
  );
}

export default function CounselorsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [credentialsFor, setCredentialsFor] = useState<Counselor | null>(null);
  const [photoFor, setPhotoFor] = useState<Counselor | null>(null);

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
              <TableCell>عکس</TableCell>
              <TableCell>کد</TableCell>
              <TableCell>نام</TableCell>
              <TableCell>تخصص</TableCell>
              <TableCell>شماره مجوز</TableCell>
              <TableCell>محل خدمت</TableCell>
              <TableCell>ظرفیت</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>صلاحیت رزرو (B05)</TableCell>
              <TableCell>حساب</TableCell>
              <TableCell align="left">عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={11} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.map((row) => {
              const st = STATUS[row.status] ?? { label: row.status, color: "default" as const };
              return (
                <TableRow key={row.id}>
                  <TableCell>
                    <Avatar
                      src={`/api/v1/public/counselors/${row.id}/photo`}
                      alt={`${row.first_name} ${row.last_name}`}
                      sx={{ width: 34, height: 34, fontSize: 14, bgcolor: "secondary.main" }}
                    >
                      {row.first_name?.charAt(0) ?? "؟"}
                    </Avatar>
                  </TableCell>
                  <TableCell>{row.counselor_code}</TableCell>
                  <TableCell>{row.first_name} {row.last_name}</TableCell>
                  <TableCell>{row.specialty ?? "—"}</TableCell>
                  <TableCell>{row.license_number ?? "—"}</TableCell>
                  <TableCell>{row.service_location_title ?? "—"}</TableCell>
                  <TableCell>{row.capacity ?? "—"}</TableCell>
                  <TableCell><Chip label={st.label} color={st.color} size="small" /></TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5} alignItems="center">
                      <Chip size="small" variant="outlined"
                        color={row.bookable ? "success" : "warning"}
                        label={row.bookable ? "قابل رزرو" : "غیرقابل رزرو"} />
                      {(row.pending_credentials ?? 0) > 0 && (
                        <Chip size="small" color="info" label={`${row.pending_credentials} در انتظار`} />
                      )}
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Chip size="small" variant="outlined" label={row.has_account ? "دارد" : "ندارد"} />
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5}>
                      <Button size="small" onClick={() => setCredentialsFor(row)}>مدارک</Button>
                      <Button size="small" onClick={() => setPhotoFor(row)}>عکس</Button>
                      <Button size="small" onClick={() => {
                        if (window.confirm("تغییر وضعیت این مشاور؟")) toggleStatus.mutate(row);
                      }}>
                        {row.status === "active" ? "غیرفعال" : "فعال"}
                      </Button>
                    </Stack>
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
      {credentialsFor && (
        <CredentialsDialog counselor={credentialsFor} onClose={() => setCredentialsFor(null)} />
      )}
      {photoFor && (
        <PhotoDialog counselor={photoFor} onClose={() => setPhotoFor(null)} onError={setError} />
      )}
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
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>مشاور جدید</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mb: 2 }}>{formError}</Alert>}
          <Stack spacing={2} mt={1}>
            <FormGrid>
              <TextField label="کد مشاور *" value={form.counselor_code ?? ""} onChange={set("counselor_code")} required />
              <TextField label="کد ملی (متن، ۱۰ رقم)" value={form.national_id ?? ""} onChange={set("national_id")} />
              <TextField label="نام *" value={form.first_name ?? ""} onChange={set("first_name")} required />
              <TextField label="نام خانوادگی *" value={form.last_name ?? ""} onChange={set("last_name")} required />
              <TextField label="عنوان حرفه‌ای" value={form.professional_title ?? ""} onChange={set("professional_title")} />
              <TextField label="تخصص" value={form.specialty ?? ""} onChange={set("specialty")} />
              <TextField label="شماره مجوز" value={form.license_number ?? ""} onChange={set("license_number")} />
              <TextField label="ظرفیت" type="number" value={form.capacity ?? ""} onChange={set("capacity")} />
              <JalaliDateField
                label="تاریخ اعتبار مجوز"
                value={undefined}
                onChange={(iso) => setLicenseExpiry(iso)}
              />
              <TextField label="تماس کاری (متن)" value={form.work_mobile ?? ""} onChange={set("work_mobile")} />
              <TextField label="ایمیل" value={form.email ?? ""} onChange={set("email")} slotProps={{ htmlInput: { dir: "ltr" } }} />
              <FormControl fullWidth size="small">
                <InputLabel>محل خدمت</InputLabel>
                <Select value={form.service_location_id ?? ""} onChange={set("service_location_id")} label="محل خدمت">
                  <MenuItem value="">—</MenuItem>
                  {locations?.map((l) => <MenuItem key={l.id} value={l.id}>{l.title} ({l.code})</MenuItem>)}
                </Select>
              </FormControl>
            </FormGrid>
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

/* فاز ۲۸ - B05: مدیریت مدارک و صلاحیت مشاور — فاز ۴۹: فرم بازطراحی‌شده (گرید واکنش‌گرا) */
function CredentialsDialog({ counselor, onClose }: {
  counselor: Counselor; onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({});
  const [issuedAt, setIssuedAt] = useState<string | undefined>(undefined);
  const [expiresAt, setExpiresAt] = useState<string | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: creds, isLoading } = useQuery({
    queryKey: ["credentials", counselor.id],
    queryFn: () => fetchCredentials(counselor.id),
  });

  useEffect(() => {
    if (counselor.id) { setForm({}); setIssuedAt(undefined); setExpiresAt(undefined); setFormError(null); }
  }, [counselor.id]);

  const set = (k: string) => (e: { target: { value: string } }) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await addCredential(counselor.id, {
        kind: form.kind || "license",
        title: form.title?.trim(),
        license_number: form.license_number?.trim() || undefined,
        issued_at: issuedAt,
        expires_at: expiresAt,
      });
      setForm({});
      setIssuedAt(undefined);
      setExpiresAt(undefined);
      queryClient.invalidateQueries({ queryKey: ["credentials", counselor.id] });
      queryClient.invalidateQueries({ queryKey: ["counselors"] });
    } catch (e) {
      setFormError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const KIND: Record<string, string> = {
    license: "مجوز حرفه‌ای",
    degree: "مدرک تحصیلی",
    certificate: "گواهی‌نامه",
  };
  const CRED_STATUS: Record<string, { label: string; color: "warning" | "success" | "error" }> = {
    pending: { label: "در انتظار بررسی", color: "warning" },
    approved: { label: "تأییدشده", color: "success" },
    rejected: { label: "ردشده", color: "error" },
  };

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>مدارک و صلاحیت — {counselor.first_name} {counselor.last_name} (B05)</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {formError && <Alert severity="error">{formError}</Alert>}
          <form onSubmit={submit}>
            <FormGrid>
              <FormControl size="small" fullWidth>
                <InputLabel>نوع مدرک</InputLabel>
                <Select value={form.kind ?? "license"} onChange={set("kind")} label="نوع مدرک">
                  <MenuItem value="license">مجوز حرفه‌ای</MenuItem>
                  <MenuItem value="degree">مدرک تحصیلی</MenuItem>
                  <MenuItem value="certificate">گواهی‌نامه</MenuItem>
                </Select>
              </FormControl>
              <TextField size="small" required label="عنوان مدرک" value={form.title ?? ""} onChange={set("title")} />
              <TextField size="small" label="شماره مدرک" value={form.license_number ?? ""} onChange={set("license_number")} />
              <JalaliDateField label="تاریخ صدور" value={issuedAt} onChange={setIssuedAt} />
              <JalaliDateField label="تاریخ انقضا" value={expiresAt} onChange={setExpiresAt} />
              <Box sx={{ gridColumn: "1 / -1" }} display="flex" justifyContent="flex-end">
                <Button type="submit" variant="contained" disabled={busy}>افزودن مدرک</Button>
              </Box>
            </FormGrid>
          </form>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>نوع</TableCell>
                <TableCell>عنوان</TableCell>
                <TableCell>شماره</TableCell>
                <TableCell>انقضا</TableCell>
                <TableCell>وضعیت بررسی</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading && (
                <TableRow><TableCell colSpan={5} align="center"><CircularProgress size={20} /></TableCell></TableRow>
              )}
              {creds?.map((c: CounselorCredential) => {
                const st = CRED_STATUS[c.verification_status] ?? { label: c.verification_status, color: "default" as never };
                return (
                  <TableRow key={c.id}>
                    <TableCell>{KIND[c.kind] ?? c.kind}</TableCell>
                    <TableCell>{c.title}</TableCell>
                    <TableCell>{c.license_number ?? "—"}</TableCell>
                    <TableCell>{c.expires_at ? formatJalali(c.expires_at) : "—"}</TableCell>
                    <TableCell>
                      <Chip size="small" label={st.label} color={st.color} />
                      {c.review_note && (
                        <Typography variant="caption" display="block" color="text.secondary">{c.review_note}</Typography>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
              {!isLoading && creds?.length === 0 && (
                <TableRow><TableCell colSpan={5} align="center">مدرکی ثبت نشده است</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}

/* فاز ۴۹ - عکس مشاور: آپلود با پیش‌نمایش؛ خانم‌ها می‌توانند عکس با حجاب داشته باشند */
function PhotoDialog({ counselor, onClose, onError }: {
  counselor: Counselor; onClose: () => void; onError: (m: string) => void;
}) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const pick = (f: File | null) => {
    setFile(f);
    setPreview(f ? URL.createObjectURL(f) : null);
  };

  const submit = async () => {
    if (!file) return;
    setBusy(true);
    try {
      await uploadCounselorPhoto(counselor.id, file);
      await queryClient.invalidateQueries({ queryKey: ["counselors"] });
      onClose();
    } catch (e) {
      onError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>عکس مشاور — {counselor.first_name} {counselor.last_name}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }} alignItems="center">
          <Avatar
            src={preview ?? `/api/v1/public/counselors/${counselor.id}/photo`}
            sx={{ width: 140, height: 140, fontSize: 48, bgcolor: "secondary.main" }}
          >
            {counselor.first_name?.charAt(0) ?? "؟"}
          </Avatar>
          <Button variant="outlined" component="label">
            انتخاب تصویر (JPEG/PNG/WebP — حداکثر ۲MB)
            <input
              type="file" accept="image/jpeg,image/png,image/webp" hidden
              onChange={(e) => pick(e.target.files?.[0] ?? null)}
            />
          </Button>
          <Typography variant="caption" color="text.secondary">
            در سایت عمومی و پروفایل مشاور نمایش داده می‌شود. برای مشاوران خانم می‌توانید عکس با حجاب انتخاب کنید.
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" disabled={!file || busy} onClick={submit}>
          {busy ? "در حال بارگذاری…" : "بارگذاری"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
