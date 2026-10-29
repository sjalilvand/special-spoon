import { useMemo, useState } from "react";
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControlLabel, IconButton, MenuItem, Paper, Stack, Switch, TextField,
  Tooltip, Typography, Snackbar,
} from "@mui/material";
import AddCircleOutlineRoundedIcon from "@mui/icons-material/AddCircleOutlineRounded";
import ArrowDownwardIcon from "@mui/icons-material/ArrowDownward";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import EditRoundedIcon from "@mui/icons-material/EditRounded";
import FactCheckRoundedIcon from "@mui/icons-material/FactCheckRounded";
import VisibilityRoundedIcon from "@mui/icons-material/VisibilityRounded";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { errDetail } from "../api/client";
import {
  FORM_FIELD_TYPE_LABELS,
  type FormFieldDef,
  type FormFieldType,
  type FormTemplate,
  type FormUpsertPayload,
  createFormTemplate,
  deleteFormTemplate,
  fetchFormTemplates,
  updateFormTemplate,
} from "../api/forms";
import { EmptyFieldsHint, FormPreview } from "../components/FormRenderer";

/** فاز ۶۱ - فرم‌ساز گرافیکی: مدیر فرم‌های نظرسنجی/پذیرش/سفارشی می‌سازد.
 * ساختار فیلدها JSON است؛ انواع مطابق FIELD_TYPES سمت سرور محدود شده‌اند. */

const KIND_LABELS: Record<FormTemplate["kind"], string> = {
  survey: "نظرسنجی",
  intake: "پذیرش",
  custom: "سفارشی",
};

const OPTION_TYPES: FormFieldType[] = ["select", "radio", "checkbox"];

function uid() {
  return "f_" + Math.random().toString(36).slice(2, 10);
}

interface FieldDraft extends FormFieldDef {}

function FieldEditorDialog({
  open, initial, onClose, onSave,
}: {
  open: boolean;
  initial: FieldDraft | null;
  onClose: () => void;
  onSave: (f: FieldDraft) => void;
}) {
  const [type, setType] = useState<FormFieldType>(initial?.type ?? "text");
  const [label, setLabel] = useState(initial?.label ?? "");
  const [required, setRequired] = useState(initial?.required ?? false);
  const [help, setHelp] = useState(initial?.help ?? "");
  const [options, setOptions] = useState<string>(initial?.options?.join("\n") ?? "");

  // هر بار بازشدن، از دادهٔ فیلد انتخابی پر شود
  const [seenKey, setSeenKey] = useState("");
  const key = `${open}-${initial?.id ?? "new"}`;
  if (open && key !== seenKey) {
    setSeenKey(key);
    setType(initial?.type ?? "text");
    setLabel(initial?.label ?? "");
    setRequired(initial?.required ?? false);
    setHelp(initial?.help ?? "");
    setOptions(initial?.options?.join("\n") ?? "");
  }

  const error =
    !label.trim() ? "برچسب فیلد لازم است"
    : OPTION_TYPES.includes(type) && !options.split("\n").map((o) => o.trim()).filter(Boolean).length
      ? "حداقل یک گزینه لازم است"
    : null;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{initial ? "ویرایش فیلد" : "افزودن فیلد"}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField
            select fullWidth size="small" label="نوع فیلد" value={type}
            onChange={(e) => setType(e.target.value as FormFieldType)}
          >
            {(Object.keys(FORM_FIELD_TYPE_LABELS) as FormFieldType[]).map((t) => (
              <MenuItem key={t} value={t}>{FORM_FIELD_TYPE_LABELS[t]}</MenuItem>
            ))}
          </TextField>
          <TextField
            fullWidth size="small" label="برچسب (سؤال / عنوان)" value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
          {OPTION_TYPES.includes(type) ? (
            <TextField
              fullWidth size="small" multiline minRows={3}
              label="گزینه‌ها (هر سطر یک گزینه)" value={options}
              onChange={(e) => setOptions(e.target.value)}
              placeholder={"گزینهٔ اول\nگزینهٔ دوم"}
            />
          ) : null}
          <TextField
            fullWidth size="small" label="راهنما (اختیاری)" value={help}
            onChange={(e) => setHelp(e.target.value)}
          />
          <FormControlLabel
            control={<Switch checked={required} onChange={(e) => setRequired(e.target.checked)} />}
            label="پاسخ به این فیلد الزامی است"
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button
          variant="contained"
          disabled={!!error}
          onClick={() =>
            onSave({
              id: initial?.id ?? uid(),
              type,
              label: label.trim(),
              required,
              help: help.trim() || undefined,
              options: OPTION_TYPES.includes(type)
                ? options.split("\n").map((o) => o.trim()).filter(Boolean)
                : undefined,
            })
          }
        >
          ذخیرهٔ فیلد
        </Button>
      </DialogActions>
      {error ? <Alert severity="warning" sx={{ mx: 2, mb: 2 }}>{error}</Alert> : null}
    </Dialog>
  );
}

function TemplateDialog({
  open, initial, onClose, onSaved,
}: {
  open: boolean;
  initial: FormTemplate | null;
  onClose: () => void;
  onSaved: (msg: string) => void;
}) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [code, setCode] = useState("");
  const [kind, setKind] = useState<FormTemplate["kind"]>("survey");
  const [description, setDescription] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isDefaultCallSurvey, setIsDefaultCallSurvey] = useState(false);
  const [fields, setFields] = useState<FieldDraft[]>([]);
  const [fieldDlg, setFieldDlg] = useState<{ open: boolean; index: number | null }>({ open: false, index: null });
  const [preview, setPreview] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [seenKey, setSeenKey] = useState("");
  const key = `${open}-${initial?.id ?? "new"}`;
  if (open && key !== seenKey) {
    setSeenKey(key);
    setTitle(initial?.title ?? "");
    setCode(initial?.code ?? "");
    setKind(initial?.kind ?? "survey");
    setDescription(initial?.description ?? "");
    setIsActive(initial?.is_active ?? true);
    setIsDefaultCallSurvey(initial?.is_default_call_survey ?? false);
    setFields(initial?.fields ?? []);
    setError(null);
  }

  const save = useMutation({
    mutationFn: async () => {
      const payload: FormUpsertPayload = {
        title: title.trim(),
        code: code.trim() || undefined,
        description: description.trim() || undefined,
        kind,
        fields,
        is_active: isActive,
        is_default_call_survey: isDefaultCallSurvey && kind === "survey",
      };
      return initial ? updateFormTemplate(initial.id, payload) : createFormTemplate(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["form-templates"] });
      onSaved(initial ? "فرم به‌روزرسانی شد" : "فرم ساخته شد");
      onClose();
    },
    onError: (e) => setError(errDetail(e)),
  });

  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= fields.length) return;
    const next = [...fields];
    [next[i], next[j]] = [next[j], next[i]];
    setFields(next);
  };

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogTitle>{initial ? `ویرایش فرم: ${initial.title}` : "فرم جدید"}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <TextField
                fullWidth size="small" label="عنوان فرم *" value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
              <TextField
                fullWidth size="small" label="کد فرم (اختیاری — خودکار ساخته می‌شود)" value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </Stack>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <TextField
                select fullWidth size="small" label="نوع فرم" value={kind}
                onChange={(e) => setKind(e.target.value as FormTemplate["kind"])}
              >
                <MenuItem value="survey">نظرسنجی</MenuItem>
                <MenuItem value="intake">پذیرش / ارزیابی</MenuItem>
                <MenuItem value="custom">سفارشی</MenuItem>
              </TextField>
              <Box sx={{ flex: 1, display: "flex", alignItems: "center", gap: 3, flexWrap: "wrap" }}>
                <FormControlLabel
                  control={<Switch checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />}
                  label="فعال"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={isDefaultCallSurvey}
                      disabled={kind !== "survey"}
                      onChange={(e) => setIsDefaultCallSurvey(e.target.checked)}
                    />
                  }
                  label="نظرسنجی پیش‌فرض پس از تماس"
                />
              </Box>
            </Stack>
            <TextField
              fullWidth size="small" multiline minRows={2} label="توضیح" value={description}
              onChange={(e) => setDescription(e.target.value)}
            />

            <Paper variant="outlined" sx={{ p: 1.5 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
                <Typography variant="subtitle2">فیلدهای فرم ({fields.length})</Typography>
                <Stack direction="row" spacing={1}>
                  <Button size="small" startIcon={<VisibilityRoundedIcon />} disabled={!fields.length} onClick={() => setPreview(true)}>
                    پیش‌نمایش
                  </Button>
                  <Button
                    size="small" variant="contained"
                    startIcon={<AddCircleOutlineRoundedIcon />}
                    onClick={() => setFieldDlg({ open: true, index: null })}
                  >
                    افزودن فیلد
                  </Button>
                </Stack>
              </Stack>
              {fields.length === 0 ? <EmptyFieldsHint /> : (
                <Stack spacing={0.5}>
                  {fields.map((f, i) => (
                    <Stack
                      key={f.id}
                      direction="row"
                      alignItems="center"
                      spacing={1}
                      sx={{ px: 1, py: 0.5, borderRadius: 1, bgcolor: i % 2 ? "#fafafa" : "transparent" }}
                    >
                      <Chip size="small" label={FORM_FIELD_TYPE_LABELS[f.type]} variant="outlined" sx={{ minWidth: 110 }} />
                      <Typography sx={{ flex: 1, fontSize: 14 }}>
                        {f.label}{f.required ? " *" : ""}
                      </Typography>
                      {f.options?.length ? (
                        <Typography variant="caption" color="text.secondary">{f.options.length} گزینه</Typography>
                      ) : null}
                      <Tooltip title="بالا"><span>
                        <IconButton size="small" disabled={i === 0} onClick={() => move(i, -1)}><ArrowUpwardIcon /></IconButton>
                      </span></Tooltip>
                      <Tooltip title="پایین"><span>
                        <IconButton size="small" disabled={i === fields.length - 1} onClick={() => move(i, 1)}><ArrowDownwardIcon /></IconButton>
                      </span></Tooltip>
                      <Tooltip title="ویرایش">
                        <IconButton size="small" onClick={() => setFieldDlg({ open: true, index: i })}><EditRoundedIcon /></IconButton>
                      </Tooltip>
                      <Tooltip title="حذف">
                        <IconButton size="small" color="error" onClick={() => setFields(fields.filter((_, x) => x !== i))}>
                          <DeleteOutlineRoundedIcon />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  ))}
                </Stack>
              )}
            </Paper>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button variant="contained" disabled={!title.trim() || save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? "در حال ذخیره…" : "ذخیرهٔ فرم"}
          </Button>
        </DialogActions>
      </Dialog>

      <FieldEditorDialog
        open={fieldDlg.open}
        initial={fieldDlg.index !== null ? fields[fieldDlg.index] : null}
        onClose={() => setFieldDlg({ open: false, index: null })}
        onSave={(f) => {
          setFields((prev) =>
            fieldDlg.index !== null
              ? prev.map((x, i) => (i === fieldDlg.index ? f : x))
              : [...prev, f],
          );
          setFieldDlg({ open: false, index: null });
        }}
      />

      <Dialog open={preview} onClose={() => setPreview(false)} maxWidth="sm" fullWidth>
        <DialogTitle>پیش‌نمایش فرم</DialogTitle>
        <DialogContent><FormPreview template={{ title, description, fields }} /></DialogContent>
        <DialogActions><Button onClick={() => setPreview(false)}>بستن</Button></DialogActions>
      </Dialog>

      <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)}>
        <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>
      </Snackbar>
    </>
  );
}

export default function FormBuilderPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [dlg, setDlg] = useState<{ open: boolean; template: FormTemplate | null }>({ open: false, template: null });
  const [toast, setToast] = useState<string | null>(null);
  const [delError, setDelError] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["form-templates"],
    queryFn: fetchFormTemplates,
  });

  const del = useMutation({
    mutationFn: deleteFormTemplate,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["form-templates"] });
      setToast("فرم حذف شد");
    },
    onError: (e) => {
      // سرور در صورت وجود پاسخ، فرم را غیرفعال می‌کند و 409 می‌دهد — دوباره بخوان
      qc.invalidateQueries({ queryKey: ["form-templates"] });
      setDelError(errDetail(e));
    },
  });

  const items = useMemo(() => data ?? [], [data]);

  return (
    <Box sx={{ maxWidth: 1000, mx: "auto", p: { xs: 1.5, md: 3 } }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Box>
          <Typography variant="h6" fontWeight={700}>فرم‌ساز و نظرسنجی</Typography>
          <Typography variant="body2" color="text.secondary">
            ساخت فرم‌های نظرسنجی، پذیرش و سفارشی — نظرسنجیِ پیش‌فرض پس از پایان هر تماس تلفنی به مراجع نمایش داده می‌شود.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddCircleOutlineRoundedIcon />} onClick={() => setDlg({ open: true, template: null })}>
          فرم جدید
        </Button>
      </Stack>

      {isLoading ? <Typography color="text.secondary">در حال بارگذاری…</Typography> : null}
      {error ? <Alert severity="error">{errDetail(error)}</Alert> : null}
      {!isLoading && !error && items.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}>
          <Typography color="text.secondary">هنوز فرمی ساخته نشده است.</Typography>
        </Paper>
      ) : null}

      <Stack spacing={1.5}>
        {items.map((t) => (
          <Paper key={t.id} variant="outlined" sx={{ p: 2 }}>
            <Stack direction={{ xs: "column", md: "row" }} alignItems={{ md: "center" }} spacing={1.5}>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                  <Typography fontWeight={700}>{t.title}</Typography>
                  <Chip size="small" label={KIND_LABELS[t.kind]} color="primary" variant="outlined" />
                  {t.is_default_call_survey ? <Chip size="small" label="پیش‌فرض تماس" color="secondary" /> : null}
                  {!t.is_active ? <Chip size="small" label="غیرفعال" /> : null}
                </Stack>
                <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.5 }}>
                  کد: {t.code} — {t.fields?.length ?? 0} فیلد — {t.response_count ?? 0} پاسخ ثبت‌شده
                </Typography>
                {t.description ? (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{t.description}</Typography>
                ) : null}
              </Box>
              <Stack direction="row" spacing={1}>
                <Tooltip title="پاسخ‌ها">
                  <IconButton onClick={() => navigate(`/form-responses/${t.id}`)}><FactCheckRoundedIcon /></IconButton>
                </Tooltip>
                <Tooltip title="ویرایش">
                  <IconButton onClick={() => setDlg({ open: true, template: t })}><EditRoundedIcon /></IconButton>
                </Tooltip>
                <Tooltip title="حذف">
                  <IconButton color="error" onClick={() => del.mutate(t.id)}><DeleteOutlineRoundedIcon /></IconButton>
                </Tooltip>
              </Stack>
            </Stack>
          </Paper>
        ))}
      </Stack>

      <TemplateDialog
        open={dlg.open}
        initial={dlg.template}
        onClose={() => setDlg({ open: false, template: null })}
        onSaved={(msg) => setToast(msg)}
      />

      <Snackbar open={!!toast} autoHideDuration={4000} onClose={() => setToast(null)}>
        <Alert severity="success" onClose={() => setToast(null)}>{toast}</Alert>
      </Snackbar>
      <Snackbar open={!!delError} autoHideDuration={6000} onClose={() => setDelError(null)}>
        <Alert severity="warning" onClose={() => setDelError(null)}>{delError}</Alert>
      </Snackbar>
    </Box>
  );
}
