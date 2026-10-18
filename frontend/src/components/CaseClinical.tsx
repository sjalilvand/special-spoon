import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, FormControl, InputLabel, MenuItem, Paper, Select, Stack, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import {
  DX_STATUS_META, PLAN_APPROACH_LABELS, createDiagnosis, createTreatmentPlan,
  fetchDiagnoses, fetchTreatmentPlans,
} from "../api/clinical";
import { formatJalali, formatJalaliDateTime } from "../utils/jalali";

export default function CaseClinical({ caseId }: { caseId: string }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const roles = user?.roles ?? [];
  const clinical = roles.includes("COUNSELOR") || roles.includes("TECHNICAL_SUPERVISOR");
  const isCounselor = roles.includes("COUNSELOR");

  const [dxOpen, setDxOpen] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: dx, isLoading: dxLoading } = useQuery({
    queryKey: ["diagnoses", caseId],
    queryFn: () => fetchDiagnoses(caseId),
    enabled: clinical,
  });

  const { data: plans, isLoading: plansLoading } = useQuery({
    queryKey: ["plans", caseId],
    queryFn: () => fetchTreatmentPlans(caseId),
    enabled: clinical,
  });

  if (!clinical) return null;
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["diagnoses", caseId] });
    qc.invalidateQueries({ queryKey: ["plans", caseId] });
  };

  return (
    <Stack spacing={2}>
      <Paper sx={{ p: 2 }}>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
          <Typography variant="subtitle1" fontWeight={700}>تشخیص‌ها (بالینی)</Typography>
          {isCounselor && (
            <Button size="small" variant="contained" onClick={() => setDxOpen(true)}>ثبت تشخیص</Button>
          )}
        </Box>
        {dxLoading && <CircularProgress size={24} />}
        {dx?.items.length === 0 && (
          <Typography variant="body2" color="text.secondary">تشخیصی ثبت نشده است.</Typography>
        )}
        {dx && dx.items.length > 0 && (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>وضعیت</TableCell>
                  <TableCell>عنوان</TableCell>
                  <TableCell>کد</TableCell>
                  <TableCell>افزایشی</TableCell>
                  <TableCell>ثبت‌کننده</TableCell>
                  <TableCell>تاریخ</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {dx.items.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <Chip size="small" color={row.status === "confirmed" ? "success" : "warning"}
                        label={DX_STATUS_META[row.status] ?? row.status} />
                    </TableCell>
                    <TableCell>{row.title ?? "—"}</TableCell>
                    <TableCell>{row.code ?? "—"}</TableCell>
                    <TableCell>{row.comorbid ?? "—"}</TableCell>
                    <TableCell>{row.recorded_by_name ?? "—"}</TableCell>
                    <TableCell>
                      {row.created_at ? formatJalali(row.created_at) : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
          <Typography variant="subtitle1" fontWeight={700}>طرح‌های درمان (بالینی)</Typography>
          {isCounselor && (
            <Button size="small" variant="contained" onClick={() => setPlanOpen(true)}>طرح درمان جدید</Button>
          )}
        </Box>
        {plansLoading && <CircularProgress size={24} />}
        {plans?.items.length === 0 && (
          <Typography variant="body2" color="text.secondary">طرح درمانی ثبت نشده است.</Typography>
        )}
        <Stack spacing={1.5}>
          {plans?.items.map((t) => (
            <Box key={t.id} sx={{ border: 1, borderColor: "divider", borderRadius: 2, p: 2 }}>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Chip size="small" color={t.status === "active" ? "success" : "default"} label={`نسخه ${t.version_no}`} />
                {t.approach && <Chip size="small" variant="outlined" label={PLAN_APPROACH_LABELS[t.approach] ?? t.approach} />}
                {t.protocol_name && <Chip size="small" variant="outlined" label={t.protocol_name} />}
                <Box flexGrow={1} />
                <Typography variant="caption" color="text.secondary">
                  {t.updated_at ? formatJalaliDateTime(t.updated_at) : ""} — {t.recorded_by_name ?? ""}
                </Typography>
              </Stack>
              <Stack mt={1} spacing={0.5}>
                <Typography variant="body2"><b>اهداف:</b> {t.goals ?? "—"}</Typography>
                <Typography variant="body2">
                  <b>جلسات:</b> {t.sessions_count ?? "—"} {t.session_interval ? `(${t.session_interval})` : ""}
                </Typography>
                <Typography variant="body2"><b>مداخلات:</b> {t.interventions ?? "—"}</Typography>
                {t.external_referral && (
                  <Typography variant="body2"><b>ارجاع خارجی:</b> {t.external_referral}</Typography>
                )}
                <Typography variant="body2">
                  <b>بازبینی:</b> {t.review_date ? formatJalali(t.review_date) : "—"}
                </Typography>
              </Stack>
            </Box>
          ))}
        </Stack>
      </Paper>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <DiagnosisDialog open={dxOpen} caseId={caseId} onClose={() => setDxOpen(false)} invalidate={invalidate} onError={setError} />
      <PlanDialog open={planOpen} caseId={caseId} onClose={() => setPlanOpen(false)} invalidate={invalidate} onError={setError} />
    </Stack>
  );
}

function DiagnosisDialog({ open, caseId, onClose, invalidate, onError }: {
  open: boolean; caseId: string; onClose: () => void; invalidate: () => void; onError: (m: string) => void;
}) {
  const [status, setStatus] = useState("probable");
  const [title, setTitle] = useState("");
  const [code, setCode] = useState("");
  const [comorbid, setComorbid] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (open) { setStatus("probable"); setTitle(""); setCode(""); setComorbid(""); setNote(""); setFormError(null); }
  }, [open]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await createDiagnosis(caseId, {
        status, title: title.trim() || undefined, code: code.trim() || undefined,
        comorbid: comorbid.trim() || undefined, note: note.trim() || undefined,
      });
      invalidate();
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
        <DialogTitle>ثبت تشخیص</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          <Stack spacing={2} mt={2}>
            <FormControl size="small">
              <InputLabel>وضعیت *</InputLabel>
              <Select value={status} label="وضعیت *" onChange={(e) => setStatus(e.target.value)}>
                {Object.entries(DX_STATUS_META).map(([k, v]) => (
                  <MenuItem key={k} value={k}>{v}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField label="عنوان تشخیص (واژگان مصوب) *" value={title} onChange={(e) => setTitle(e.target.value)}
              required={status !== "none"} fullWidth />
            <TextField label="کد (اختیاری)" value={code} onChange={(e) => setCode(e.target.value)} fullWidth />
            <TextField label="تشخیص‌های افزایشی" value={comorbid} onChange={(e) => setComorbid(e.target.value)} multiline minRows={2} fullWidth />
            <TextField label="توضیح" value={note} onChange={(e) => setNote(e.target.value)} multiline minRows={2} fullWidth />
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

function PlanDialog({ open, caseId, onClose, invalidate, onError }: {
  open: boolean; caseId: string; onClose: () => void; invalidate: () => void; onError: (m: string) => void;
}) {
  const [form, setForm] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (open) { setForm({}); setFormError(null); }
  }, [open]);

  const set = (k: string) => (e: { target: { value: string } }) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await createTreatmentPlan(caseId, {
        goals: form.goals?.trim() || undefined,
        approach: form.approach || undefined,
        approach_note: form.approach_note?.trim() || undefined,
        protocol_name: form.protocol_name?.trim() || undefined,
        sessions_count: form.sessions_count ? Number(form.sessions_count) : undefined,
        session_interval: form.session_interval?.trim() || undefined,
        interventions: form.interventions?.trim() || undefined,
        external_referral: form.external_referral?.trim() || undefined,
        review_date: form.review_date?.trim() || undefined,
        remarks: form.remarks?.trim() || undefined,
      });
      invalidate();
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
        <DialogTitle>طرح درمان جدید</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          <Stack spacing={2} mt={2}>
            <TextField label="اهداف درمان" value={form.goals ?? ""} onChange={set("goals")} multiline minRows={2} fullWidth />
            <FormControl size="small" fullWidth>
              <InputLabel>رویکرد/پروتکل</InputLabel>
              <Select value={form.approach ?? ""} onChange={set("approach")} label="رویکرد/پروتکل">
                <MenuItem value="">—</MenuItem>
                {Object.entries(PLAN_APPROACH_LABELS).map(([k, v]) => (
                  <MenuItem key={k} value={k}>{v}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField label="توضیح رویکرد" value={form.approach_note ?? ""} onChange={set("approach_note")} fullWidth />
            <TextField label="نام و نسخه پروتکل" value={form.protocol_name ?? ""} onChange={set("protocol_name")} fullWidth />
            <Stack direction="row" spacing={2}>
              <TextField label="تعداد جلسات" type="number" value={form.sessions_count ?? ""} onChange={set("sessions_count")} fullWidth />
              <TextField label="فاصله جلسات (مثال: هفتگی)" value={form.session_interval ?? ""} onChange={set("session_interval")} fullWidth />
            </Stack>
            <TextField label="مداخلات برنامه‌ریزی‌شده" value={form.interventions ?? ""} onChange={set("interventions")} multiline minRows={2} fullWidth />
            <TextField label="ارجاع به مرکز دیگر (مقصد، علت، تاریخ)" value={form.external_referral ?? ""} onChange={set("external_referral")} fullWidth />
            <TextField label="تاریخ بازبینی (مثال: 1403/06/01 شمسی)" value={form.review_date ?? ""} onChange={set("review_date")} fullWidth />
            <TextField label="ملاحظات" value={form.remarks ?? ""} onChange={set("remarks")} multiline minRows={2} fullWidth />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>ثبت طرح</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
