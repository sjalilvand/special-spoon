import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControl,
  InputLabel, ListItemText, MenuItem, OutlinedInput, Paper, Select, Stack, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { errDetail } from "../api/client";
import {
  Branch, createBranch, createClinic, fetchAllServices, fetchBranches, fetchClinics,
  setBranchOfferings, updateBranch,
} from "../api/branches";
import { formatJalaliDateTime } from "../utils/jalali";

// فاز ۲۹ - B31 سند جامع: مراکز مشاوره و شعب — slug یکتا، مختصات معتبر،
// شعبه منتشرنشده عمومی نیست، «خدمت ناموجود برای شعبه نشان داده نشود»

const fa = (n: number | string | null | undefined) =>
  n === null || n === undefined ? "—" : typeof n === "number" ? n.toLocaleString("fa-IR") : n;

const STATUS: Record<string, { label: string; color: "success" | "warning" }> = {
  published: { label: "منتشرشده", color: "success" },
  draft: { label: "پیش‌نویس", color: "warning" },
};

export default function BranchesPage() {
  const qc = useQueryClient();
  const [selectedClinic, setSelectedClinic] = useState<string | null>(null);
  const [newClinicOpen, setNewClinicOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  const clinics = useQuery({ queryKey: ["clinics"], queryFn: fetchClinics });
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
      setOkMsg(`مرکز «${c.name}» ایجاد شد`);
      setError(null);
    },
    onError: (e) => setError(errDetail(e)),
  });

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
      {okMsg && <Alert severity="success" onClose={() => setOkMsg(null)}>{okMsg}</Alert>}

      {clinic && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={700}>{clinic.name}</Typography>
          <Typography variant="body2" color="text.secondary">
            slug: <code>{clinic.slug}</code> · تلفن: {clinic.phone ?? "—"} · وب‌سایت: {clinic.website ?? "—"} ·
            {" "}وضعیت: {clinic.is_active ? "فعال" : "غیرفعال"} · تعداد شعب: {fa(clinic.branch_count)}
          </Typography>
        </Paper>
      )}

      <BranchTable
        branches={branches.data ?? []}
        loading={branches.isLoading}
        services={(services.data ?? []).map((s) => ({ id: s.id, title: s.title }))}
        onPublish={(b, status) => publishMut.mutate({ id: b.id, status })}
        onSaved={() => {
          qc.invalidateQueries({ queryKey: ["branches", selectedClinic] });
          setOkMsg("شعبه ذخیره شد");
          setError(null);
        }}
        onError={(m) => setError(m)}
        clinicId={selectedClinic}
      />

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
  onPublish: (b: Branch, status: "draft" | "published") => void;
  onSaved: () => void;
  onError: (msg: string) => void;
}) {
  const [offeringsFor, setOfferingsFor] = useState<Branch | null>(null);
  const [newBranchOpen, setNewBranchOpen] = useState(false);
  return (
    <>
      {props.clinicId && (
        <Box display="flex" justifyContent="flex-end">
          <Button variant="outlined" onClick={() => setNewBranchOpen(true)}>+ شعبه جدید</Button>
        </Box>
      )}
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
                <TableCell colSpan={8}>
                  {props.clinicId ? "شعبه‌ای ثبت نشده است" : "برای مشاهده شعب، یک مرکز انتخاب کنید"}
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
      <NewBranchDialog
        open={newBranchOpen}
        clinicId={props.clinicId}
        services={props.services}
        onClose={() => setNewBranchOpen(false)}
        onSaved={props.onSaved}
        onError={props.onError}
      />
    </>
  );
}

/* ------------------------------ دیالوگ شعبه جدید ------------------------------ */

function NewBranchDialog(props: {
  open: boolean;
  clinicId: string | null;
  services: { id: string; title: string }[];
  onClose: () => void;
  onSaved: () => void;
  onError: (msg: string) => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [province, setProvince] = useState("");
  const [city, setCity] = useState("");
  const [address, setAddress] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [phone, setPhone] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [serviceIds, setServiceIds] = useState<string[]>([]);
  const [publish, setPublish] = useState(false);
  const [busy, setBusy] = useState(false);

  const reset = () => {
    setName(""); setProvince(""); setCity(""); setAddress(""); setPostalCode("");
    setPhone(""); setLatitude(""); setLongitude(""); setServiceIds([]); setPublish(false);
  };

  const submit = async () => {
    if (!props.clinicId || !name.trim()) return;
    setBusy(true);
    try {
      await createBranch(props.clinicId, {
        name: name.trim(),
        province: province || undefined,
        city: city || undefined,
        address: address || undefined,
        postal_code: postalCode || undefined,
        phone: phone || undefined,
        latitude: latitude === "" ? undefined : Number(latitude),
        longitude: longitude === "" ? undefined : Number(longitude),
        status: publish ? "published" : "draft",
        service_ids: serviceIds,
      });
      qc.invalidateQueries({ queryKey: ["branches"] });
      props.onSaved();
      reset();
      props.onClose();
    } catch (e) {
      props.onError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={props.open && !!props.clinicId} onClose={props.onClose} maxWidth="sm" fullWidth>
      <DialogTitle>شعبه جدید</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField required label="نام شعبه" value={name} onChange={(e) => setName(e.target.value)} />
          <Stack direction="row" spacing={2}>
            <TextField label="استان" fullWidth value={province} onChange={(e) => setProvince(e.target.value)} />
            <TextField label="شهر" fullWidth value={city} onChange={(e) => setCity(e.target.value)} />
          </Stack>
          <TextField label="نشانی" multiline minRows={2} value={address} onChange={(e) => setAddress(e.target.value)} />
          <Stack direction="row" spacing={2}>
            <TextField label="کدپستی" fullWidth value={postalCode} onChange={(e) => setPostalCode(e.target.value)} />
            <TextField label="تلفن" fullWidth value={phone} onChange={(e) => setPhone(e.target.value)} />
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField
              label="عرض جغرافیایی (−۹۰ تا ۹۰)" fullWidth type="number"
              value={latitude} onChange={(e) => setLatitude(e.target.value)}
              slotProps={{ htmlInput: { step: "any", min: -90, max: 90, dir: "ltr" } }}
            />
            <TextField
              label="طول جغرافیایی (−۱۸۰ تا ۱۸۰)" fullWidth type="number"
              value={longitude} onChange={(e) => setLongitude(e.target.value)}
              slotProps={{ htmlInput: { step: "any", min: -180, max: 180, dir: "ltr" } }}
            />
          </Stack>
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
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={props.onClose}>انصراف</Button>
        <Button variant="contained" disabled={busy || !name.trim()} onClick={submit}>ایجاد شعبه</Button>
      </DialogActions>
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
