import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControl,
  InputLabel, ListItemText, MenuItem, OutlinedInput, Paper, Select, Stack, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { errDetail } from "../api/client";
import {
  Branch, createBranch, createClinic, fetchAllServices, fetchBranches, fetchClinics,
  setBranchOfferings, updateBranch,
} from "../api/branches";
import { IRAN_PROVINCES, findProvince } from "../constants/provinces";
import BranchMapPicker from "../components/BranchMapPicker";
import { formatJalaliDateTime } from "../utils/jalali";

// فاز ۲۹ - B31 سند جامع: مراکز مشاوره و شعب — slug یکتا، مختصات معتبر،
// شعبه منتشرنشده عمومی نیست، «خدمت ناموجود برای شعبه نشان داده نشود»
// فاز ۴۹: انتخاب استان ۳۱گانه + نقشه انتخاب موقعیت + ویرایش کامل شعبه

const fa = (n: number | string | null | undefined) =>
  n === null || n === undefined ? "—" : typeof n === "number" ? n.toLocaleString("fa-IR") : n;

const STATUS: Record<string, { label: string; color: "success" | "warning" }> = {
  published: { label: "منتشرشده", color: "success" },
  draft: { label: "پیش‌نویس", color: "warning" },
};

const FormGrid = ({ children }: { children: React.ReactNode }) => (
  <Box display="grid" gap={2} gridTemplateColumns={{ xs: "1fr", sm: "1fr 1fr" }}>
    {children}
  </Box>
);

export default function BranchesPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [selectedClinic, setSelectedClinic] = useState<string | null>(null);
  const [newClinicOpen, setNewClinicOpen] = useState(false);
  // فاز ۵۱: فرم شعبه در سطح صفحه — دکمهٔ «+ شعبه جدید» همیشه دیده می‌شود؛
  // اگر مرکزی انتخاب نشده باشد، راهنمای شفاف نشان داده می‌شود (رفع «امکان ثبت شعب نیست»)
  const [formTarget, setFormTarget] = useState<{ branch: Branch | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  const clinics = useQuery({ queryKey: ["clinics"], queryFn: fetchClinics });

  // فاز ۶۶د: تا وقتی مرکزی انتخاب نشده، جدول عمداً خالی است (فاز ۵۱) — اما
  // گزارش میدانی: کاربر فکر می‌کرد «هیچ کلینیکی لود نمی‌شود». حالا به‌محض
  // بارگذاری فهرست، اولین مرکز (ترتیب نام سرور) خودکار انتخاب می‌شود تا
  // فهرست شعب بی‌درنگ دیده شود؛ انتخاب دستی همچنان آزاد است (فقط یک‌بار،
  // با useRef، تا «همه / انتخاب کنید» دستی کاربر دوباره override نشود).
  const autoPicked = useRef(false);
  useEffect(() => {
    if (!autoPicked.current && !selectedClinic && (clinics.data?.length ?? 0) > 0) {
      autoPicked.current = true;
      setSelectedClinic(clinics.data![0].id);
    }
  }, [clinics.data, selectedClinic]);
  const branches = useQuery({
    queryKey: ["branches", selectedClinic],
    queryFn: () => fetchBranches(selectedClinic!),
    enabled: !!selectedClinic,
  });
  const services = useQuery({ queryKey: ["all-services"], queryFn: fetchAllServices });

  const createClinicMut = useMutation({
    mutationFn: createClinic,
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["clinics"] });
      setNewClinicOpen(false);
      setSelectedClinic(c.id);
      setOkMsg(`مرکز «${c.name}» ایجاد شد و انتخاب شد — اکنون با دکمهٔ «+ شعبه جدید» شعب این مرکز را ثبت کنید`);
      setError(null);
    },
    onError: (e) => setError(errDetail(e)),
  });

  const openBranchForm = () => {
    if (!selectedClinic) {
      setError("برای ثبت شعبه، ابتدا یک مرکز را از فهرست «مرکز» انتخاب کنید — یا با دکمهٔ «+ مرکز جدید» مرکز بسازید؛ پس از انتخاب مرکز، ثبت شعبه فعال می‌شود.");
      setOkMsg(null);
      return;
    }
    setError(null);
    setFormTarget({ branch: null });
  };

  const publishMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "draft" | "published" }) =>
      updateBranch(id, { status }),
    onSuccess: (b) => {
      qc.invalidateQueries({ queryKey: ["branches", selectedClinic] });
      setOkMsg(b.status === "published" ? "شعبه منتشر شد و در صفحات عمومی دیده می‌شود" : "انتشار شعبه لغو شد");
    },
    onError: (e) => setError(errDetail(e)),
  });

  const clinic = clinics.data?.find((c) => c.id === selectedClinic) ?? null;

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={800}>شعب و مراکز (B31)</Typography>
        <Box flexGrow={1} />
        <Button variant="outlined" onClick={() => navigate("/branch-map")}>نمایش روی نقشه (B40)</Button>
        <FormControl size="small" sx={{ minWidth: 240 }}>
          <InputLabel>مرکز</InputLabel>
          <Select
            value={selectedClinic ?? ""}
            label="مرکز"
            onChange={(e) => setSelectedClinic((e.target.value as string) || null)}
          >
            <MenuItem value=""><em>— همه / انتخاب کنید —</em></MenuItem>
            {(clinics.data ?? []).map((c) => (
              <MenuItem key={c.id} value={c.id}>{c.name} ({c.slug})</MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button variant="contained" onClick={() => setNewClinicOpen(true)}>+ مرکز جدید</Button>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {clinics.isError && (
        <Alert severity="error">
          بارگذاری فهرست مراکز ناموفق بود{errDetail(clinics.error) ? `: ${errDetail(clinics.error)}` : ""}
        </Alert>
      )}
      {okMsg && <Alert severity="success" onClose={() => setOkMsg(null)}>{okMsg}</Alert>}

      {clinic && (
        <Paper sx={{ p: 2 }}>
          <Stack direction="row" alignItems="center" spacing={1.5} flexWrap="wrap" useFlexGap>
            <Box flexGrow={1} minWidth={220}>
              <Typography variant="subtitle1" fontWeight={700}>{clinic.name}</Typography>
              <Typography variant="body2" color="text.secondary">
                slug: <code>{clinic.slug}</code> · تلفن: {clinic.phone ?? "—"} · وب‌سایت: {clinic.website ?? "—"} ·
                {" "}وضعیت: {clinic.is_active ? "فعال" : "غیرفعال"} · تعداد شعب: {fa(clinic.branch_count)}
              </Typography>
            </Box>
            <Button variant="contained" onClick={openBranchForm}>+ ثبت شعبه برای این مرکز</Button>
          </Stack>
        </Paper>
      )}

      <BranchTable
        branches={branches.data ?? []}
        loading={branches.isLoading}
        services={(services.data ?? []).map((s) => ({ id: s.id, title: s.title }))}
        clinicId={selectedClinic}
        onAddBranch={openBranchForm}
        onEditBranch={(b) => { setError(null); setFormTarget({ branch: b }); }}
        onPublish={(b, status) => publishMut.mutate({ id: b.id, status })}
        onSaved={() => {
          qc.invalidateQueries({ queryKey: ["branches", selectedClinic] });
          setOkMsg("شعبه ذخیره شد");
          setError(null);
        }}
        onError={(m) => setError(m)}
      />

      {formTarget && selectedClinic && (
        <BranchFormDialog
          clinicId={selectedClinic}
          branch={formTarget.branch}
          services={(services.data ?? []).map((s) => ({ id: s.id, title: s.title }))}
          onClose={() => setFormTarget(null)}
          onSaved={() => {
            qc.invalidateQueries({ queryKey: ["branches", selectedClinic] });
            setOkMsg("شعبه ذخیره شد");
            setError(null);
          }}
          onError={(m) => setError(m)}
        />
      )}

      <NewClinicDialog
        open={newClinicOpen}
        onClose={() => setNewClinicOpen(false)}
        onSubmit={(payload) => createClinicMut.mutate(payload)}
        submitting={createClinicMut.isPending}
      />
    </Stack>
  );
}

/* ------------------------------ جدول شعب ------------------------------ */

function BranchTable(props: {
  branches: Branch[];
  loading: boolean;
  services: { id: string; title: string }[];
  clinicId: string | null;
  onAddBranch: () => void;
  onEditBranch: (b: Branch) => void;
  onPublish: (b: Branch, status: "draft" | "published") => void;
  onSaved: () => void;
  onError: (msg: string) => void;
}) {
  const [offeringsFor, setOfferingsFor] = useState<Branch | null>(null);
  return (
    <>
      {/* فاز ۵۱: دکمهٔ ثبت شعبه همیشه دیده می‌شود؛ بدون انتخاب مرکز، راهنما نشان داده می‌شود */}
      <Box display="flex" justifyContent="flex-end">
        <Button variant="contained" onClick={props.onAddBranch}>+ شعبه جدید</Button>
      </Box>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>شعبه</TableCell>
              <TableCell>استان / شهر</TableCell>
              <TableCell>نشانی</TableCell>
              <TableCell>مختصات</TableCell>
              <TableCell>خدمات</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>ایجاد</TableCell>
              <TableCell align="left">عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {props.loading && (
              <TableRow><TableCell colSpan={8}>در حال بارگذاری…</TableCell></TableRow>
            )}
            {!props.loading && props.branches.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} align="center">
                  <Stack spacing={0.5} alignItems="center" sx={{ py: 2 }}>
                    <Typography variant="body2">
                      {props.clinicId
                        ? "برای این مرکز هنوز شعبه‌ای ثبت نشده است — با دکمهٔ «+ شعبه جدید» اولین شعبه را اضافه کنید"
                        : "برای مشاهده و ثبت شعب، ابتدا یک مرکز را از فهرست «مرکز» در بالای صفحه انتخاب کنید"}
                    </Typography>
                    {!props.clinicId && (
                      <Typography variant="caption" color="text.secondary">
                        اگر مرکزی ندارید، با دکمهٔ «+ مرکز جدید» بسازید؛ پس از ایجاد، مرکز به‌طور خودکار انتخاب می‌شود.
                      </Typography>
                    )}
                  </Stack>
                </TableCell>
              </TableRow>
            )}
            {props.branches.map((b) => (
              <TableRow key={b.id} hover>
                <TableCell>{b.name}</TableCell>
                <TableCell>{b.province ?? "—"} / {b.city ?? "—"}</TableCell>
                <TableCell sx={{ maxWidth: 220 }}>{b.address ?? "—"}</TableCell>
                <TableCell sx={{ direction: "ltr", fontSize: 12 }}>
                  {b.latitude !== null && b.longitude !== null
                    ? `${Number(b.latitude).toFixed(4)}, ${Number(b.longitude).toFixed(4)}`
                    : "—"}
                </TableCell>
                <TableCell>
                  {(b.services ?? []).map((s) => (
                    <Chip key={s.id} size="small" sx={{ mx: 0.25 }} label={s.title} />
                  ))}
                  {(b.services ?? []).length === 0 && "—"}
                </TableCell>
                <TableCell>
                  <Chip size="small" color={STATUS[b.status]?.color ?? "default"} label={STATUS[b.status]?.label ?? b.status} />
                </TableCell>
                <TableCell>{formatJalaliDateTime(b.created_at)}</TableCell>
                <TableCell align="left">
                  <Stack direction="row" spacing={0.5}>
                    <Button size="small" onClick={() => props.onEditBranch(b)}>ویرایش</Button>
                    <Button size="small" onClick={() => setOfferingsFor(b)}>خدمات</Button>
                    <Button
                      size="small"
                      color={b.status === "published" ? "warning" : "success"}
                      onClick={() => props.onPublish(b, b.status === "published" ? "draft" : "published")}
                    >
                      {b.status === "published" ? "لغو انتشار" : "انتشار"}
                    </Button>
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <OfferingsDialog
        branch={offeringsFor}
        services={props.services}
        onClose={() => setOfferingsFor(null)}
        onSaved={props.onSaved}
        onError={props.onError}
      />
    </>
  );
}

/* --------------------- دیالوگ ایجاد/ویرایش شعبه (با نقشه) --------------------- */

function BranchFormDialog(props: {
  clinicId: string;
  branch: Branch | null;
  services: { id: string; title: string }[];
  onClose: () => void;
  onSaved: () => void;
  onError: (msg: string) => void;
}) {
  const qc = useQueryClient();
  const editing = props.branch !== null;
  const [name, setName] = useState(props.branch?.name ?? "");
  const [province, setProvince] = useState(props.branch?.province ?? "");
  const [city, setCity] = useState(props.branch?.city ?? "");
  const [address, setAddress] = useState(props.branch?.address ?? "");
  const [postalCode, setPostalCode] = useState(props.branch?.postal_code ?? "");
  const [phone, setPhone] = useState(props.branch?.phone ?? "");
  const [latitude, setLatitude] = useState<number | null>(
    props.branch?.latitude != null ? Number(props.branch.latitude) : null);
  const [longitude, setLongitude] = useState<number | null>(
    props.branch?.longitude != null ? Number(props.branch.longitude) : null);
  const [serviceIds, setServiceIds] = useState<string[]>([]);
  const [publish, setPublish] = useState(props.branch?.status === "published");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const onProvinceChange = (p: string) => {
    setProvince(p);
    const info = findProvince(p);
    if (info) {
      if (!city.trim()) setCity(info.capital);
      setLatitude(info.lat);
      setLongitude(info.lng);
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      if (editing) {
        await updateBranch(props.branch!.id, {
          name: name.trim(),
          province: province || undefined,
          city: city || undefined,
          address: address || undefined,
          postal_code: postalCode || undefined,
          phone: phone || undefined,
          latitude: latitude ?? undefined,
          longitude: longitude ?? undefined,
          status: publish ? "published" : "draft",
        });
      } else {
        await createBranch(props.clinicId, {
          name: name.trim(),
          province: province || undefined,
          city: city || undefined,
          address: address || undefined,
          postal_code: postalCode || undefined,
          phone: phone || undefined,
          latitude: latitude ?? undefined,
          longitude: longitude ?? undefined,
          status: publish ? "published" : "draft",
          service_ids: serviceIds,
        });
      }
      qc.invalidateQueries({ queryKey: ["branches"] });
      props.onSaved();
      props.onClose();
    } catch (e) {
      setFormError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onClose={props.onClose} maxWidth="md" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>{editing ? `ویرایش شعبه — ${props.branch!.name}` : "شعبه جدید"}</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mb: 2 }}>{formError}</Alert>}
          <Stack spacing={2} sx={{ mt: 1 }}>
            <FormGrid>
              <TextField required label="نام شعبه *" value={name} onChange={(e) => setName(e.target.value)} />
              <TextField
                select label="استان" value={province}
                onChange={(e) => onProvinceChange(e.target.value)}
                helperText="انتخاب استان، شهر و مختصات پیش‌فرض (مرکز استان) را پر می‌کند"
              >
                <MenuItem value="">—</MenuItem>
                {IRAN_PROVINCES.map((p) => (
                  <MenuItem key={p.name} value={p.name}>{p.name}</MenuItem>
                ))}
              </TextField>
              <TextField label="شهر" value={city} onChange={(e) => setCity(e.target.value)} />
              <TextField label="کدپستی" value={postalCode} onChange={(e) => setPostalCode(e.target.value)} />
              <TextField label="تلفن" value={phone} onChange={(e) => setPhone(e.target.value)} slotProps={{ htmlInput: { dir: "ltr" } }} />
              <TextField
                label="وضعیت انتشار" select value={publish ? "published" : "draft"}
                onChange={(e) => setPublish(e.target.value === "published")}
              >
                <MenuItem value="draft">پیش‌نویس (عمومی نمی‌شود)</MenuItem>
                <MenuItem value="published">منتشرشده (در سایت/نقشه)</MenuItem>
              </TextField>
              <Box sx={{ gridColumn: "1 / -1" }}>
                <TextField
                  label="نشانی" multiline minRows={2} fullWidth
                  value={address} onChange={(e) => setAddress(e.target.value)}
                />
              </Box>
              <TextField
                label="عرض جغرافیایی (−۹۰ تا ۹۰)" type="number"
                value={latitude ?? ""} onChange={(e) => setLatitude(e.target.value === "" ? null : Number(e.target.value))}
                slotProps={{ htmlInput: { step: "any", min: -90, max: 90, dir: "ltr" } }}
              />
              <TextField
                label="طول جغرافیایی (−۱۸۰ تا ۱۸۰)" type="number"
                value={longitude ?? ""} onChange={(e) => setLongitude(e.target.value === "" ? null : Number(e.target.value))}
                slotProps={{ htmlInput: { step: "any", min: -180, max: 180, dir: "ltr" } }}
              />
            </FormGrid>

            <BranchMapPicker lat={latitude} lng={longitude} onChange={(la, lo) => { setLatitude(la); setLongitude(lo); }} />

            {!editing && (
              <FormControl fullWidth size="small">
                <InputLabel>خدمات ارائه‌شده</InputLabel>
                <Select
                  multiple
                  value={serviceIds}
                  onChange={(e) => setServiceIds(e.target.value as string[])}
                  input={<OutlinedInput label="خدمات ارائه‌شده" />}
                  renderValue={(picked) =>
                    props.services.filter((s) => (picked as string[]).includes(s.id)).map((s) => s.title).join("، ")
                  }
                >
                  {props.services.map((s) => (
                    <MenuItem key={s.id} value={s.id}><ListItemText primary={s.title} /></MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={props.onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy || !name.trim()}>
            {busy ? "در حال ذخیره…" : editing ? "ذخیره تغییرات" : "ایجاد شعبه"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

/* ------------------------------ دیالوگ خدمات شعبه ------------------------------ */

function OfferingsDialog(props: {
  branch: Branch | null;
  services: { id: string; title: string }[];
  onClose: () => void;
  onSaved: () => void;
  onError: (msg: string) => void;
}) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string[]>([]);
  const [initializedFor, setInitializedFor] = useState<string | null>(null);

  if (props.branch && initializedFor !== props.branch.id) {
    setInitializedFor(props.branch.id);
    setSelected((props.branch.services ?? []).map((s) => s.id));
  }
  if (!props.branch && initializedFor !== null) {
    setInitializedFor(null);
  }

  const mut = useMutation({
    mutationFn: () => setBranchOfferings(props.branch!.id, selected),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["branches"] });
      props.onSaved();
      props.onClose();
    },
    onError: (e) => props.onError(errDetail(e)),
  });

  return (
    <Dialog open={!!props.branch} onClose={props.onClose} maxWidth="sm" fullWidth>
      <DialogTitle>خدمات شعبه «{props.branch?.name}»</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          فقط خدمت‌های انتخابیِ فعال در صفحات عمومی این شعبه نشان داده می‌شود (پذیرش B31).
        </Typography>
        <FormControl fullWidth size="small">
          <InputLabel>خدمات</InputLabel>
          <Select
            multiple
            value={selected}
            onChange={(e) => setSelected(e.target.value as string[])}
            input={<OutlinedInput label="خدمات" />}
            renderValue={(picked) =>
              props.services.filter((s) => (picked as string[]).includes(s.id)).map((s) => s.title).join("، ")
            }
          >
            {props.services.map((s) => (
              <MenuItem key={s.id} value={s.id}>
                <ListItemText primary={s.title} />
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </DialogContent>
      <DialogActions>
        <Button onClick={props.onClose}>انصراف</Button>
        <Button variant="contained" disabled={mut.isPending} onClick={() => mut.mutate()}>
          ذخیره
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/* ------------------------------ دیالوگ مرکز جدید ------------------------------ */

function NewClinicDialog(props: {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: Record<string, unknown>) => void;
  submitting: boolean;
}) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [phone, setPhone] = useState("");
  const [website, setWebsite] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    props.onSubmit({
      name, slug: slug.trim().toLowerCase(),
      description: description || undefined,
      phone: phone || undefined,
      website: website || undefined,
    });
  };

  return (
    <Dialog open={props.open} onClose={props.onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>مرکز جدید (B31)</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField required label="نام مرکز" value={name} onChange={(e) => setName(e.target.value)} />
            <TextField
              required label="slug (یکینامه عمومی)" value={slug}
              onChange={(e) => setSlug(e.target.value)}
              helperText="فقط حروف کوچک لاتین، عدد و خط تیره — مثل rose-clinic"
              slotProps={{ htmlInput: { dir: "ltr" } }}
            />
            <TextField label="شرح" multiline minRows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
            <TextField label="تلفن" value={phone} onChange={(e) => setPhone(e.target.value)} />
            <TextField label="وب‌سایت" value={website} onChange={(e) => setWebsite(e.target.value)} slotProps={{ htmlInput: { dir: "ltr" } }} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={props.onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={props.submitting}>ایجاد</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
