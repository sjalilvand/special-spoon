import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControl, FormControlLabel, Grid, InputLabel, MenuItem, Paper, Select, Stack, Switch,
  Table, TableBody, TableCell, TableContainer, TableHead, TablePagination, TableRow, TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { errDetail } from "../api/client";
import JalaliDateField from "../components/JalaliDateField";
import {
  createService, createSpecialty, createTariff, fetchQuote, fetchServices, fetchSpecialties,
  fetchTariffs, updateService, updateTariff,
} from "../api/catalog";
import type { PricingQuote, Service, TariffVersion } from "../api/catalog";

// فاز ۲۸ - B06/B07 سند جامع: خدمت (تخصص، مدت مثبت، نوع جلسه، وضعیت ارائه)
// و تعرفه نسخه‌دار (مبلغ، ارز، بازه اعتبار؛ هم‌پوشانی ممنوع؛ قیمت گذشته ثابت)

const SESSION_TYPE: Record<string, string> = {
  in_person: "حضوری",
  online: "برخط",
  phone: "تلفنی",
};

const SERVICE_STATUS: Record<string, { label: string; color: "success" | "default" }> = {
  active: { label: "فعال", color: "success" },
  inactive: { label: "غیرفعال", color: "default" },
};

const fa = (n: number | string | null | undefined) =>
  n === null || n === undefined ? "—" : typeof n === "number" ? n.toLocaleString("fa-IR") : n;

export default function ServicesPage() {
  const [tab, setTab] = useState<"services" | "tariffs">("services");
  return (
    <Stack spacing={2}>
      <Box display="flex" gap={1}>
        <Button variant={tab === "services" ? "contained" : "text"} onClick={() => setTab("services")}>
          خدمات و تخصص‌ها (B06)
        </Button>
        <Button variant={tab === "tariffs" ? "contained" : "text"} onClick={() => setTab("tariffs")}>
          تعرفه نسخه‌دار (B07)
        </Button>
      </Box>
      {tab === "services" ? <ServicesTab /> : <TariffsTab />}
    </Stack>
  );
}

/* ------------------------------ خدمات ------------------------------ */

function ServicesTab() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [openService, setOpenService] = useState(false);
  const [openSpecialty, setOpenSpecialty] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["services", page, search, statusFilter],
    queryFn: () => fetchServices({ page: page + 1, search: search || undefined, status: statusFilter || undefined }),
  });

  const toggleStatus = useMutation({
    mutationFn: (row: Service) =>
      updateService(row.id, { status: row.status === "active" ? "inactive" : "active" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["services"] }),
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Stack spacing={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center" gap={2} flexWrap="wrap">
        <Typography variant="h6" fontWeight={700}>خدمات</Typography>
        <TextField size="small" label="جست‌وجو عنوان" value={search}
          onChange={(e) => { setPage(0); setSearch(e.target.value); }} sx={{ width: 220 }} />
        <FormControl size="small" sx={{ width: 150 }}>
          <InputLabel>وضعیت</InputLabel>
          <Select value={statusFilter} label="وضعیت" onChange={(e) => { setPage(0); setStatusFilter(e.target.value); }}>
            <MenuItem value="">همه</MenuItem>
            <MenuItem value="active">فعال</MenuItem>
            <MenuItem value="inactive">غیرفعال</MenuItem>
          </Select>
        </FormControl>
        <Button variant="outlined" onClick={() => setOpenSpecialty(true)}>تخصص جدید</Button>
        <Button variant="contained" onClick={() => setOpenService(true)}>خدمت جدید</Button>
      </Box>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>عنوان</TableCell>
              <TableCell>تخصص</TableCell>
              <TableCell>کد</TableCell>
              <TableCell>مدت (دقیقه)</TableCell>
              <TableCell>نوع جلسه</TableCell>
              <TableCell>قیمت جاری</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={8} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.map((row) => {
              const st = SERVICE_STATUS[row.status] ?? { label: row.status, color: "default" as const };
              return (
                <TableRow key={row.id}>
                  <TableCell>{row.title}</TableCell>
                  <TableCell>{row.specialty_name ?? "—"}</TableCell>
                  <TableCell>{row.code ?? "—"}</TableCell>
                  <TableCell>{fa(row.duration_minutes)}</TableCell>
                  <TableCell>{SESSION_TYPE[row.session_type] ?? row.session_type}</TableCell>
                  <TableCell>
                    {row.current_price !== null ? `${fa(row.current_price)} ${row.current_currency ?? ""}` : "—"}
                  </TableCell>
                  <TableCell><Chip label={st.label} color={st.color} size="small" /></TableCell>
                  <TableCell>
                    <Button size="small" onClick={() => {
                      if (window.confirm(row.status === "active"
                        ? "با غیرفعال‌سازی، این خدمت رزرو جدید نمی‌پذیرد. ادامه؟"
                        : "فعال‌سازی این خدمت؟")) {
                        toggleStatus.mutate(row);
                      }
                    }}>
                      {row.status === "active" ? "غیرفعال" : "فعال"}
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
            {!isLoading && data?.items.length === 0 && (
              <TableRow><TableCell colSpan={8} align="center">خدمتی ثبت نشده است</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
        <TablePagination component="div" count={data?.total ?? 0} page={page}
          onPageChange={(_, p) => setPage(p)} rowsPerPage={10} rowsPerPageOptions={[10]}
          labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`} />
      </TableContainer>

      <ServiceCreateDialog open={openService} onClose={() => setOpenService(false)} />
      <SpecialtyCreateDialog open={openSpecialty} onClose={() => setOpenSpecialty(false)} />
    </Stack>
  );
}

function ServiceCreateDialog({ open, onClose }: {
  open: boolean; onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const { data: specialties } = useQuery({ queryKey: ["specialties"], queryFn: () => fetchSpecialties(true), enabled: open });

  useEffect(() => { if (open) { setForm({}); setFormError(null); } }, [open]);
  const set = (k: string) => (e: { target: { value: string } }) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await createService({
        specialty_id: form.specialty_id,
        title: form.title?.trim(),
        duration_minutes: Number(form.duration_minutes),
        session_type: form.session_type || "in_person",
        code: form.code?.trim() || undefined,
        description: form.description?.trim() || undefined,
      });
      queryClient.invalidateQueries({ queryKey: ["services"] });
      onClose();
    } catch (e) {
      setFormError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>خدمت جدید (B06)</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {formError && <Alert severity="error">{formError}</Alert>}
            <FormControl size="small" required>
              <InputLabel>تخصص</InputLabel>
              <Select value={form.specialty_id ?? ""} label="تخصص" onChange={set("specialty_id")}>
                {(specialties ?? []).map((s) => (
                  <MenuItem key={s.id} value={s.id}>{s.name}{s.is_active ? "" : " (غیرفعال)"}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField size="small" required label="عنوان خدمت" value={form.title ?? ""} onChange={set("title")} />
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField size="small" required type="number" inputProps={{ min: 1, max: 600 }}
                  label="مدت (دقیقه)" value={form.duration_minutes ?? ""} onChange={set("duration_minutes")}
                  helperText="باید مثبت باشد" />
              </Grid>
              <Grid item xs={6}>
                <FormControl size="small" fullWidth>
                  <InputLabel>نوع جلسه</InputLabel>
                  <Select value={form.session_type ?? "in_person"} label="نوع جلسه" onChange={set("session_type")}>
                    <MenuItem value="in_person">حضوری</MenuItem>
                    <MenuItem value="online">برخط</MenuItem>
                    <MenuItem value="phone">تلفنی</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
            <TextField size="small" label="کد خدمت (اختیاری)" value={form.code ?? ""} onChange={set("code")} />
            <TextField size="small" multiline minRows={2} label="شرح (اختیاری)" value={form.description ?? ""} onChange={set("description")} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>ثبت</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function SpecialtyCreateDialog({ open, onClose }: {
  open: boolean; onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  useEffect(() => { if (open) { setName(""); setDescription(""); setFormError(null); } }, [open]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await createSpecialty({ name: name.trim(), description: description.trim() || undefined });
      queryClient.invalidateQueries({ queryKey: ["specialties"] });
      onClose();
    } catch (e) {
      setFormError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>تخصص جدید</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {formError && <Alert severity="error">{formError}</Alert>}
            <TextField size="small" required label="نام تخصص" value={name} onChange={(e) => setName(e.target.value)} />
            <TextField size="small" multiline minRows={2} label="شرح (اختیاری)" value={description}
              onChange={(e) => setDescription(e.target.value)} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>ثبت</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

/* ------------------------------ تعرفه‌ها ------------------------------ */

function TariffsTab() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [openCreate, setOpenCreate] = useState(false);

  const { data: servicesData } = useQuery({
    queryKey: ["services", "tariff-picker"],
    queryFn: () => fetchServices({ page: 1, status: "active" }),
  });
  const services = servicesData?.items ?? [];

  const { data: tariffs, isLoading } = useQuery({
    queryKey: ["tariffs", selected],
    queryFn: () => fetchTariffs(selected),
    enabled: !!selected,
  });

  const closeVersion = useMutation({
    mutationFn: (t: TariffVersion) => {
      const today = new Date().toISOString().slice(0, 10);
      const to = window.prompt(`بستن نسخه تعرفه تا تاریخ (ISO، امروز: ${today}):`, today);
      if (!to) throw new Error("لغو شد");
      return updateTariff(t.id, { valid_to: to });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tariffs", selected] }),
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Stack spacing={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center" gap={2} flexWrap="wrap">
        <Typography variant="h6" fontWeight={700}>تعرفه نسخه‌دار (B07)</Typography>
        <FormControl size="small" sx={{ minWidth: 260 }}>
          <InputLabel>خدمت</InputLabel>
          <Select value={selected} label="خدمت" onChange={(e) => setSelected(e.target.value)}>
            {services.map((s) => <MenuItem key={s.id} value={s.id}>{s.title}</MenuItem>)}
          </Select>
        </FormControl>
        <Button variant="contained" disabled={!selected} onClick={() => setOpenCreate(true)}>نسخه تعرفه جدید</Button>
      </Box>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      <Alert severity="info" variant="outlined">
        بازه‌های اعتبار هم‌پوشان برای یک خدمت پذیرفته نمی‌شود؛ نسخه باز-پایان (بدون تاریخ پایان) پیش از
        افزودن نسخه جدید باید بسته شود. قیمت نوبت‌های ثبت‌شده snapshot می‌ماند و با تغییر تعرفه تغییر نمی‌کند.
      </Alert>
      {selected && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>مبلغ</TableCell>
                <TableCell>ارز</TableCell>
                <TableCell>از تاریخ</TableCell>
                <TableCell>تا تاریخ</TableCell>
                <TableCell>یادداشت</TableCell>
                <TableCell>عملیات</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading && (
                <TableRow><TableCell colSpan={6} align="center"><CircularProgress size={24} /></TableCell></TableRow>
              )}
              {tariffs?.map((t) => (
                <TableRow key={t.id}>
                  <TableCell>{fa(t.amount)}</TableCell>
                  <TableCell>{t.currency}</TableCell>
                  <TableCell dir="ltr">{t.valid_from}</TableCell>
                  <TableCell dir="ltr">{t.valid_to ?? "بدون پایان"}</TableCell>
                  <TableCell>{t.note ?? "—"}</TableCell>
                  <TableCell>
                    {t.valid_to === null && (
                      <Button size="small" onClick={() => closeVersion.mutate(t)}>بستن بازه</Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {!isLoading && tariffs?.length === 0 && (
                <TableRow><TableCell colSpan={6} align="center">برای این خدمت تعرفه‌ای ثبت نشده است</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      {selected && <QuoteChecker serviceId={selected} />}
      <TariffCreateDialog open={openCreate} onClose={() => setOpenCreate(false)} serviceId={selected} />
    </Stack>
  );
}

function QuoteChecker({ serviceId }: { serviceId: string }) {
  const [date, setDate] = useState("");
  const [quote, setQuote] = useState<PricingQuote | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const check = async () => {
    setError(null);
    setQuote(null);
    setBusy(true);
    try {
      setQuote(await fetchQuote(serviceId, date || undefined));
    } catch (e) {
      setError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2" gutterBottom>استعلام قیمت (pricing/quote)</Typography>
      <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
        {/* فاز ۵۹: تقویم شمسی به‌جای ورودی میلادی */}
        <Box sx={{ width: 220 }}>
          <JalaliDateField label="تاریخ استعلام" value={date}
            onChange={(iso) => setDate(iso ?? new Date().toISOString().slice(0, 10))} />
        </Box>
        <Button variant="outlined" onClick={check} disabled={busy}>استعلام</Button>
        {quote && (
          <Typography variant="body2">
            قیمت در این تاریخ: <b>{fa(quote.amount)} {quote.currency}</b>
            {" "}（اعتبار {quote.valid_from} تا {quote.valid_to ?? "بدون پایان"}）
          </Typography>
        )}
      </Stack>
      {error && <Alert severity="warning" sx={{ mt: 1 }}>{error}</Alert>}
    </Paper>
  );
}

function TariffCreateDialog({ open, onClose, serviceId }: {
  open: boolean; onClose: () => void; serviceId: string;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({});
  const [openEnded, setOpenEnded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  useEffect(() => { if (open) { setForm({}); setOpenEnded(false); setFormError(null); } }, [open]);
  const set = (k: string) => (e: { target: { value: string } }) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await createTariff({
        service_id: serviceId,
        amount: Number(form.amount),
        currency: form.currency?.trim() || "IRR",
        valid_from: form.valid_from,
        valid_to: openEnded || !form.valid_to ? undefined : form.valid_to,
        note: form.note?.trim() || undefined,
      });
      queryClient.invalidateQueries({ queryKey: ["tariffs", serviceId] });
      onClose();
    } catch (e) {
      setFormError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>نسخه تعرفه جدید</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {formError && <Alert severity="error">{formError}</Alert>}
            <TextField size="small" required type="number" inputProps={{ min: 0 }} label="مبلغ" value={form.amount ?? ""} onChange={set("amount")} />
            <TextField size="small" label="ارز (پیش‌فرض IRR)" value={form.currency ?? ""} onChange={set("currency")} />
            {/* فاز ۵۹: تقویم شمسی برای اعتبار تعرفه */}
            <JalaliDateField label="اعتبار از" required value={form.valid_from ?? ""}
              onChange={(iso) => setForm((p) => ({ ...p, valid_from: iso ?? "" }))} />
            {!openEnded && (
              <JalaliDateField label="اعتبار تا (خالی = باز-پایان)" value={form.valid_to ?? ""}
                onChange={(iso) => setForm((p) => ({ ...p, valid_to: iso ?? "" }))} />
            )}
            <FormControlLabel control={<Switch checked={openEnded} onChange={(e) => setOpenEnded(e.target.checked)} />}
              label="بدون تاریخ پایان (باز-پایان)" />
            <TextField size="small" multiline minRows={2} label="یادداشت (اختیاری)" value={form.note ?? ""} onChange={set("note")} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>ثبت</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
