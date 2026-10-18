import {
  Alert, Box, Button, Checkbox, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, FormControlLabel, MenuItem, Paper, Stack, TextField, Typography,
} from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import {
  ASSESSMENT_STATUS_META, approveAssessment, createAssessmentDraft, createRevision,
  fetchAssessment, fetchFormDefinition, fetchFormHead, fetchForms, finalizeAssessment,
  returnAssessment, saveAssessmentDraft,
} from "../api/assessments";
import type { FormDefinition, FormFieldDef, FormSectionDef } from "../api/assessments";
import { fetchCase } from "../api/cases";
import { printAssessment } from "../api/reports";

export default function AssessmentFormPage() {
  const params = useParams<{ id?: string; caseId?: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const qc = useQueryClient();
  const { user } = useAuth();

  const [currentId, setCurrentId] = useState<string | null>(params.id ?? null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [rowVersion, setRowVersion] = useState(1);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [busySave, setBusySave] = useState(false);
  const [busyFinalize, setBusyFinalize] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmFinalize, setConfirmFinalize] = useState(false);
  const [returnOpen, setReturnOpen] = useState(false);
  const [returnComment, setReturnComment] = useState("");

  // انتخاب فرم هنگام ایجاد جدید (از query یا پیش‌فرض RS-PS-04-01)
  const isCreateMode = !currentId;
  const [selectedFormCode, setSelectedFormCode] = useState<string>(
    searchParams.get("form") || "RS-PS-04-01"
  );

  const { data: formsList } = useQuery({
    queryKey: ["forms-list"],
    queryFn: fetchForms,
    enabled: isCreateMode,
  });

  const { data: formHead } = useQuery({
    queryKey: ["form-head", selectedFormCode],
    queryFn: () => fetchFormHead(selectedFormCode),
    enabled: isCreateMode,
  });

  const { data: headDef, isLoading: defLoading } = useQuery({
    queryKey: ["form-def", selectedFormCode],
    queryFn: () => fetchFormDefinition(selectedFormCode),
    enabled: isCreateMode,
  });

  const { data: existing, isLoading: existingLoading } = useQuery({
    queryKey: ["assessment", currentId],
    queryFn: () => fetchAssessment(currentId!),
    enabled: Boolean(currentId),
  });

  const { data: caseInfo } = useQuery({
    queryKey: ["case", params.caseId],
    queryFn: () => fetchCase(params.caseId!),
    enabled: !currentId && Boolean(params.caseId),
  });

  // رندر نسخه‌ای: ارزیابی قدیمی با تعریف نسخه خودش نمایش داده می‌شود
  const def: FormDefinition | undefined = existing?.form_definition
    ? existing.form_definition
    : (formHead
        ? { code: formHead.code, version: formHead.version, sections: formHead.definition.sections }
        : headDef);

  useEffect(() => {
    if (existing && loadedFor !== existing.id) {
      setAnswers(existing.answers ?? {});
      setRowVersion(existing.row_version);
      setLoadedFor(existing.id);
    }
  }, [existing, loadedFor]);

  const status = existing?.status ?? "draft";
  const editable = !currentId
    ? true
    : Boolean(
        existing &&
        existing.author_user_id === user?.id &&
        (existing.status === "draft" || existing.status === "returned")
      );
  const canReview = Boolean(
    existing &&
    existing.status === "pending_review" &&
    user?.roles.includes("TECHNICAL_SUPERVISOR") &&
    user?.id !== existing.author_user_id
  );
  const isRevisionable = Boolean(
    existing &&
    existing.author_user_id === user?.id &&
    (existing.status === "pending_review" || existing.status === "approved")
  );

  const setValue = (path: string, v: unknown) => setAnswers((p) => ({ ...p, [path]: v }));

  const ensureSaved = async (): Promise<{ id: string; rowVersion: number }> => {
    if (!currentId) {
      const res = await createAssessmentDraft(params.caseId!, answers, selectedFormCode);
      setCurrentId(res.id);
      navigate(`/assessments/${res.id}`, { replace: true });
      return { id: res.id, rowVersion: res.row_version };
    }
    const res = await saveAssessmentDraft(currentId, answers, rowVersion);
    setRowVersion(res.row_version);
    return { id: currentId, rowVersion: res.row_version };
  };

  const refreshAll = (id: string) => {
    qc.invalidateQueries({ queryKey: ["assessment", id] });
    qc.invalidateQueries();
  };

  const doSave = async () => {
    setBusySave(true);
    setError(null);
    setMessage(null);
    try {
      const s = await ensureSaved();
      setMessage("پیش‌نویس ذخیره شد.");
      refreshAll(s.id);
    } catch (e) {
      setError(errDetail(e));
    } finally {
      setBusySave(false);
    }
  };

  const doFinalize = async () => {
    setBusyFinalize(true);
    setError(null);
    setMessage(null);
    try {
      const s = await ensureSaved();
      await finalizeAssessment(s.id, s.rowVersion);
      setConfirmFinalize(false);
      setMessage("ارزیابی نهایی شد و به صف بررسی مسئول فنی رفت.");
      refreshAll(s.id);
    } catch (e) {
      setError(errDetail(e));
      setConfirmFinalize(false);
    } finally {
      setBusyFinalize(false);
    }
  };

  const doApprove = async () => {
    if (!currentId || !window.confirm("تأیید این ارزیابی؟")) return;
    setError(null);
    try {
      await approveAssessment(currentId);
      setMessage("ارزیابی تأیید شد.");
      refreshAll(currentId);
    } catch (e) {
      setError(errDetail(e));
    }
  };

  const doReturn = async () => {
    if (!currentId) return;
    if (returnComment.trim().length < 5) {
      setError("ثبت توضیح برای برگشت الزامی است (بند ۷.۲)");
      return;
    }
    setError(null);
    try {
      await returnAssessment(currentId, returnComment.trim());
      setReturnOpen(false);
      setReturnComment("");
      setMessage("ارزیابی برای اصلاح به مشاور برگشت داده شد.");
      refreshAll(currentId);
    } catch (e) {
      setError(errDetail(e));
    }
  };

  const doRevision = async () => {
    if (!currentId || !window.confirm("ایجاد نسخه اصلاحی جدید متصل به این نسخه؟")) return;
    setError(null);
    try {
      const res = await createRevision(currentId);
      navigate(`/assessments/${res.id}`, { replace: true });
      setCurrentId(res.id);
      setLoadedFor(null);
      setMessage("نسخه اصلاحی ایجاد شد.");
      qc.invalidateQueries();
    } catch (e) {
      setError(errDetail(e));
    }
  };

  if (defLoading || (currentId && existingLoading)) return <CircularProgress />;
  if (!def) return <Alert severity="error">تعریف فرم بارگذاری نشد.</Alert>;

  const st = ASSESSMENT_STATUS_META[status] ?? { label: status, color: "default" as const };
  const headerCaseNumber = existing?.case_number ?? caseInfo?.case_number ?? "—";
  const headerApplicant = existing?.applicant_name ?? caseInfo?.applicant_name ?? "—";
  const formTitle = existing?.form_title ?? formHead?.title ?? null;

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={700}>
          فرم {def.code} — نسخه {def.version}
        </Typography>
        {formTitle && <Typography variant="body2" color="text.secondary">{formTitle}</Typography>}
        <Chip size="small" color={st.color} label={st.label} />
        <Typography variant="body2" color="text.secondary">
          پرونده {headerCaseNumber} — {headerApplicant}
          {existing ? ` — نسخه شماره ${existing.version_no}` : ""}
        </Typography>
        <Box flexGrow={1} />
        {editable && (
          <>
            <Button variant="outlined" onClick={doSave} disabled={busySave}>
              {busySave ? "در حال ذخیره…" : "ذخیره پیش‌نویس"}
            </Button>
            <Button variant="contained" onClick={() => setConfirmFinalize(true)} disabled={busyFinalize}>
              نهایی‌سازی
            </Button>
          </>
        )}
        {canReview && (
          <>
            <Button variant="contained" color="success" onClick={doApprove}>تأیید</Button>
            <Button variant="outlined" color="error" onClick={() => setReturnOpen(true)}>برگشت</Button>
          </>
        )}
        {isRevisionable && (
          <Button variant="outlined" onClick={doRevision}>ایجاد نسخه اصلاحی</Button>
        )}
        {existing && ["finalized", "pending_review", "approved"].includes(existing.status) && (
          <Button
            variant="outlined"
            onClick={async () => {
              try { await printAssessment(existing.id); } catch { /* رخداد چاپ غیربحرانی است */ }
              window.print();
            }}
          >
            چاپ فرم
          </Button>
        )}
      </Box>

      {status === "returned" && (
        <Alert severity="warning">
          این نسخه توسط مسئول فنی برگشت خورده است؛ پس از اصلاح، دوباره نهایی‌سازی کنید.
        </Alert>
      )}
      {message && <Alert severity="success" onClose={() => setMessage(null)}>{message}</Alert>}
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      {isCreateMode && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={700} mb={1}>انتخاب فرم ارزیابی</Typography>
          <Typography variant="body2" color="text.secondary" mb={1.5}>
            نوع فرم را پیش از شروع ثبت انتخاب کنید؛ پس از ذخیره پیش‌نویس، نوع فرم قابل تغییر نیست.
          </Typography>
          <Box display="flex" gap={2} flexWrap="wrap" alignItems="flex-start">
            <TextField
              select
              sx={{ minWidth: 320 }}
              size="small"
              label="نوع فرم"
              value={selectedFormCode}
              onChange={(e) => {
                setSelectedFormCode(e.target.value);
                setSearchParams({ form: e.target.value }, { replace: true });
              }}
            >
              {(formsList?.items ?? []).map((f) => (
                <MenuItem key={f.code} value={f.code}>
                  {f.code} — {f.title} (نسخه {f.version})
                </MenuItem>
              ))}
            </TextField>
            {formHead && (
              <Box sx={{ flex: 1, minWidth: 280 }}>
                <Typography variant="body2" fontWeight={600}>{formHead.title}</Typography>
                <Typography variant="caption" color="text.secondary">{formHead.description}</Typography>
                <Typography variant="caption" display="block" color="primary">جایگاه در گردش کار: {formHead.usage}</Typography>
              </Box>
            )}
          </Box>
        </Paper>
      )}

      {def.sections.map((sec: FormSectionDef) => (
        <Paper key={sec.key} sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={700} mb={1.5}>{sec.title}</Typography>
          {editable ? (
            <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "1fr 1fr" }} gap={2}>
              {sec.fields.map((f) => {
                const path = `${sec.key}.${f.key}`;
                return (
                  <Box key={path} gridColumn={f.type === "textarea" || f.type === "multiselect" ? "1 / -1" : undefined}>
                    <FieldInput field={f} path={path} value={answers[path]} onChange={setValue} />
                  </Box>
                );
              })}
            </Box>
          ) : (
            <Stack spacing={0.5}>
              {sec.fields.map((f) => {
                const path = `${sec.key}.${f.key}`;
                return <ReadOnlyField key={path} def={f} value={answers[path]} />;
              })}
            </Stack>
          )}
        </Paper>
      ))}

      {existing && existing.review_actions.length > 0 && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={700} mb={1}>سوابق بررسی</Typography>
          <Stack spacing={1}>
            {existing.review_actions.map((r) => (
              <Stack key={r.id} direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Chip size="small" color={r.decision === "approved" ? "success" : "error"}
                  label={r.decision === "approved" ? "تأیید" : "برگشت"} />
                <Typography variant="body2">{r.reviewer_name ?? "—"}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {r.created_at ? new Date(r.created_at).toLocaleString("fa-IR") : "—"}
                </Typography>
                {r.comment && <Typography variant="body2">توضیح: {r.comment}</Typography>}
              </Stack>
            ))}
          </Stack>
        </Paper>
      )}

      <Dialog open={confirmFinalize} onClose={() => setConfirmFinalize(false)} maxWidth="xs" fullWidth>
        <DialogTitle>نهایی‌سازی ارزیابی</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            فیلدهای لازم در سرور کنترل می‌شوند. پس از نهایی‌سازی، فرم بی‌ردپا تغییر نمی‌کند و
            برای اصلاح باید نسخه جدید بسازید (بند ۶.۲).
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmFinalize(false)}>انصراف</Button>
          <Button variant="contained" onClick={doFinalize} disabled={busyFinalize}>
            {busyFinalize ? "در حال نهایی‌سازی…" : "نهایی‌سازی"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={returnOpen} onClose={() => setReturnOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>برگشت برای اصلاح</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus fullWidth multiline minRows={3} margin="normal"
            label="توضیح برگشت (الزامی — بند ۷.۲)"
            value={returnComment}
            onChange={(e) => setReturnComment(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReturnOpen(false)}>انصراف</Button>
          <Button variant="contained" color="error" onClick={doReturn}>ثبت برگشت</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

function FieldInput({
  field, path, value, onChange,
}: {
  field: FormFieldDef;
  path: string;
  value: unknown;
  onChange: (path: string, v: unknown) => void;
}) {
  const label = field.label + (field.required ? " *" : "");
  if (field.type === "boolean") {
    return (
      <FormControlLabel
        control={<Checkbox checked={Boolean(value)} onChange={(e) => onChange(path, e.target.checked)} />}
        label={field.label}
      />
    );
  }
  if (field.type === "select") {
    return (
      <TextField
        select fullWidth size="small" label={label}
        value={(value as string) ?? ""}
        onChange={(e) => onChange(path, e.target.value || undefined)}
      >
        <MenuItem value="">—</MenuItem>
        {field.options.map((o) => (
          <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
        ))}
      </TextField>
    );
  }
  if (field.type === "multiselect") {
    const arr = Array.isArray(value) ? (value as string[]) : [];
    return (
      <Box>
        <Typography variant="caption" color="text.secondary">{label}</Typography>
        <Box display="grid" gridTemplateColumns={{ xs: "1fr", sm: "1fr 1fr", md: "1fr 1fr 1fr" }} gap={0.5} mt={0.5}>
          {field.options.map((o) => (
            <FormControlLabel
              key={o.value}
              control={
                <Checkbox
                  size="small"
                  checked={arr.includes(o.value)}
                  onChange={(e) => {
                    const next = e.target.checked ? [...arr, o.value] : arr.filter((v) => v !== o.value);
                    onChange(path, next.length ? next : undefined);
                  }}
                />
              }
              label={<Typography variant="body2">{o.label}</Typography>}
            />
          ))}
        </Box>
      </Box>
    );
  }
  if (field.type === "textarea") {
    return (
      <TextField fullWidth multiline minRows={2} size="small" label={label}
        value={(value as string) ?? ""}
        onChange={(e) => onChange(path, e.target.value || undefined)} />
    );
  }
  return (
    <TextField fullWidth size="small" label={label}
      value={(value as string) ?? ""}
      onChange={(e) => onChange(path, e.target.value || undefined)} />
  );
}

function ReadOnlyField({ def, value }: { def: FormFieldDef; value: unknown }) {
  let display = "—";
  if (def.type === "boolean") {
    display = value ? "بله" : "خیر";
  } else if (def.type === "select") {
    const v = value as string | undefined;
    display = v ? (def.options.find((o) => o.value === v)?.label ?? v) : "—";
  } else if (def.type === "multiselect") {
    const arr = Array.isArray(value) ? (value as string[]) : [];
    display = arr.length
      ? arr.map((v) => def.options.find((o) => o.value === v)?.label ?? v).join("، ")
      : "—";
  } else if (typeof value === "string" && value.trim()) {
    display = value;
  }
  return (
    <Stack direction="row" spacing={1}>
      <Typography variant="body2" sx={{ minWidth: 240, color: "text.secondary" }}>{def.label}:</Typography>
      <Typography variant="body2">{display}</Typography>
    </Stack>
  );
}
