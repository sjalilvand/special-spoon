// فاز ۳۳ - B21 سند جامع: سازمان‌ها/قرارداد/سهم پرداخت —
// slug و شناسه ملی یکتا، درصد/سقف/بازه اعتبار، وضعیت قرارداد،
// تقسیم سهم در سفارش snapshot می‌شود؛ مطالبه از سازمان گزارش می‌شود
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControl,
  InputLabel, ListItemText, MenuItem, OutlinedInput, Paper, Select, Snackbar, Stack, Switch,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { errDetail } from "../api/client";
import { fetchAllServices } from "../api/branches";
import {
  Contract, Organization, ReceivablesReport, createContract, createOrganization,
  fetchContracts, fetchOrganizations, fetchReceivables, updateContract, updateOrganization,
} from "../api/organizations";

const fa = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : typeof n === "number" ? n.toLocaleString("fa-IR") : n;

const C_STATUS: Record<string, { label: string; color: "success" | "warning" | "default" }> = {
  active: { label: "فعال", color: "success" },
  draft: { label: "پیش‌نویس", color: "warning" },
  terminated: { label: "ملغی", color: "default" },
};

export default function OrganizationsPage() {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [createOrgOpen, setCreateOrgOpen] = useState(false);
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [newContractFor, setNewContractFor] = useState<Organization | null>(null);
  const [receivablesOrg, setReceivablesOrg] = useState<Organization | null>(null);

  const orgs = useQuery({ queryKey: ["organizations"], queryFn: fetchOrganizations });
  const contracts = useQuery({
    queryKey: ["contracts", selectedOrg?.id],
    queryFn: () => fetchContracts(selectedOrg!.id),
    enabled: !!selectedOrg,
  });
  const services = useQuery({ queryKey: ["all-services"], queryFn: fetchAllServices });
  const receivables = useQuery({
    queryKey: ["receivables", receivablesOrg?.id],
    queryFn: () => fetchReceivables(receivablesOrg!.id),
    enabled: !!receivablesOrg,
  });

  const createOrgMut = useMutation({
    mutationFn: createOrganization,
    onSuccess: (o) => {
      qc.invalidateQueries({ queryKey: ["organizations"] });
      setCreateOrgOpen(false);
      setOkMsg(`سازمان «${o.name}» ایجاد شد`);
    },
    onError: (e) => setError(errDetail(e)),
  });
  const toggleOrgMut = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      updateOrganization(id, { is_active }),
    onSuccess: (o) => {
      qc.invalidateQueries({ queryKey: ["organizations"] });
      setOkMsg(o.is_active ? "سازمان فعال شد" : "سازمان غیرفعال شد");
    },
    onError: (e) => setError(errDetail(e)),
  });
  const createContractMut = useMutation({
    mutationFn: ({ orgId, payload }: { orgId: string; payload: Record<string, unknown> }) =>
      createContract(orgId, payload),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["contracts"] });
      qc.invalidateQueries({ queryKey: ["organizations"] });
      setNewContractFor(null);
      setOkMsg(`قرارداد «${c.title}» ثبت شد (پیش‌نویس — پس از کنترل، فعال کنید)`);
    },
    onError: (e) => setError(errDetail(e)),
  });
  const setContractStatusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateContract(id, { status }),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["contracts"] });
      qc.invalidateQueries({ queryKey: ["organizations"] });
      setOkMsg(
        c.status === "active"
          ? "قرارداد فعال شد — سفارش‌های جدید با تقسیم سهم سازمان ساخته می‌شوند"
          : c.status === "terminated"
            ? "قرارداد ملغی شد — در سفارش‌های جدید اعمال نمی‌شود"
            : "وضعیت قرارداد تغییر کرد",
      );
    },
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={800}>سازمان‌ها و قراردادها (B21)</Typography>
        <Box flexGrow={1} />
        <Button variant="contained" onClick={() => setCreateOrgOpen(true)}>سازمان جدید</Button>
      </Box>
      <Alert severity="info">
        قرارداد سازمان درصد سهم پرداخت سازمان را تعیین می‌کند؛ سهم در لحظه ساخت سفارش
        snapshot می‌شود و با تغییر قرارداد تغییر نمی‌کند. قرارداد و کد تخفیف هم‌زمان قابل
        استفاده نیستند. قرارداد منقضی/پیش‌نویس/ملغی اعمال نمی‌شود.
      </Alert>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>سازمان</TableCell>
              <TableCell>slug</TableCell>
              <TableCell>شناسه ملی</TableCell>
              <TableCell>تلفن</TableCell>
              <TableCell>قرارداد فعال</TableCell>
              <TableCell>تعداد قرارداد</TableCell>
              <TableCell>فعال</TableCell>
              <TableCell align="left">عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(orgs.data ?? []).map((o) => (
              <TableRow
                key={o.id}
                hover
                selected={selectedOrg?.id === o.id}
                onClick={() => setSelectedOrg(o)}
                sx={{ cursor: "pointer", opacity: o.is_active ? 1 : 0.55 }}
              >
                <TableCell>{o.name}</TableCell>
                <TableCell dir="ltr" sx={{ fontFamily: "monospace", fontSize: 12 }}>{o.slug}</TableCell>
                <TableCell dir="ltr">{o.national_id ?? "—"}</TableCell>
                <TableCell dir="ltr">{o.phone ?? "—"}</TableCell>
                <TableCell>
                  {o.active_contract ? (
                    <Chip size="small" color="success" variant="outlined"
                          label={`${o.active_contract.title} — ${fa(o.active_contract.coverage_percent)}٪`} />
                  ) : (
                    <Chip size="small" label="بدون قرارداد فعال" />
                  )}
                </TableCell>
                <TableCell>{fa(o.contract_count)}</TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Switch
                    size="small" checked={o.is_active}
                    onChange={(e) => toggleOrgMut.mutate({ id: o.id, is_active: e.target.checked })}
                  />
                </TableCell>
                <TableCell align="left" onClick={(e) => e.stopPropagation()}>
                  <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                    <Button size="small" onClick={() => setNewContractFor(o)}>قرارداد جدید</Button>
                    <Button size="small" onClick={() => setReceivablesOrg(o)}>مطالبات</Button>
                    <Button size="small" onClick={() => toggleOrgMut.mutate({ id: o.id, is_active: !o.is_active })}>
                      {o.is_active ? "غیرفعال" : "فعال"}
                    </Button>
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
            {(orgs.data ?? []).length === 0 && (
              <TableRow><TableCell colSpan={8} align="center" sx={{ py: 4, color: "text.secondary" }}>
                سازمانی ثبت نشده است.
              </TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {selectedOrg && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography fontWeight={700} mb={1}>
            قراردادهای «{selectedOrg.name}»
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>عنوان</TableCell>
                  <TableCell>سهم سازمان</TableCell>
                  <TableCell>سقف هر سفارش</TableCell>
                  <TableCell>اعتبار</TableCell>
                  <TableCell>دامنه</TableCell>
                  <TableCell>وضعیت</TableCell>
                  <TableCell align="left">عملیات</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(contracts.data ?? []).map((c) => (
                  <ContractRow key={c.id} c={c}
                               onStatus={(s) => setContractStatusMut.mutate({ id: c.id, status: s })} />
                ))}
                {(contracts.data ?? []).length === 0 && (
                  <TableRow><TableCell colSpan={7} align="center" sx={{ py: 3, color: "text.secondary" }}>
                    قراردادی ثبت نشده است.
                  </TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      <CreateOrgDialog
        open={createOrgOpen}
        loading={createOrgMut.isPending}
        onClose={() => setCreateOrgOpen(false)}
        onSubmit={(payload) => createOrgMut.mutate(payload)}
      />
      <CreateContractDialog
        org={newContractFor}
        services={services.data ?? []}
        loading={createContractMut.isPending}
        onClose={() => setNewContractFor(null)}
        onSubmit={(payload) => newContractFor && createContractMut.mutate({ orgId: newContractFor.id, payload })}
      />
      <ReceivablesDialog
        report={receivables.data ?? null}
        orgName={receivablesOrg?.name ?? ""}
        loading={receivables.isLoading}
        onClose={() => setReceivablesOrg(null)}
      />

      <Snackbar open={!!okMsg} autoHideDuration={4000} onClose={() => setOkMsg(null)}
                anchorOrigin={{ vertical: "bottom", horizontal: "center" }}>
        <Alert severity="success" variant="filled">{okMsg}</Alert>
      </Snackbar>
    </Stack>
  );
}

function ContractRow({ c, onStatus }: { c: Contract; onStatus: (s: string) => void }) {
  const st = C_STATUS[c.status] ?? C_STATUS.draft;
  const scope = c.services.length === 0 ? "همه خدمات" : `${c.services.length} خدمت مشخص`;
  return (
    <TableRow sx={{ opacity: c.status === "terminated" ? 0.55 : 1 }}>
      <TableCell>{c.title}</TableCell>
      <TableCell>{fa(c.coverage_percent)}٪</TableCell>
      <TableCell>{c.coverage_cap_amount ? fa(c.coverage_cap_amount) : "—"}</TableCell>
      <TableCell dir="ltr" sx={{ fontSize: 12 }}>
        {c.valid_from} ← {c.valid_to ?? "∞"}
      </TableCell>
      <TableCell>{scope}</TableCell>
      <TableCell><Chip size="small" color={st.color} label={st.label} /></TableCell>
      <TableCell align="left">
        <Stack direction="row" spacing={0.5} justifyContent="flex-end">
          {c.status === "draft" && (
            <Button size="small" color="success" onClick={() => onStatus("active")}>فعال‌سازی</Button>
          )}
          {c.status !== "terminated" && (
            <Button size="small" color="error" onClick={() => onStatus("terminated")}>لغو</Button>
          )}
        </Stack>
      </TableCell>
    </TableRow>
  );
}

function CreateOrgDialog({ open, loading, onClose, onSubmit }: {
  open: boolean; loading: boolean; onClose: () => void;
  onSubmit: (payload: Record<string, unknown>) => void;
}) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [nationalId, setNationalId] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({
      name, slug,
      national_id: nationalId || null,
      phone: phone || null, email: email || null, address: address || null,
    });
    setName(""); setSlug(""); setNationalId(""); setPhone(""); setEmail(""); setAddress("");
  };
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>سازمان جدید (B21)</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField label="نام سازمان" required value={name} onChange={(e) => setName(e.target.value)} />
            <TextField label="slug (لاتین کوچک)" required dir="ltr" value={slug}
                       helperText="مثال: tehran-steel-co" onChange={(e) => setSlug(e.target.value)} />
            <TextField label="شناسه ملی (اختیاری، یکتا)" dir="ltr" value={nationalId}
                       onChange={(e) => setNationalId(e.target.value)} />
            <TextField label="تلفن" dir="ltr" value={phone} onChange={(e) => setPhone(e.target.value)} />
            <TextField label="ایمیل" dir="ltr" value={email} onChange={(e) => setEmail(e.target.value)} />
            <TextField label="نشانی" multiline minRows={2} value={address}
                       onChange={(e) => setAddress(e.target.value)} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={loading}>ایجاد</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function CreateContractDialog({ org, services, loading, onClose, onSubmit }: {
  org: Organization | null;
  services: { id: string; title: string; status: string }[];
  loading: boolean;
  onClose: () => void;
  onSubmit: (payload: Record<string, unknown>) => void;
}) {
  const [title, setTitle] = useState("");
  const [percent, setPercent] = useState(30);
  const [cap, setCap] = useState("");
  const [validFrom, setValidFrom] = useState(new Date().toISOString().slice(0, 10));
  const [validTo, setValidTo] = useState("");
  const [serviceIds, setServiceIds] = useState<string[]>([]);
  if (!org) return null;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({
      title, coverage_percent: percent,
      coverage_cap_amount: cap ? Number(cap) : null,
      valid_from: validFrom,
      valid_to: validTo || null,
      service_ids: serviceIds,
    });
    setTitle(""); setPercent(30); setCap(""); setServiceIds([]);
  };
  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>قرارداد جدید برای «{org.name}»</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField label="عنوان قرارداد" required value={title}
                       onChange={(e) => setTitle(e.target.value)} />
            <TextField label="درصد سهم سازمان (۱ تا ۱۰۰)" type="number" required value={percent}
                       inputProps={{ min: 1, max: 100 }}
                       helperText="سهم سازمان از هر سفارش؛ باقیمانده بر عهده متقاضی"
                       onChange={(e) => setPercent(Number(e.target.value))} />
            <TextField label="سقف سهم به‌ازای هر سفارش (اختیاری)" type="number" dir="ltr"
                       value={cap} onChange={(e) => setCap(e.target.value)} />
            <Stack direction="row" spacing={2}>
              <TextField label="شروع اعتبار" type="date" required value={validFrom}
                         onChange={(e) => setValidFrom(e.target.value)} fullWidth />
              <TextField label="پایان اعتبار (اختیاری)" type="date" value={validTo}
                         onChange={(e) => setValidTo(e.target.value)} fullWidth />
            </Stack>
            <FormControl size="small">
              <InputLabel>دامنه خدمات (خالی = همه خدمات)</InputLabel>
              <Select multiple value={serviceIds}
                      onChange={(e) => setServiceIds(e.target.value as string[])}
                      input={<OutlinedInput label="دامنه خدمات (خالی = همه خدمات)" />}
                      renderValue={(sel) => (sel as string[])
                        .map((id) => services.find((s) => s.id === id)?.title ?? "؟").join("، ")}>
                {services.map((s) => (
                  <MenuItem key={s.id} value={s.id} disabled={s.status !== "active"}>
                    <ListItemText primary={s.title} />
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={loading}>ثبت قرارداد</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function ReceivablesDialog({ report, orgName, loading, onClose }: {
  report: ReceivablesReport | null;
  orgName: string;
  loading: boolean;
  onClose: () => void;
}) {
  if (!report && !loading) return null;
  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>مطالبه از سازمان «{orgName}»</DialogTitle>
      <DialogContent>
        {loading && <Typography>در حال بارگذاری…</Typography>}
        {report && (
          <Stack spacing={2}>
            <Alert severity="info">{report.note}</Alert>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              <Paper variant="outlined" sx={{ p: 1.5, minWidth: 180 }}>
                <Typography variant="caption">سفارش پرداخت‌شده با سهم سازمان</Typography>
                <Typography fontWeight={800}>{fa(report.paid_orders_with_share)}</Typography>
              </Paper>
              <Paper variant="outlined" sx={{ p: 1.5, minWidth: 180 }}>
                <Typography variant="caption">مطالبه از سازمان (B21)</Typography>
                <Typography fontWeight={800} color="warning.main">{fa(report.org_share_total)}</Typography>
              </Paper>
              <Paper variant="outlined" sx={{ p: 1.5, minWidth: 180 }}>
                <Typography variant="caption">دریافتی از متقاضی</Typography>
                <Typography fontWeight={800} color="success.main">{fa(report.applicant_share_total)}</Typography>
              </Paper>
              <Paper variant="outlined" sx={{ p: 1.5, minWidth: 180 }}>
                <Typography variant="caption">جمع مبلغ سفارش‌ها</Typography>
                <Typography fontWeight={800}>{fa(report.total_amount)}</Typography>
              </Paper>
            </Stack>
            {report.items.length > 0 && (
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>سفارش</TableCell>
                      <TableCell>مبلغ کل</TableCell>
                      <TableCell>درصد</TableCell>
                      <TableCell>سهم سازمان</TableCell>
                      <TableCell>سهم متقاضی</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {report.items.map((it) => (
                      <TableRow key={it.order_id}>
                        <TableCell>{it.order_number}</TableCell>
                        <TableCell>{fa(it.amount)}</TableCell>
                        <TableCell>{it.coverage_percent ? `${fa(it.coverage_percent)}٪` : "—"}</TableCell>
                        <TableCell>{fa(it.org_share_amount)}</TableCell>
                        <TableCell>{fa(it.applicant_share_amount)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Stack>
        )}
      </DialogContent>
      <DialogActions><Button onClick={onClose}>بستن</Button></DialogActions>
    </Dialog>
  );
}
