// فاز ۵۵ - پنل پذیرش/مدیر: مشاهدهٔ گفتگوهای عمومی سایت و امتیازها
// پرسش اصلی: «چه کسی چه پرسیده؟» — هویت (کاربر لاگین/نام مهمان/IP) +
// پرسش اول + کل ترنسکریپت + امتیاز و نظر کاربر + یادداشت پیگیری پذیرش
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, FormControl, InputLabel, MenuItem, Paper, Select, Stack, Table,
  TableBody, TableCell, TableContainer, TableHead, TablePagination, TableRow,
  TextField, Tooltip, Typography,
} from "@mui/material";
import StarIcon from "@mui/icons-material/Star";
import StarBorderIcon from "@mui/icons-material/StarBorder";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import SendRoundedIcon from "@mui/icons-material/SendRounded";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { errDetail } from "../api/client";
import {
  fetchPublicChatMessages, fetchPublicChatSessions, fetchPublicChatStats,
  replyToPublicChatSession, updatePublicChatSession,
} from "../api/publicChat";
import type { PublicChatMessageRow } from "../api/publicChat";
import { formatJalaliDateTime } from "../utils/jalali";

const INTENT_TITLES: Record<string, string> = {
  booking: "رزرو نوبت",
  pricing: "قیمت خدمات",
  counselors: "مشاوران",
  login: "ورود/ثبت‌نام",
  services: "خدمات",
  hours: "ساعات کاری",
  contact: "تماس/پشتیبانی",
  greeting: "سلام",
  thanks: "تشکر",
  fallback: "خارج از دامنه",
};

function RatingStars({ value, size }: { value: number | null; size?: "small" | "medium" }) {
  if (value == null) return <Typography variant="caption" color="text.secondary">—</Typography>;
  return (
    <Stack direction="row" spacing={0}>
      {[1, 2, 3, 4, 5].map((i) =>
        i <= value ? (
          <StarIcon key={i} sx={{ fontSize: size === "small" ? 15 : 20, color: "#f9a825" }} />
        ) : (
          <StarBorderIcon key={i} sx={{ fontSize: size === "small" ? 15 : 20, color: "#cfd8dc" }} />
        ),
      )}
    </Stack>
  );
}

export default function PublicChatsPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(0);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [rating, setRating] = useState("");
  const [days, setDays] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const filters = { q: q.trim() || undefined, status: status || undefined, rating: rating || undefined, days: days || undefined };

  const { data, isLoading } = useQuery({
    queryKey: ["public-chat-sessions", page, filters],
    queryFn: () => fetchPublicChatSessions({ ...filters, page: page + 1, page_size: 20 }),
    // فاز ۵۶: بازآوری خودکار هر ۱۵ ثانیه — پذیرش گفتگوهای تازه را زنده می‌بیند
    refetchInterval: 15000,
  });
  const { data: stats } = useQuery({
    queryKey: ["public-chat-stats"],
    queryFn: fetchPublicChatStats,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["public-chat-sessions"] });
    qc.invalidateQueries({ queryKey: ["public-chat-stats"] });
  };

  return (
    <Stack spacing={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center" gap={2} flexWrap="wrap">
        <Box>
          <Typography variant="h6" fontWeight={700}>گفتگوهای عمومی سایت</Typography>
          <Typography variant="caption" color="text.secondary">
            چه کسی چه پرسیده؟ — هویت گوینده (کاربر/مهمان/IP)، متن گفتگو و امتیاز ثبت‌شده
          </Typography>
        </Box>
        <Tooltip title="به‌روزرسانی">
          <Button startIcon={<RefreshRoundedIcon />} onClick={invalidate}>به‌روزرسانی</Button>
        </Tooltip>
      </Box>

      {/* کارت‌های آماری */}
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        <Chip label={`کل گفتگوها: ${(stats?.total ?? 0).toLocaleString("fa-IR")}`} variant="outlined" />
        <Chip label={`امروز: ${(stats?.today ?? 0).toLocaleString("fa-IR")}`} variant="outlined" color="primary" />
        <Chip label={`۷ روز اخیر: ${(stats?.last_7d ?? 0).toLocaleString("fa-IR")}`} variant="outlined" />
        <Chip label={`باز: ${(stats?.open ?? 0).toLocaleString("fa-IR")}`} variant="outlined" />
        <Chip
          icon={<StarIcon sx={{ fontSize: 14, color: "#f9a825" }} />}
          label={`میانگین امتیاز: ${stats?.avg_rating != null ? stats.avg_rating.toLocaleString("fa-IR") : "—"} (${(stats?.rated ?? 0).toLocaleString("fa-IR")} نظر)`}
          variant="outlined"
        />
        {stats && Object.keys(stats.distribution).length > 0 && (
          <Chip
            variant="outlined"
            label={[5, 4, 3, 2, 1].map((r) => `${r}★: ${(stats.distribution[String(r)] ?? 0).toLocaleString("fa-IR")}`).join("  |  ")}
          />
        )}
      </Stack>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      {/* فیلترها */}
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        <TextField
          size="small" label="جست‌وجو (نام، IP، متن پرسش، نظر)" value={q}
          onChange={(e) => { setPage(0); setQ(e.target.value); }}
          sx={{ minWidth: 280, flexGrow: 1, maxWidth: 420 }}
        />
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>وضعیت</InputLabel>
          <Select value={status} label="وضعیت" onChange={(e) => { setPage(0); setStatus(e.target.value); }}>
            <MenuItem value="">همه</MenuItem>
            <MenuItem value="open">باز</MenuItem>
            <MenuItem value="closed">بسته</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel>امتیاز</InputLabel>
          <Select value={rating} label="امتیاز" onChange={(e) => { setPage(0); setRating(e.target.value); }}>
            <MenuItem value="">همه</MenuItem>
            <MenuItem value="rated">داده‌شده</MenuItem>
            <MenuItem value="unrated">بدون امتیاز</MenuItem>
            {[5, 4, 3, 2, 1].map((r) => <MenuItem key={r} value={String(r)}>{r} ستاره</MenuItem>)}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel>بازه</InputLabel>
          <Select value={days} label="بازه" onChange={(e) => { setPage(0); setDays(Number(e.target.value)); }}>
            <MenuItem value={0}>همهٔ زمان‌ها</MenuItem>
            <MenuItem value={1}>۲۴ ساعت اخیر</MenuItem>
            <MenuItem value={7}>۷ روز اخیر</MenuItem>
            <MenuItem value={30}>۳۰ روز اخیر</MenuItem>
          </Select>
        </FormControl>
      </Stack>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>گوینده</TableCell>
              <TableCell>IP</TableCell>
              <TableCell>پرسش اول</TableCell>
              <TableCell>آخرین پیام</TableCell>
              <TableCell align="center">پیام‌ها</TableCell>
              <TableCell>امتیاز</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>آخرین فعالیت</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={9} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.length === 0 && (
              <TableRow><TableCell colSpan={9}>هنوز گفتگویی ثبت نشده است.</TableCell></TableRow>
            )}
            {data?.items.map((row) => (
              <TableRow
                key={row.id}
                hover
                sx={{ cursor: "pointer" }}
                onClick={() => setOpenId(row.id)}
              >
                <TableCell>
                  <Stack direction="row" spacing={0.75} alignItems="center">
                    <Typography variant="body2" fontWeight={700}>{row.display_name}</Typography>
                    <Chip
                      size="small" sx={{ height: 18, fontSize: 10 }}
                      color={row.is_registered ? "primary" : "default"}
                      variant={row.is_registered ? "filled" : "outlined"}
                      label={row.is_registered ? "کاربر" : "مهمان"}
                    />
                  </Stack>
                  {row.visitor_name && row.is_registered && (
                    <Typography variant="caption" color="text.secondary" display="block">
                      نام معرفی‌شده: {row.visitor_name}
                    </Typography>
                  )}
                  {row.staff_note && (
                    <Tooltip title={row.staff_note}>
                      <Typography variant="caption" color="info.main" display="block" noWrap sx={{ maxWidth: 180 }}>
                        📝 {row.staff_note}
                      </Typography>
                    </Tooltip>
                  )}
                </TableCell>
                <TableCell>
                  <Typography variant="caption" sx={{ direction: "ltr", unicodeBidi: "plaintext" }}>
                    {row.ip}
                  </Typography>
                </TableCell>
                <TableCell sx={{ maxWidth: 220 }}>
                  <Typography variant="caption" noWrap display="block" sx={{ maxWidth: 220 }}>
                    {row.first_question ?? "—"}
                  </Typography>
                </TableCell>
                <TableCell sx={{ maxWidth: 200 }}>
                  <Typography variant="caption" color="text.secondary" noWrap display="block" sx={{ maxWidth: 200 }}>
                    {row.last_message ?? "—"}
                  </Typography>
                  {/* فاز ۵۶: آخرین پیام از بازدیدکننده است و هنوز پاسخی نیامده */}
                  {row.status === "open" && row.last_role === "user" && (
                    <Chip size="small" color="warning" sx={{ height: 17, fontSize: 10, mt: 0.3 }} label="در انتظار پاسخ" />
                  )}
                </TableCell>
                <TableCell align="center">{(row.message_count ?? 0).toLocaleString("fa-IR")}</TableCell>
                <TableCell>
                  <RatingStars value={row.rating} size="small" />
                  {row.rating_comment && (
                    <Tooltip title={row.rating_comment}>
                      <Typography variant="caption" color="text.secondary" noWrap display="block" sx={{ maxWidth: 140 }}>
                        {row.rating_comment}
                      </Typography>
                    </Tooltip>
                  )}
                </TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    color={row.status === "open" ? "success" : "default"}
                    label={row.status === "open" ? "باز" : "بسته"}
                  />
                </TableCell>
                <TableCell>
                  <Typography variant="caption">{formatJalaliDateTime(row.updated_at)}</Typography>
                </TableCell>
                <TableCell>
                  <Button
                    size="small" variant="outlined"
                    onClick={(e) => { e.stopPropagation(); setOpenId(row.id); }}
                  >
                    مشاهده
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <TablePagination
          component="div" count={data?.total ?? 0} page={page}
          onPageChange={(_, p) => setPage(p)} rowsPerPage={20} rowsPerPageOptions={[20]}
          labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`}
        />
      </TableContainer>

      <TranscriptDialog
        sessionId={openId}
        onClose={() => setOpenId(null)}
        onChanged={invalidate}
        onError={setError}
      />
    </Stack>
  );
}

function TranscriptDialog({ sessionId, onClose, onChanged, onError }: {
  sessionId: string | null;
  onClose: () => void;
  onChanged: () => void;
  onError: (m: string) => void;
}) {
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [replyBusy, setReplyBusy] = useState(false);

  // فاز ۵۶: بازآوری زندهٔ ترنسکریپت هر ۵ ثانیه — پاسخ بازدیدکننده فوری دیده می‌شود
  const { data, isLoading } = useQuery({
    queryKey: ["public-chat-messages", sessionId],
    queryFn: () => fetchPublicChatMessages(sessionId as string),
    enabled: sessionId != null,
    refetchInterval: sessionId != null ? 5000 : false,
  });

  // هر بار گفتگوی تازه‌ای باز شد، یادداشت از سرور پر شود
  if (sessionId && sessionId !== loadedKey && data?.session) {
    setLoadedKey(sessionId);
    setNote(data.session.staff_note ?? "");
    setReply("");
  }

  const sendReply = async () => {
    if (!sessionId || !reply.trim()) return;
    setReplyBusy(true);
    try {
      await replyToPublicChatSession(sessionId, reply.trim());
      setReply("");
      onChanged();
      await qc.invalidateQueries({ queryKey: ["public-chat-messages", sessionId] });
    } catch (err) {
      onError(errDetail(err));
    } finally {
      setReplyBusy(false);
    }
  };

  const save = async (status?: "open" | "closed") => {
    if (!sessionId) return;
    setBusy(true);
    try {
      await updatePublicChatSession(sessionId, {
        staff_note: note.trim() || null,
        ...(status ? { status } : {}),
      });
      onChanged();
      if (status) onClose();
    } catch (err) {
      onError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  const s = data?.session;

  return (
    <Dialog open={sessionId != null} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" useFlexGap>
          <span>گفتگو با {s?.display_name ?? "…"}</span>
          {s && (
            <Chip
              size="small" color={s.is_registered ? "primary" : "default"}
              variant="outlined" label={s.is_registered ? `کاربر ثبت‌شده (${s.username})` : "مهمان"}
            />
          )}
        </Stack>
      </DialogTitle>
      <DialogContent>
        {isLoading && <CircularProgress size={24} sx={{ display: "block", mx: "auto", my: 3 }} />}
        {s && (
          <>
            {/* سربرگ هویت و بازخورد */}
            <Paper variant="outlined" sx={{ p: 1.5, mb: 2, bgcolor: "#fafafa" }}>
              <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap rowGap={0.5}>
                <Typography variant="caption" sx={{ direction: "ltr", unicodeBidi: "plaintext" }}>IP: {s.ip}</Typography>
                {s.first_page && <Typography variant="caption">صفحهٔ ورود: {s.first_page}</Typography>}
                <Typography variant="caption">شروع: {formatJalaliDateTime(s.created_at)}</Typography>
                <Typography variant="caption">پیام‌ها: {(s.message_count ?? 0).toLocaleString("fa-IR")}</Typography>
                {s.handled_by && (
                  <Typography variant="caption" color="info.main">
                    آخرین رسیدگی: {s.handled_by} — {formatJalaliDateTime(s.handled_at)}
                  </Typography>
                )}
              </Stack>
              <Stack direction="row" spacing={1} alignItems="center" mt={0.5}>
                <Typography variant="caption">امتیاز کاربر:</Typography>
                <RatingStars value={s.rating} />
                {s.rating_comment && (
                  <Typography variant="caption" color="text.secondary">«{s.rating_comment}»</Typography>
                )}
              </Stack>
            </Paper>

            {/* ترنسکریپت */}
            <Stack spacing={1} sx={{ maxHeight: "42vh", overflowY: "auto", mb: 2, px: 0.5 }}>
              {data?.messages.length === 0 && (
                <Typography variant="caption" color="text.secondary" align="center">پیامی رد و بدل نشده است.</Typography>
              )}
              {data?.messages.map((m) => <Bubble key={m.id} m={m} />)}
            </Stack>

            {/* فاز ۵۶: جعبهٔ پاسخ زندهٔ اپراتور — مستقیم در ویجت بازدیدکننده می‌افتد */}
            <Paper variant="outlined" sx={{ p: 1.25, mb: 2, bgcolor: "#f4faf5", borderColor: "#cfe8d6" }}>
              <Stack direction="row" spacing={1} alignItems="flex-end">
                <TextField
                  label="پاسخ زندهٔ پذیرش (در ویجت سایت نمایش داده می‌شود)"
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendReply(); }
                  }}
                  multiline maxRows={3} fullWidth size="small"
                  inputProps={{ maxLength: 1000 }}
                />
                <Button
                  variant="contained" color="success"
                  startIcon={<SendRoundedIcon />}
                  disabled={replyBusy || !reply.trim()}
                  onClick={sendReply}
                  sx={{ whiteSpace: "nowrap", flexShrink: 0 }}
                >
                  {replyBusy ? "…" : "ارسال"}
                </Button>
              </Stack>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
                پس از ارسال، تا ۱۵ دقیقه دستیار خودکار برای این گفتگو پیامی نمی‌فرستد.
              </Typography>
            </Paper>

            {/* یادداشت پذیرش + کنترل وضعیت */}
            <TextField
              label="یادداشت پذیرش/مدیر (پیگیری: تماس گرفتیم، نوبت ثبت شد و…)"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              multiline minRows={2} fullWidth size="small"
            />
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ flexWrap: "wrap", gap: 1 }}>
        {s?.status === "open" ? (
          <Button
            size="small" color="warning" startIcon={<CloseRoundedIcon />}
            disabled={busy} onClick={() => save("closed")}
          >
            بستن گفتگو
          </Button>
        ) : (
          s && (
            <Button size="small" disabled={busy} onClick={() => save("open")}>
              بازکردن گفتگو
            </Button>
          )
        )}
        <Button size="small" variant="outlined" disabled={busy} onClick={() => save()}>
          ذخیرهٔ یادداشت
        </Button>
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}

function Bubble({ m }: { m: PublicChatMessageRow }) {
  const isUser = m.role === "user";
  const isOperator = m.role === "operator"; // فاز ۵۶
  return (
    <Box sx={{ display: "flex", justifyContent: isUser ? "flex-end" : "flex-start" }}>
      <Box sx={{ maxWidth: "78%" }}>
        {isOperator && (
          <Typography variant="caption" sx={{ px: 0.5, fontWeight: 800, color: "#2e7d46" }} component="div">
            پذیرش{m.sender_name ? ` — ${m.sender_name}` : ""}
          </Typography>
        )}
        <Paper
          elevation={0}
          sx={{
            px: 1.25, py: 0.75,
            bgcolor: isUser ? "primary.main" : isOperator ? "#e8f5ec" : "action.hover",
            color: isUser ? "primary.contrastText" : "text.primary",
            border: isOperator ? "1px solid #cfe8d6" : "none",
            borderRadius: 2, borderBottomRightRadius: isUser ? 0.5 : 2,
            borderBottomLeftRadius: isUser ? 2 : 0.5,
            whiteSpace: "pre-wrap", wordBreak: "break-word",
          }}
        >
          <Typography variant="body2">{m.content}</Typography>
          {m.actions && m.actions.length > 0 && (
            <Stack direction="row" spacing={0.5} mt={0.75} flexWrap="wrap" useFlexGap>
              {m.actions.map((a, i) => (
                <Chip key={i} size="small" sx={{ height: 20, fontSize: 10 }} label={`↪ ${a.label}`} />
              ))}
            </Stack>
          )}
        </Paper>
        <Typography variant="caption" color="text.secondary" sx={{ px: 0.5 }} component="div">
          {isUser ? "بازدیدکننده" : isOperator ? "پذیرش" : "دستیار"}
          {!isOperator && m.intent && m.intent !== "fallback" && INTENT_TITLES[m.intent] ? ` • ${INTENT_TITLES[m.intent]}` : ""}
          {" • "}
          {formatJalaliDateTime(m.created_at)}
        </Typography>
      </Box>
    </Box>
  );
}
