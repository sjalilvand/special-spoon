import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControl, InputLabel, LinearProgress, MenuItem, Paper, Select, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TablePagination, TableRow, TextField, Typography,
} from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { errDetail } from "../api/client";
import {
  Applicant, createApplicant, createApplicantAccount, createApplicantActivationLink,
  createApplicantRequest, enrollApplicantOrgPrograms, fetchApplicantSummary, fetchApplicants,
  fetchOrgUnits, fetchServiceLocations,
} from "../api/people";
import { fetchOrganizations } from "../api/organizations";
import JalaliDateField from "../components/JalaliDateField";

const KIND_LABELS: Record<string, string> = {
  psych_test: "آزمون",
  consultation: "درخواست مشاوره",
  appointment: "نوبت",
  intake: "پرسشنامهٔ پذیرش",
  assessment: "ارزیابی",
};

const TYPE_LABELS: Record<string, string> = {
  in_person: "حضوری",
  phone: "تلفنی",
  online: "آنلاین",
};

export default function ApplicantsPage() {
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [requestFor, setRequestFor] = useState<Applicant | null>(null);
  const [fileFor, setFileFor] = useState<Applicant | null>(null);
  const [accountFor, setAccountFor] = useState<Applicant | null>(null);

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
      {notice && <Alert severity="success" onClose={() => setNotice(null)}>{notice}</Alert>}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>شناسه</TableCell>
              <TableCell>کد ملی</TableCell>
              <TableCell>نام</TableCell>
              <TableCell>موبایل</TableCell>
              <TableCell>سازمان</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={7} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.external_id ?? row.employee_code ?? "—"}</TableCell>
                <TableCell>{row.national_id ?? "—"}</TableCell>
                <TableCell>{row.first_name} {row.last_name}</TableCell>
                <TableCell>{row.mobile ?? "—"}</TableCell>
                <TableCell>{row.organization_name ?? "—"}</TableCell>
                <TableCell>
                  <Chip size="small" color={row.status === "active" ? "success" : "default"}
                    label={row.status === "active" ? "فعال" : row.status === "archived" ? "بایگانی" : "غیرفعال"} />
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                    <Button size="small" onClick={() => setRequestFor(row)}>درخواست</Button>
                    <Button size="small" onClick={() => setFileFor(row)}>پرونده</Button>
                    <Button size="small" onClick={() => setAccountFor(row)}>
                      {row.has_account ? "لینک فعال‌سازی" : "حساب"}
                    </Button>
                  </Stack>
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
      {requestFor && (
        <RequestDialog applicant={requestFor} onClose={() => setRequestFor(null)}
          onError={setError} onDone={(m) => { setNotice(m); setRequestFor(null); }} />
      )}
      {fileFor && (
        <FileDialog applicant={fileFor} onClose={() => setFileFor(null)} onError={setError}
          onEnrolled={(m) => setNotice(m)} />
      )}
      {accountFor && (
        <AccountDialog applicant={accountFor} onClose={() => setAccountFor(null)}
          onError={setError} onDone={(m) => { setNotice(m); setAccountFor(null); }} />
      )}
    </Stack>
  );
}

function CreateDialog({ open, onClose, onError }: { open: boolean; onClose: () => void; onError: (m: string) => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({});
  const [createAccount, setCreateAccount] = useState(false);
  const [birthDate, setBirthDate] = useState<string | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const { data: units } = useQuery({ queryKey: ["units"], queryFn: fetchOrgUnits, enabled: open });
  const { data: locations } = useQuery({ queryKey: ["locations"], queryFn: fetchServiceLocations, enabled: open });
  const { data: orgs } = useQuery({ queryKey: ["organizations"], queryFn: fetchOrganizations, enabled: open });

  useEffect(() => {
    if (open) { setForm({}); setCreateAccount(false); setFormError(null); setBirthDate(undefined); }
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
        birth_date: birthDate,
        gender: form.gender || undefined,
        mobile: form.mobile?.trim() || undefined,
        unit_id: form.unit_id || undefined,
        organization_id: form.organization_id || undefined,
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
              {/* فاز ۸۷: value متصل به state — قبلاً undefined بود و تاریخ انتخابی نمایش داده نمی‌شد */}
              <JalaliDateField
                label="تاریخ تولد"
                value={birthDate}
                onChange={(iso) => setBirthDate(iso)}
              />
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
              {/* فاز ۸۷: انتخاب سازمان کارفرما — حساب متقاضی هم به همان سازمان منتسب می‌شود */}
              <FormControl fullWidth size="small">
                <InputLabel>سازمان</InputLabel>
                <Select value={form.organization_id ?? ""} onChange={set("organization_id")} label="سازمان">
                  <MenuItem value="">—</MenuItem>
                  {orgs?.map((o) => <MenuItem key={o.id} value={o.id}>{o.name}</MenuItem>)}
                </Select>
              </FormControl>
              <FormControl fullWidth size="small">
                <InputLabel>واحد سازمانی</InputLabel>
                <Select value={form.unit_id ?? ""} onChange={set("unit_id")} label="واحد سازمانی">
                  <MenuItem value="">—</MenuItem>
                  {units?.map((u) => <MenuItem key={u.id} value={u.id}>{u.title} ({u.code})</MenuItem>)}
                </Select>
              </FormControl>
            </Stack>
            <Stack direction="row" spacing={2}>
              <FormControl fullWidth size="small">
                <InputLabel>محل خدمت</InputLabel>
                <Select value={form.service_location_id ?? ""} onChange={set("service_location_id")} label="محل خدمت">
                  <MenuItem value="">—</MenuItem>
                  {locations?.map((l) => <MenuItem key={l.id} value={l.id}>{l.title} ({l.code})</MenuItem>)}
                </Select>
              </FormControl>
              <TextField label="منبع ارجاع" fullWidth value={form.referral_source ?? ""} onChange={set("referral_source")} />
            </Stack>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input type="checkbox" checked={createAccount} onChange={(e) => setCreateAccount(e.target.checked)} />
              ایجاد حساب ورود (نقش ثابت متقاضی) — متقاضی با آن وارد پنل می‌شود و پرسشنامه و نتیجهٔ آزمون‌هایش را می‌بیند
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

/** فاز ۸۷ — ثبت درخواست مشاورهٔ حضوری/تلفنی از روی پروفایل متقاضی */
function RequestDialog({ applicant, onClose, onError, onDone }: {
  applicant: Applicant; onClose: () => void; onError: (m: string) => void; onDone: (m: string) => void;
}) {
  const queryClient = useQueryClient();
  const [topic, setTopic] = useState("");
  const [message, setMessage] = useState("");
  const [requestType, setRequestType] = useState("in_person");
  const [date, setDate] = useState<string | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await createApplicantRequest(applicant.id, {
        topic: topic.trim(),
        message: message.trim() || undefined,
        preferred_date: date,
        request_type: requestType,
      });
      await queryClient.invalidateQueries({ queryKey: ["applicants"] });
      onDone("درخواست مشاوره ثبت شد و به پروندهٔ متقاضی اضافه شد.");
    } catch (err) {
      setFormError(errDetail(err));
      onError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>ثبت درخواست مشاوره — {applicant.first_name} {applicant.last_name}</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mt: 1 }}>{formError}</Alert>}
          <Stack spacing={2} mt={1}>
            <FormControl fullWidth size="small">
              <InputLabel>نوع درخواست</InputLabel>
              <Select value={requestType} onChange={(e) => setRequestType(e.target.value)} label="نوع درخواست">
                <MenuItem value="in_person">حضوری</MenuItem>
                <MenuItem value="phone">تلفنی</MenuItem>
                <MenuItem value="online">آنلاین</MenuItem>
              </Select>
            </FormControl>
            <TextField label="موضوع *" fullWidth value={topic} onChange={(e) => setTopic(e.target.value)} required />
            <JalaliDateField label="تاریخ مرجوع/مراجعه" value={date} onChange={(iso) => setDate(iso)} />
            <TextField label="توضیح" fullWidth multiline minRows={2} value={message} onChange={(e) => setMessage(e.target.value)} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>{busy ? "در حال ثبت…" : "ثبت درخواست"}</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

/** فاز ۸۷ — پروندهٔ الکترونیکی متقاضی: همهٔ اطلاعات یک‌جا */
function FileDialog({ applicant, onClose, onError, onEnrolled }: {
  applicant: Applicant; onClose: () => void; onError: (m: string) => void; onEnrolled: (m: string) => void;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["applicant-summary", applicant.id],
    queryFn: () => fetchApplicantSummary(applicant.id),
  });
  const [enrolling, setEnrolling] = useState(false);

  useEffect(() => {
    if (error) onError(errDetail(error));
  }, [error, onError]);

  const enroll = async () => {
    setEnrolling(true);
    try {
      const r = await enrollApplicantOrgPrograms(applicant.id);
      onEnrolled(`متقاضی در ${r.added} برنامهٔ فعال سازمان ثبت‌نام شد (از ${r.programs} برنامه).`);
    } catch (err) {
      onError(errDetail(err));
    } finally {
      setEnrolling(false);
    }
  };

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        پروندهٔ الکترونیکی — {applicant.first_name} {applicant.last_name}
      </DialogTitle>
      <DialogContent dividers>
        {isLoading && <LinearProgress />}
        {data && (
          <Stack spacing={2}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip size="small" label={`سازمان: ${data.organization_name ?? "—"}`} variant="outlined" />
              <Chip size="small" label={`موبایل: ${data.applicant.mobile ?? "—"}`} variant="outlined" />
              <Chip size="small" label={`کد ملی: ${data.applicant.national_id ?? "—"}`} variant="outlined" />
              {data.user ? (
                <Chip size="small" color="info" label={`حساب: ${data.user.username} (${data.user.status === "active" ? "فعال" : data.user.status === "pending_activation" ? "در انتظار فعال‌سازی" : "غیرفعال"})`} />
              ) : (
                <Chip size="small" color="warning" label="بدون حساب کاربری" />
              )}
            </Stack>

            <Box>
              <Typography variant="subtitle2" fontWeight={700} mb={1}>درخواست‌های مشاوره ({data.requests.length})</Typography>
              {data.requests.length === 0 && <Typography variant="body2" color="text.secondary">ثبت نشده است.</Typography>}
              {data.requests.map((r) => (
                <Box key={r.id} display="flex" gap={1} alignItems="center" mb={0.5}>
                  <Chip size="small" label={r.request_type ? TYPE_LABELS[r.request_type] ?? r.request_type : "—"} />
                  <Typography variant="body2">{r.topic}</Typography>
                  <Chip size="small" variant="outlined"
                    label={r.status === "new" ? "جدید" : r.status === "in_review" ? "در بررسی" : r.status === "converted" ? "تبدیل به پرونده" : "بایگانی"} />
                </Box>
              ))}
            </Box>

            <Box>
              <Typography variant="subtitle2" fontWeight={700} mb={1}>پرونده‌های بالینی ({data.cases.length})</Typography>
              {data.cases.length === 0 && <Typography variant="body2" color="text.secondary">ثبت نشده است.</Typography>}
              {data.cases.map((c) => (
                <Box key={c.id} display="flex" gap={1} alignItems="center" mb={0.5}>
                  <Chip size="small" label={c.case_number} />
                  <Chip size="small" variant="outlined" label={c.status} />
                </Box>
              ))}
            </Box>

            <Box>
              <Typography variant="subtitle2" fontWeight={700} mb={1}>تاریخچهٔ کامل (آزمون، پرسشنامه، نوبت، مشاوره)</Typography>
              {data.timeline.length === 0 && <Typography variant="body2" color="text.secondary">موردی ثبت نشده است.</Typography>}
              {data.timeline.map((t) => (
                <Box key={`${t.kind}-${t.id}`} display="flex" gap={1} alignItems="center" mb={0.5}>
                  <Chip size="small" color={t.kind === "psych_test" ? "primary" : t.kind === "intake" ? "secondary" : "default"}
                    label={KIND_LABELS[t.kind] ?? t.kind} />
                  <Typography variant="body2" sx={{ flexGrow: 1 }}>{t.title}</Typography>
                  {t.status && <Chip size="small" variant="outlined" label={t.status} />}
                  {t.at && <Typography variant="caption" color="text.secondary">{t.at.slice(0, 10)}</Typography>}
                </Box>
              ))}
            </Box>
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={enroll} disabled={enrolling || !applicant.organization_id}
          title="ثبت‌نام متقاضی در همهٔ برنامه‌های فعال سازمانِ او">
          {enrolling ? "در حال ثبت‌نام…" : "ثبت‌نام در برنامه‌های سازمان"}
        </Button>
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}

/** فاز ۸۷ — حساب کاربری متقاضی: ساخت حساب یا صدور لینک فعال‌سازی */
function AccountDialog({ applicant, onClose, onError, onDone }: {
  applicant: Applicant; onClose: () => void; onError: (m: string) => void; onDone: (m: string) => void;
}) {
  const [username, setUsername] = useState(applicant.mobile || "");
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState<{ username: string; activation_path: string } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const createAccount = async () => {
    setFormError(null);
    setBusy(true);
    try {
      await createApplicantAccount(applicant.id, username.trim());
      onDone("حساب کاربری ساخته شد. اکنون لینک فعال‌سازی بگیرید و برای متقاضی بفرستید.");
    } catch (err) {
      setFormError(errDetail(err));
      onError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  const issueLink = async () => {
    setFormError(null);
    setBusy(true);
    try {
      const r = await createApplicantActivationLink(applicant.id);
      setLink(r);
    } catch (err) {
      setFormError(errDetail(err));
      onError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  const fullUrl = link ? `${window.location.origin}${link.activation_path}` : "";

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>حساب کاربری متقاضی</DialogTitle>
      <DialogContent>
        {formError && <Alert severity="error" sx={{ mt: 1 }}>{formError}</Alert>}
        {!applicant.has_account ? (
          <Stack spacing={2} mt={1}>
            <Typography variant="body2" color="text.secondary">
              حساب در وضعیت «در انتظار فعال‌سازی» ساخته می‌شود؛ سپس لینک یک‌بارمصرف تعیین رمز صادر کنید.
            </Typography>
            <TextField label="نام کاربری *" fullWidth value={username} onChange={(e) => setUsername(e.target.value)} />
            <Button variant="contained" onClick={createAccount} disabled={busy || !username.trim()}>
              {busy ? "در حال ساخت…" : "ساخت حساب"}
            </Button>
          </Stack>
        ) : (
          <Stack spacing={2} mt={1}>
            <Typography variant="body2" color="text.secondary">
              لینک فعال‌سازی یک‌بارمصرف صادر کنید و برای متقاضی بفرستید (۲۴ ساعت اعتبار دارد).
            </Typography>
            {!link && (
              <Button variant="contained" onClick={issueLink} disabled={busy}>
                {busy ? "…" : "صدور لینک فعال‌سازی"}
              </Button>
            )}
            {link && (
              <>
                <TextField label="لینک فعال‌سازی" fullWidth multiline value={fullUrl}
                  InputProps={{ readOnly: true }} onClick={(e) => (e.target as HTMLInputElement).select()} />
                <Button variant="outlined"
                  onClick={() => { navigator.clipboard?.writeText(fullUrl); }}>
                  کپی لینک
                </Button>
              </>
            )}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}
