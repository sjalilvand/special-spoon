// فاز ۳۵ - B25/B26/B27 سند جامع: دستیار هوشمند — تصمیم D07 (پلاگین‌پذیر)
import {
  Alert, Box, Chip, Paper, Snackbar, Stack, Tab, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, TextField, Typography, Button,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { errDetail } from "../api/client";
import {
  ChatResult, NoShowRiskItem, aiChat, fetchAiConfig, fetchNoShowRisk, fetchRecommendations,
} from "../api/ai";

export default function AssistantPage() {
  const [tab, setTab] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<{ role: "user" | "ai"; text: string; provider?: string }[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const config = useQuery({ queryKey: ["ai-config"], queryFn: fetchAiConfig });
  const recs = useQuery({ queryKey: ["ai-recs"], queryFn: fetchRecommendations, enabled: tab === 1 });
  const risk = useQuery({ queryKey: ["ai-noshow"], queryFn: () => fetchNoShowRisk(7), enabled: tab === 2 });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setBusy(true);
    try {
      const res: ChatResult = await aiChat(text);
      setMessages((m) => [...m, { role: "ai", text: `${res.response}\n\n— ${res.disclaimer}`, provider: res.provider }]);
    } catch (e) {
      setError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const active = config.data;

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={800}>دستیار هوشمند (B25–B27)</Typography>
        {active && (
          <Chip size="small" variant="outlined"
            color={active.fallback_applied ? "warning" : "success"}
            label={`سرویس فعال: ${active.active_provider}${active.fallback_applied ? " (fallback)" : ""}`} />
        )}
      </Box>
      {active && (
        <Alert severity="info">
          D07 — سرویس پلاگین‌پذیر؛ پیکربندی: {active.configured_provider}، فعال: {active.active_provider}؛
          سقف {active.rate_limit_per_minute} پیام در دقیقه. {active.disclaimer}
        </Alert>
      )}
      <Paper sx={{ p: 1.5 }}>
        <Stack direction="row" spacing={1}>
          <Tab label="گفتگو (B25)" onClick={() => setTab(0)} />
          <Tab label="پیشنهاد خدمات (B26)" onClick={() => setTab(1)} />
          <Tab label="ریسک عدم‌حضور (B27)" onClick={() => setTab(2)} />
        </Stack>
      </Paper>

      {tab === 0 && (
        <Paper variant="outlined" sx={{ p: 2, minHeight: 380, display: "flex", flexDirection: "column" }}>
          <Stack spacing={1} flexGrow={1}>
            {messages.length === 0 && (
              <Typography variant="body2" color="text.secondary">
                درباره رزرو نوبت، خدمات، سفارش و پرداخت، شعب یا کیف پول بپرسید…
              </Typography>
            )}
            {messages.map((m, i) => (
              <Paper key={i} variant="outlined" sx={{
                p: 1, maxWidth: "85%", alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                bgcolor: m.role === "user" ? "action.hover" : "background.paper",
              }}>
                <Typography variant="caption">{m.role === "user" ? "شما" : `دستیار${m.provider ? ` (${m.provider})` : ""}`}</Typography>
                <Typography sx={{ whiteSpace: "pre-wrap" }}>{m.text}</Typography>
              </Paper>
            ))}
            <div ref={bottomRef} />
          </Stack>
          <Stack direction="row" spacing={1} mt={1}>
            <TextField size="small" fullWidth placeholder="پیام شما…" value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); } }} />
            <Button variant="contained" onClick={() => void send()} disabled={busy || !input.trim()}>
              ارسال
            </Button>
          </Stack>
        </Paper>
      )}

      {tab === 1 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead><TableRow><TableCell>خدمت پیشنهادی (هم‌دسته آخرین سفارش شما)</TableCell></TableRow></TableHead>
            <TableBody>
              {(recs.data ?? []).map((r) => (
                <TableRow key={r.service_id}><TableCell>{r.title}</TableCell></TableRow>
              ))}
              {!(recs.data ?? []).length && (
                <TableRow><TableCell>هنوز پیشنهادی برای شما نیست (نیازمند حداقل یک سفارش)</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {tab === 2 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>نوبت</TableCell><TableCell>ریسک</TableCell><TableCell>سطح</TableCell><TableCell>عوامل</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(risk.data?.items ?? []).map((it: NoShowRiskItem) => (
                <TableRow key={it.appointment_id}>
                  <TableCell dir="ltr" sx={{ fontSize: 11 }}>
                    {it.scheduled_at ? new Date(it.scheduled_at).toLocaleString("fa-IR") : "—"}
                  </TableCell>
                  <TableCell>{it.risk_score}٪</TableCell>
                  <TableCell>{it.risk_level}</TableCell>
                  <TableCell>{it.factors.join("، ")}</TableCell>
                </TableRow>
              ))}
              {!(risk.data?.items ?? []).length && (
                <TableRow><TableCell colSpan={4}>نوبت آینده‌ای در پنجره ۷ روز نیست</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)}>
        <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>
      </Snackbar>
    </Stack>
  );
}
