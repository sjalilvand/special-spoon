// فاز ۳۶ - B28 سند جامع: یکپارچه‌سازی‌های بیرونی — وضعیت سرویس‌ها + صف پیامک
import {
  Box, Button, Chip, Paper, Snackbar, Alert, Stack, Tab, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Tabs, Typography, LinearProgress, MenuItem, TextField,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { errDetail } from "../api/client";
import {
  IntegrationStatus, SmsRow, fetchIntegrationsConfig, fetchSmsOutbox,
  processSmsOutbox, retrySmsRow,
} from "../api/integrations";

const statusChip = (s: string) => {
  const map: Record<string, { label: string; color: "success" | "default" | "warning" | "error" | "info" }> = {
    pending: { label: "در انتظار ارسال", color: "warning" },
    sent: { label: "ارسال‌شده", color: "success" },
    failed: { label: "ناموفق", color: "error" },
    disabled: { label: "غیرفعال", color: "default" },
  };
  const it = map[s] ?? { label: s, color: "default" as const };
  return <Chip size="small" label={it.label} color={it.color} variant="outlined" />;
};

const providerLabel = (p: string) =>
  ({ log: "log (توسعه/آزمون)", kavenegar: "کاوه‌نگار", smsir: "SMS.ir" }[p] ?? p);

function IntegrationCard({ title, decision, st }: { title: string; decision: string; st: IntegrationStatus }) {
  return (
    <Paper sx={{ p: 2, display: "flex", flexDirection: "column", gap: 1 }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between">
        <Typography variant="subtitle1" fontWeight={700}>{title}</Typography>
        <Chip size="small" label={`آماده: ${st.ready ? "بله" : "خیر"}`} color={st.ready ? "success" : "default"} />
      </Stack>
      <Typography variant="body2" color="text.secondary">
        سرویس پیکربندی‌شده: <b>{st.configured}</b> · تصمیم سند: <b>{decision}</b>
      </Typography>
    </Paper>
  );
}

export default function IntegrationsPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const config = useQuery({ queryKey: ["integrations-config"], queryFn: fetchIntegrationsConfig });
  const outbox = useQuery({
    queryKey: ["sms-outbox", statusFilter, page],
    queryFn: () => fetchSmsOutbox({ status: statusFilter || undefined, page, page_size: 30 }),
  });

  const processMut = useMutation({
    mutationFn: () => processSmsOutbox(50),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["sms-outbox"] });
      setOkMsg(`ارسال انجام شد: ${r.sent} موفق، ${r.failed} ناموفق، ${r.disabled} غیرفعال`);
    },
    onError: (e) => setError(errDetail(e)),
  });

  const retryMut = useMutation({
    mutationFn: (id: string) => retrySmsRow(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sms-outbox"] });
      setOkMsg("ردیف برای تلاش مجدد بازگذاری شد");
    },
    onError: (e) => setError(errDetail(e)),
  });

  const sms = config.data?.sms;

  return (
    <Box p={3}>
      <Typography variant="h5" fontWeight={800} mb={2}>یکپارچه‌سازی‌های بیرونی (B28)</Typography>

      {config.isLoading && <LinearProgress sx={{ mb: 2 }} />}
      {config.isError && <Alert severity="error" sx={{ mb: 2 }}>{errDetail(config.error)}</Alert>}

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label="وضعیت سرویس‌ها" />
        <Tab label="صف پیامک" />
      </Tabs>

      {tab === 0 && config.data && (
        <Box>
          {sms && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" fontWeight={700} mb={1}>پیامک (B28)</Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                <Chip size="small" label={`فعال: ${sms.enabled ? "بله" : "خیر"}`} color={sms.enabled ? "success" : "default"} />
                <Chip size="small" label={`آداپتور فعال: ${providerLabel(sms.active_provider)}`} />
                {sms.fallback_applied && <Chip size="small" label="fallback از آداپتور کلیددار" color="warning" />}
                <Chip size="small" label={`سقف تلاش: ${sms.max_attempts}`} variant="outlined" />
              </Stack>
              <Typography variant="body2" color="text.secondary" mt={1}>
                آداپتور پلاگین‌پذیر همان الگوی D02/D03/D07 — پیش‌فرض «log» بدون کلید؛
                کلید سرویس هرگز در این صفحه یا هر پاسخ API نشان داده نمی‌شود. ارسال با صف
                پایگاه‌داده انجام می‌شود (بدهی ADR-02 صف کار).
              </Typography>
            </Paper>
          )}
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
            <IntegrationCard title="درگاه پرداخت" decision={config.data.payment_gateway.decision} st={config.data.payment_gateway} />
            <IntegrationCard title="سرویس نقشه" decision={config.data.maps.decision} st={config.data.maps} />
            <IntegrationCard title="ایمیل (SMTP)" decision={config.data.email.decision} st={config.data.email} />
            <IntegrationCard title="هوش مصنوعی" decision={config.data.ai.decision} st={config.data.ai} />
          </Box>
        </Box>
      )}

      {tab === 1 && (
        <Box>
          <Stack direction="row" spacing={2} alignItems="center" mb={2} flexWrap="wrap" useFlexGap>
            <TextField
              select size="small" label="وضعیت" sx={{ minWidth: 180 }}
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            >
              <MenuItem value="">همه</MenuItem>
              <MenuItem value="pending">در انتظار ارسال</MenuItem>
              <MenuItem value="sent">ارسال‌شده</MenuItem>
              <MenuItem value="failed">ناموفق</MenuItem>
              <MenuItem value="disabled">غیرفعال</MenuItem>
            </TextField>
            <Button
              variant="contained"
              onClick={() => processMut.mutate()}
              disabled={processMut.isPending}
            >
              اجرای ارسال صف
            </Button>
            {outbox.data?.summary && (
              <Typography variant="body2" color="text.secondary">
                فعال: {outbox.data.summary.sms_enabled ? "بله" : "خیر"} · آداپتور: {providerLabel(outbox.data.summary.active_provider)}
              </Typography>
            )}
          </Stack>

          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>گیرنده</TableCell>
                  <TableCell>هدف</TableCell>
                  <TableCell>متن</TableCell>
                  <TableCell>آداپتور</TableCell>
                  <TableCell>وضعیت</TableCell>
                  <TableCell>تلاش</TableCell>
                  <TableCell>ایجاد</TableCell>
                  <TableCell> </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(outbox.data?.items ?? []).map((r: SmsRow) => (
                  <TableRow key={r.id}>
                    <TableCell>{r.recipient_mobile}</TableCell>
                    <TableCell>{r.purpose}</TableCell>
                    <TableCell sx={{ maxWidth: 260 }}>{r.body.length > 60 ? r.body.slice(0, 60) + "…" : r.body}</TableCell>
                    <TableCell>{providerLabel(r.provider)}</TableCell>
                    <TableCell>{statusChip(r.status)}</TableCell>
                    <TableCell>{r.attempts}</TableCell>
                    <TableCell>{r.created_at?.slice(0, 16).replace("T", " ") ?? "—"}</TableCell>
                    <TableCell>
                      {r.status === "failed" && (
                        <Button size="small" onClick={() => retryMut.mutate(r.id)} disabled={retryMut.isPending}>
                          تلاش مجدد
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
                {(outbox.data?.items ?? []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8} align="center">ردیفی یافت نشد</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
          <Stack direction="row" spacing={1} mt={1} alignItems="center">
            <Button size="small" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>قبلی</Button>
            <Typography variant="body2">صفحه {page} — مجموع {outbox.data?.total ?? 0}</Typography>
            <Button
              size="small"
              disabled={outbox.data ? page * outbox.data.page_size >= outbox.data.total : true}
              onClick={() => setPage((p) => p + 1)}
            >
              بعدی
            </Button>
          </Stack>
        </Box>
      )}

      <Snackbar open={!!error} autoHideDuration={5000} onClose={() => setError(null)}>
        <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>
      </Snackbar>
      <Snackbar open={!!okMsg} autoHideDuration={4000} onClose={() => setOkMsg(null)}>
        <Alert severity="success" onClose={() => setOkMsg(null)}>{okMsg}</Alert>
      </Snackbar>
    </Box>
  );
}
