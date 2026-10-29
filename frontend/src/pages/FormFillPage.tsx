import { useMemo, useState } from "react";
import {
  Alert, Box, Button, CircularProgress, Paper, Stack, Typography,
} from "@mui/material";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { errDetail } from "../api/client";
import { fetchFormTemplateForFill, submitFormResponse } from "../api/forms";
import FormRenderer, { validateFormValues, type FormValues } from "../components/FormRenderer";

/** فاز ۶۱ - تکمیل فرم از طریق لینک مستقیم (/forms/:templateId/fill?call=…)
 * نظرسنجی پس از تماس می‌تواند از همین صفحه تکمیل شود. */

export default function FormFillPage() {
  const { templateId } = useParams();
  const [params] = useSearchParams();
  const callId = params.get("call") ?? undefined;
  const navigate = useNavigate();
  const [values, setValues] = useState<FormValues>({});
  const [error, setError] = useState<string | null>(null);
  const [doneId, setDoneId] = useState<string | null>(null);

  const { data: template, isLoading, error: loadError } = useQuery({
    queryKey: ["form-template-fill", templateId],
    queryFn: () => fetchFormTemplateForFill(templateId!),
    enabled: !!templateId,
  });

  const submit = useMutation({
    mutationFn: async () => {
      if (!template) throw new Error("فرم بارگذاری نشده است");
      const err = validateFormValues(template.fields ?? [], values);
      if (err) throw new Error(err);
      return submitFormResponse(template.id, values, callId);
    },
    onSuccess: (res) => setDoneId(res.id),
    onError: (e) => setError(e instanceof Error ? e.message : errDetail(e)),
  });

  const requiredCount = useMemo(
    () => (template?.fields ?? []).filter((f) => f.type !== "heading" && f.required).length,
    [template],
  );

  if (isLoading) return <CircularProgress sx={{ display: "block", mx: "auto", mt: 8 }} />;
  if (loadError) {
    return (
      <Box sx={{ maxWidth: 700, mx: "auto", p: 3 }}>
        <Alert severity="error">{errDetail(loadError)}</Alert>
      </Box>
    );
  }

  if (doneId) {
    return (
      <Box sx={{ maxWidth: 700, mx: "auto", p: { xs: 1.5, md: 3 } }}>
        <Paper variant="outlined" sx={{ p: 5, textAlign: "center" }}>
          <CheckCircleRoundedIcon color="success" sx={{ fontSize: 56, mb: 1 }} />
          <Typography variant="h6" fontWeight={700}>پاسخ شما ثبت شد</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            از وقتی که فرصت کردید سپاسگزاریم.
          </Typography>
          <Button variant="contained" sx={{ mt: 3 }} onClick={() => navigate("/")}>
            بازگشت
          </Button>
        </Paper>
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 700, mx: "auto", p: { xs: 1.5, md: 3 } }}>
      <Typography variant="h6" fontWeight={700}>{template?.title}</Typography>
      {template?.description ? (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{template.description}</Typography>
      ) : (
        <Box sx={{ mb: 2 }} />
      )}
      <Paper variant="outlined" sx={{ p: { xs: 2, md: 3 } }}>
        {template ? (
          <>
            <FormRenderer
              template={template}
              values={values}
              onChange={(id, v) => setValues((s) => ({ ...s, [id]: v }))}
            />
            {error ? <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert> : null}
            <Stack direction="row" justifyContent="flex-end" sx={{ mt: 3 }}>
              <Button
                variant="contained"
                disabled={submit.isPending}
                onClick={() => submit.mutate()}
              >
                {submit.isPending ? "در حال ارسال…" : `ثبت پاسخ${requiredCount ? ` (${requiredCount} فیلد اجباری)` : ""}`}
              </Button>
            </Stack>
          </>
        ) : null}
      </Paper>
    </Box>
  );
}
