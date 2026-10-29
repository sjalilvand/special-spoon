import { useEffect, useState } from "react";
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle,
  IconButton, MenuItem, Paper, Snackbar, Stack, TextField, Tooltip, Typography,
} from "@mui/material";
import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import VisibilityRoundedIcon from "@mui/icons-material/VisibilityRounded";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { errDetail } from "../api/client";
import {
  type FormResponseRow,
  type FormTemplate,
  fetchFormResponses,
  fetchFormTemplates,
} from "../api/forms";
import FormRenderer, { responsesToCsv } from "../components/FormRenderer";
import { formatJalaliDateTime } from "../utils/jalali";

/** فاز ۶۱ - پاسخ‌های فرم: مدیر پاسخ‌های ثبت‌شدهٔ هر فرم را می‌بیند و CSV می‌گیرد. */

function ResponsesTable({ template, rows }: { template: FormTemplate; rows: FormResponseRow[] }) {
  const [view, setView] = useState<FormResponseRow | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const exportCsv = () => {
    const csv = responsesToCsv(
      template.fields ?? [],
      rows.map((r) => ({ respondent_name: r.respondent_name, submitted_at: r.submitted_at, answers: r.answers })),
    );
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${template.code || "form"}-responses.csv`;
    a.click();
    URL.revokeObjectURL(url);
    setToast("فایل CSV دانلود شد");
  };

  return (
    <>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
        <Typography variant="body2" color="text.secondary">{rows.length} پاسخ</Typography>
        <Button size="small" startIcon={<DownloadRoundedIcon />} disabled={!rows.length} onClick={exportCsv}>
          دریافت CSV (اکسل)
        </Button>
      </Stack>
      <Stack spacing={1}>
        {rows.map((r) => (
          <Paper key={r.id} variant="outlined" sx={{ p: 1.5 }}>
            <Stack direction="row" alignItems="center" spacing={1.5}>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{ fontWeight: 600, fontSize: 14 }}>
                  {r.respondent_name ?? "کاربر حذف‌شده"}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {r.submitted_at ? formatJalaliDateTime(r.submitted_at) : "—"}
                  {r.call_duration_sec !== null && r.call_duration_sec !== undefined
                    ? ` — مرتبط با تماس (${Math.floor(r.call_duration_sec / 60)}:${String(r.call_duration_sec % 60).padStart(2, "0")})`
                    : ""}
                </Typography>
              </Box>
              <Tooltip title="مشاهدهٔ پاسخ">
                <IconButton onClick={() => setView(r)}><VisibilityRoundedIcon /></IconButton>
              </Tooltip>
            </Stack>
          </Paper>
        ))}
        {rows.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 3, textAlign: "center" }}>
            <Typography color="text.secondary">هنوز پاسخی ثبت نشده است.</Typography>
          </Paper>
        ) : null}
      </Stack>

      <Dialog open={!!view} onClose={() => setView(null)} maxWidth="sm" fullWidth>
        <DialogTitle>پاسخ {view?.respondent_name ?? ""}</DialogTitle>
        <DialogContent>
          {view && template ? (
            <FormRenderer template={template} values={view.answers} readOnly />
          ) : null}
        </DialogContent>
        <DialogActions><Button onClick={() => setView(null)}>بستن</Button></DialogActions>
      </Dialog>

      <Snackbar open={!!toast} autoHideDuration={3000} onClose={() => setToast(null)}>
        <Alert severity="success" onClose={() => setToast(null)}>{toast}</Alert>
      </Snackbar>
    </>
  );
}

export default function FormResponsesPage() {
  const { templateId } = useParams();
  const navigate = useNavigate();
  const [selected, setSelected] = useState<string>(templateId ?? "");

  // همگام‌سازی پارامتر مسیر با انتخاب (ناوبری از فرم‌ساز)
  useEffect(() => {
    if (templateId) setSelected(templateId);
  }, [templateId]);

  const { data: templates } = useQuery({ queryKey: ["form-templates"], queryFn: fetchFormTemplates });

  const { data, isLoading, error } = useQuery({
    queryKey: ["form-responses", selected],
    queryFn: () => fetchFormResponses(selected),
    enabled: !!selected,
  });

  return (
    <Box sx={{ maxWidth: 1000, mx: "auto", p: { xs: 1.5, md: 3 } }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Box>
          <Typography variant="h6" fontWeight={700}>پاسخ‌های فرم</Typography>
          <Typography variant="body2" color="text.secondary">
            مشاهدهٔ پاسخ‌های ثبت‌شدهٔ مراجعان و همکاران برای هر فرم
          </Typography>
        </Box>
        {selected ? (
          <Chip
            label="بازگشت به فهرست فرم‌ها"
            onClick={() => navigate("/form-builder")}
            variant="outlined"
          />
        ) : null}
      </Stack>

      <TextField
        select fullWidth size="small" sx={{ mb: 2 }}
        label="انتخاب فرم"
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
      >
        {(templates ?? []).map((t) => (
          <MenuItem key={t.id} value={t.id}>{t.title}</MenuItem>
        ))}
      </TextField>

      {isLoading ? <Typography color="text.secondary">در حال بارگذاری…</Typography> : null}
      {error ? <Alert severity="error">{errDetail(error)}</Alert> : null}
      {!selected ? (
        <Paper variant="outlined" sx={{ p: 4, textAlign: "center" }}>
          <Typography color="text.secondary">یک فرم را از فهرست بالا انتخاب کنید.</Typography>
        </Paper>
      ) : null}
      {selected && data ? <ResponsesTable template={data.template} rows={data.items} /> : null}
      {selected && !isLoading && !data && !error ? (
        <Paper variant="outlined" sx={{ p: 3, textAlign: "center" }}>
          <Typography color="text.secondary">داده‌ای یافت نشد.</Typography>
        </Paper>
      ) : null}
    </Box>
  );
}
