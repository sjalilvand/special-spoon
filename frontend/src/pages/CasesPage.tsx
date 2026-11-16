import {
  Alert, Autocomplete, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControl, InputLabel, MenuItem, Paper, Select, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TablePagination, TableRow, TextField, Typography,
} from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { errDetail } from "../api/client";
import {
  CASE_STATUS_META, CONSENT_META, PRIORITY_LABELS,
  createCase, fetchApplicantOptions, fetchCases, fetchCounselorOptions,
} from "../api/cases";
import type { OptionRow } from "../api/cases";
import { fetchOrganizations } from "../api/organizations";
import { fetchServiceLocations } from "../api/people";
import { formatJalali } from "../utils/jalali";

/** فاز ۸۹ - گزینهٔ «همهٔ سازمان‌ها»: جست‌وجوی سراسری متقاضیان (حداقل ۲ حرف) */
const ALL_ORGS = "__all__";

export default function CasesPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading, error: listError } = useQuery({
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
      {/* فاز ۸۹ - خطای بارگذاری فهرست دیگر بی‌صدا نیست */}
      {listError && (
        <Alert severity="error">
          دریافت فهرست پرونده‌ها ناموفق بود: {errDetail(listError)}
        </Alert>
      )}

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
                  <TableCell>{formatJalali(row.acceptance_date)}</TableCell>
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

  // فاز ۸۹ - جریان سازمان → متقاضی: ابتدا سازمان/مرکز، سپس جست‌وجوی متقاضیان همان سازمان
  const [orgId, setOrgId] = useState("");
  const [applicantSearch, setApplicantSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [applicantValue, setApplicantValue] = useState<OptionRow | null>(null);
  const [counselorValue, setCounselorValue] = useState<OptionRow | null>(null);
  const prefilledRef = useRef(false);

  const { data: organizations, error: orgError } = useQuery({
    queryKey: ["organization-list"],
    queryFn: fetchOrganizations,
    enabled: open,
  });
  const searchReady = orgId === ALL_ORGS ? debouncedSearch.trim().length >= 2 : orgId !== "";
  const { data: applicants, isFetching: applicantsLoading, error: applicantsError } = useQuery({
    queryKey: ["applicant-options", orgId, debouncedSearch],
    queryFn: () => fetchApplicantOptions({
      search: debouncedSearch.trim() || undefined,
      org_id: orgId === ALL_ORGS ? undefined : orgId,
    }),
    enabled: open && searchReady,
    staleTime: 30_000,
  });
  const { data: counselors, error: counselorsError } = useQuery({
    queryKey: ["counselor-options"], queryFn: fetchCounselorOptions, enabled: open,
  });
  const { data: locations, error: locationsError } = useQuery({
    queryKey: ["locations"], queryFn: fetchServiceLocations, enabled: open,
  });

  useEffect(() => {
    if (open) { setForm({}); setFormError(null); }
  }, [open]);

  // فاز ۸۹ - اگر کاربرِ واردشده خودش مشاور است، نام خودش به‌عنوان مشاور اصلی پیش‌گزینش می‌شود
  useEffect(() => {
    if (!open) { prefilledRef.current = false; return; }
    if (prefilledRef.current) return;
    const self = counselors?.self_counselor ?? null;
    if (self) {
      prefilledRef.current = true;
      setForm((p) => ({ ...p, counselor_id: self.id }));
      setCounselorValue(self);
    }
  }, [open, counselors]);

  // جست‌وجوی متقاضی با تأخیر ۴۰۰ میلی‌ثانیه (ضد اسپم سرور)
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(applicantSearch), 400);
    return () => clearTimeout(t);
  }, [applicantSearch]);

  const orgOptions = useMemo(() => [
    { id: ALL_ORGS, name: "همهٔ سازمان‌ها (جست‌وجوی سراسری)" },
    ...(organizations ?? []).map((o) => ({ id: o.id, name: o.is_active === false ? `${o.name} (غیرفعال)` : o.name })),
  ], [organizations]);

  // فاز ۸۹ - هیچ خطای بارگذاری گزینه‌ها بی‌صدا نمی‌ماند
  const optionErrorText = useMemo(() => {
    const failed: string[] = [];
    if (orgError) failed.push("فهرست سازمان‌ها");
    if (counselorsError) failed.push("فهرست مشاوران");
    if (locationsError) failed.push("محل‌های ارائه خدمت");
    if (applicantsError) failed.push("جست‌وجوی متقاضیان");
    if (failed.length === 0) return "";
    const first = orgError || counselorsError || locationsError || applicantsError;
    return `بارگذاری ${failed.join(" و ")} ناموفق بود — ${errDetail(first)}`;
  }, [orgError, counselorsError, locationsError, applicantsError]);

  const set = (k: string) => (e: { target: { value: string } }) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!form.applicant_id) {
      setFormError("ابتدا سازمان متقاضی را مشخص و سپس متقاضی را جست‌وجو و انتخاب کنید.");
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

  const applicantNoOptions = orgId === ""
    ? "ابتدا سازمان متقاضی را انتخاب کنید"
    : orgId === ALL_ORGS && debouncedSearch.trim().length < 2
      ? "برای جست‌وجوی همهٔ سازمان‌ها حداقل ۲ حرف بنویسید"
      : "موردی یافت نشد";

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>تشکیل پرونده جدید</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            تاریخ پذیرش به‌صورت خودکار امروز ثبت می‌شود و شماره پرونده در سرور تولید می‌گردد.
          </Typography>
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          {optionErrorText && <Alert severity="error" sx={{ mt: 2 }}>{optionErrorText}</Alert>}
          <Stack spacing={2} mt={2}>
            {/* گام ۱ — سازمان/مرکز متقاضی */}
            <Autocomplete
              size="small"
              options={orgOptions}
              value={orgOptions.find((o) => o.id === orgId) ?? null}
              getOptionLabel={(o) => o.name}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              onChange={(_, v) => {
                setOrgId(v?.id ?? "");
                setApplicantValue(null);
                setForm((p) => ({ ...p, applicant_id: "" }));
              }}
              renderInput={(params) => (
                <TextField {...params} size="small" required label="سازمان / مرکز متقاضی"
                  placeholder="جست‌وجوی سازمان…" />
              )}
            />
            {/* گام ۲ — جست‌وجوی متقاضی (سمت سرور، مخصوص حجم بالا ~۲ میلیون) */}
            <Autocomplete
              size="small"
              disablePortal
              options={applicants?.items ?? []}
              value={applicantValue}
              loading={applicantsLoading}
              filterOptions={(x) => x}
              getOptionLabel={(o) => o.label}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              onInputChange={(_, v) => setApplicantSearch(v)}
              onChange={(_, v) => {
                setApplicantValue(v);
                setForm((p) => ({ ...p, applicant_id: v?.id ?? "" }));
              }}
              renderInput={(params) => (
                <TextField {...params} size="small" required
                  label={orgId === ALL_ORGS ? "جست‌وجوی متقاضی در همهٔ سازمان‌ها" : "جست‌وجوی متقاضی (نام یا کد ملی)"}
                  placeholder="مثلاً: رضایی یا ۰۰۱۲…" />
              )}
              noOptionsText={applicantNoOptions}
            />
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
            {/* فاز ۸۹ - جست‌وجوی مشاور؛ اگر کاربرِ واردشده خودش مشاور باشد نامش پیش‌گزینش شده است */}
            <Autocomplete
              size="small"
              options={counselors?.items ?? []}
              value={counselorValue}
              getOptionLabel={(o) => o.label}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              onChange={(_, v) => {
                setCounselorValue(v);
                setForm((p) => ({ ...p, counselor_id: v?.id ?? "" }));
              }}
              renderInput={(params) => (
                <TextField {...params} size="small" label="مشاور اصلی (اختیاری)"
                  placeholder="جست‌وجوی مشاور…" />
              )}
              noOptionsText="مشاوری یافت نشد"
            />
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
