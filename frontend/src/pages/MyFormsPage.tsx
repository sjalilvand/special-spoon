import { useState } from "react";
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle,
  Paper, Snackbar, Stack, Typography,
} from "@mui/material";
import HistoryIcon from "@mui/icons-material/History";
import RateReviewRoundedIcon from "@mui/icons-material/RateReviewRounded";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { errDetail } from "../api/client";
import {
  type PendingForm,
  fetchMyForms,
  submitFormResponse,
} from "../api/forms";
import FormRenderer, { validateFormValues, type FormValues } from "../components/FormRenderer";
import { formatJalaliDateTime } from "../utils/jalali";

/** فاز ۶۱ - فرم‌های من: نظرسنجی‌های در انتظار (پس از تماس) + تاریخچهٔ پاسخ‌ها.
 * تکمیل نظرسنجی همین‌جا به‌صورت پنجرهٔ باز انجام می‌شود. */

function SurveyDialog({
  pending, onClose,
}: {
  pending: PendingForm | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [values, setValues] = useState<FormValues>({});
  const [error, setError] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: async () => {
      if (!pending) throw new Error("no pending");
      const err = validateFormValues(pending.template.fields ?? [], values);
      if (err) throw new Error(err);
      return submitFormResponse(pending.template.id, values, pending.call_id);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-forms"] });
      onClose();
    },
    onError: (e) => setError(e instanceof Error ? e.message : errDetail(e)),
  });

  return (
    <Dialog open={!!pending} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{pending?.template.title ?? ""}</DialogTitle>
      <DialogContent>
        {pending ? (
          <Stack spacing={2}>
            <Typography variant="body2" color="text.secondary">
              {pending.template.description}
            </Typography>
            {pending.caller_name ? (
              <Typography variant="caption" color="text.secondary">
                تماس با {pending.caller_name}
                {pending.call_duration_sec ? ` — مدت ${Math.floor(pending.call_duration_sec / 60)}:${String(pending.call_duration_sec % 60).padStart(2, "0")}` : ""}
              </Typography>
            ) : null}
            <FormRenderer
              template={pending.template}
              values={values}
              onChange={(id, v) => setValues((s) => ({ ...s, [id]: v }))}
            />
            {error ? <Alert severity="error">{error}</Alert> : null}
          </Stack>
        ) : null}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>بعداً</Button>
        <Button variant="contained" disabled={submit.isPending} onClick={() => submit.mutate()}>
          {submit.isPending ? "در حال ارسال…" : "ثبت پاسخ"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function MyFormsPage() {
  const [survey, setSurvey] = useState<PendingForm | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({ queryKey: ["my-forms"], queryFn: fetchMyForms });

  return (
    <Box sx={{ maxWidth: 800, mx: "auto", p: { xs: 1.5, md: 3 } }}>
      <Typography variant="h6" fontWeight={700} sx={{ mb: 0.5 }}>فرم‌های من</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        نظرسنجی‌هایی که پس از پایان تماس برای شما فعال شده و فرم‌هایی که تکمیل کرده‌اید
      </Typography>

      {isLoading ? <Typography color="text.secondary">در حال بارگذاری…</Typography> : null}
      {error ? <Alert severity="error">{errDetail(error)}</Alert> : null}

      {/* در انتظار تکمیل */}
      <Typography variant="subtitle2" sx={{ mt: 1, mb: 1 }}>
        در انتظار تکمیل {data?.pending?.length ? `(${data.pending.length})` : ""}
      </Typography>
      {data?.pending?.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 2.5, textAlign: "center" }}>
          <Typography color="text.secondary" variant="body2">نظرسنجی در انتظار تکمیل ندارید.</Typography>
        </Paper>
      ) : null}
      <Stack spacing={1.5} sx={{ mb: 3 }}>
        {(data?.pending ?? []).map((p) => (
          <Paper key={p.call_id} variant="outlined" sx={{ p: 2, bgcolor: "#fffdf5", borderColor: "#f0e0b0" }}>
            <Stack direction={{ xs: "column", sm: "row" }} alignItems={{ sm: "center" }} spacing={1.5}>
              <Box sx={{ flex: 1 }}>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                  <Typography fontWeight={700}>{p.template.title}</Typography>
                  <Chip size="small" label="نظرسنجی" color="warning" />
                </Stack>
                <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.5 }}>
                  {p.caller_name ? `تماس با ${p.caller_name} — ` : ""}
                  {p.call_ended_at ? `پایان تماس: ${formatJalaliDateTime(p.call_ended_at)}` : ""}
                </Typography>
              </Box>
              <Button variant="contained" startIcon={<RateReviewRoundedIcon />} onClick={() => setSurvey(p)}>
                تکمیل نظرسنجی
              </Button>
            </Stack>
          </Paper>
        ))}
      </Stack>

      {/* تاریخچه */}
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
        <HistoryIcon fontSize="small" />
        <Typography variant="subtitle2">تاریخچهٔ پاسخ‌های من</Typography>
      </Stack>
      <Stack spacing={1}>
        {(data?.history ?? []).map((h) => (
          <Paper key={h.id} variant="outlined" sx={{ p: 1.5 }}>
            <Stack direction="row" alignItems="center" spacing={1.5}>
              <Box sx={{ flex: 1 }}>
                <Typography sx={{ fontSize: 14, fontWeight: 600 }}>{h.template_title ?? "فرم"}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {h.submitted_at ? formatJalaliDateTime(h.submitted_at) : "—"}
                </Typography>
              </Box>
              <Chip size="small" label="ثبت شد" color="success" variant="outlined" />
            </Stack>
          </Paper>
        ))}
        {data?.history?.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 2.5, textAlign: "center" }}>
            <Typography color="text.secondary" variant="body2">تاکنون فرمی تکمیل نکرده‌اید.</Typography>
          </Paper>
        ) : null}
      </Stack>

      <SurveyDialog
        pending={survey}
        onClose={() => {
          setSurvey(null);
          setToast("نظرسنجی ثبت شد — سپاسگزاریم");
        }}
      />

      <Snackbar open={!!toast} autoHideDuration={4000} onClose={() => setToast(null)}>
        <Alert severity="success" onClose={() => setToast(null)}>{toast}</Alert>
      </Snackbar>
    </Box>
  );
}
