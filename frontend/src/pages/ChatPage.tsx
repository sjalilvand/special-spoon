import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Badge,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  InputAdornment,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import AudioFileRoundedIcon from "@mui/icons-material/AudioFileRounded";
import CallEndRoundedIcon from "@mui/icons-material/CallEndRounded";
import GroupAddIcon from "@mui/icons-material/GroupAdd";
import MicIcon from "@mui/icons-material/Mic";
import PhoneRoundedIcon from "@mui/icons-material/PhoneRounded";
import SearchIcon from "@mui/icons-material/Search";
import SendIcon from "@mui/icons-material/Send";
import StopIcon from "@mui/icons-material/Stop";
import ChatIcon from "@mui/icons-material/Chat";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { errDetail, ensureAccessToken } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { roleTitle } from "../api/auth";
import {
  type ChatMessage,
  type Conversation,
  type DirectoryUser,
  chatWsUrl,
  fetchChatDirectory,
  fetchConversations,
  fetchMessages,
  inviteToConversation,
  markRead,
  sendTextMessage,
  sendVoiceMessage,
  startConversation,
} from "../api/chat";
import {
  type CallSessionDto,
  answerCall,
  cancelCall,
  declineCall,
  endCall,
  fetchActiveCall,
  startCall,
} from "../api/calls";
import {
  fetchFormTemplateForFill,
  submitFormResponse,
} from "../api/forms";
import FormRenderer, { validateFormValues, type FormValues } from "../components/FormRenderer";
import { formatJalaliDateTime } from "../utils/jalali";

/**
 * فاز ۵۲ - چت آنلاین + فاز ۶۱ (پیام صوتی پایدار + تماس تلفنی + نظرسنجی پس از تماس):
 * - گفتگوی دو نفره (get-or-create) + «دعوت به مشاوره» (تبدیل dm به گروه)؛
 * - پیام صوتی: MediaRecorder (در بستر امن) با پیش‌نمایش پیش از ارسال؛
 *   در سایت HTTP (زمینهٔ ناامن) راهنمای فعال‌سازی میکروفون + بارگذاری فایل صوتی؛
 * - تماس تلفنی مدیریت‌شده: زنگ → پاسخ/رد → پایان → نظرسنجی خودکار برای گیرنده؛
 * - زنده‌رسانی با WebSocket + همگام‌سازی دوره‌ای (fail-open)؛
 * - آهنگ وضعیت: منبع حقیقت = سرور؛ WS فقط اعلان تازگی است.
 */

const POLL_MS = 15000;

/** آیا مرورگر امکان ضبط صدا دارد؟ در HTTP غیر localhost رسانه‌ها بسته است */
export function canRecordAudio(): boolean {
  return typeof navigator !== "undefined"
    && !!navigator.mediaDevices
    && typeof navigator.mediaDevices.getUserMedia === "function"
    && typeof window.MediaRecorder !== "undefined";
}

/** زنگ کوتاه تماس ورودی — بدون نیاز به فایل صوتی (Web Audio) */
function playIncomingBeep() {
  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const beep = (at: number) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.frequency.value = 880;
      o.type = "sine";
      g.gain.setValueAtTime(0.0001, at);
      g.gain.exponentialRampToValueAtTime(0.18, at + 0.05);
      g.gain.exponentialRampToValueAtTime(0.0001, at + 0.45);
      o.connect(g); g.connect(ctx.destination);
      o.start(at); o.stop(at + 0.5);
    };
    const t = ctx.currentTime;
    beep(t); beep(t + 0.6); beep(t + 1.2);
    setTimeout(() => ctx.close().catch(() => undefined), 2500);
  } catch {
    /* بی‌صدا نادیده گرفته می‌شود */
  }
}

export default function ChatPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newChatOpen, setNewChatOpen] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [live, setLive] = useState(false);
  // فاز ۶۱: تماس فعال + نظرسنجی پس از تماس (شناسهٔ قالب + شناسهٔ تماس برای پیوند پاسخ)
  const [call, setCall] = useState<CallSessionDto | null>(null);
  const [surveyCtx, setSurveyCtx] = useState<{ templateId: string; callId: string | null } | null>(null);
  const meId = user?.id ?? "";

  // بازسازی تماس فعال پس از رفرش صفحه
  useEffect(() => {
    fetchActiveCall()
      .then((c) => setCall(c))
      .catch(() => undefined);
  }, []);

  const convs = useQuery({
    queryKey: ["chat-conversations"],
    queryFn: fetchConversations,
    refetchInterval: POLL_MS,
  });

  const conversations: Conversation[] = useMemo(() => convs.data ?? [], [convs.data]);
  const active = conversations.find((c) => c.id === activeId) ?? null;

  // --- WebSocket زنده‌رسانی (fail-open: قطع → همگام‌سازی دوره‌ای) ---
  const wsRef = useRef<WebSocket | null>(null);
  useEffect(() => {
    let closed = false;
    let retry = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const connect = async () => {
      const token = await ensureAccessToken();
      if (closed) return;
      if (!token) {
        timer = setTimeout(connect, 5000);
        return;
      }
      const ws = new WebSocket(chatWsUrl(token));
      wsRef.current = ws;
      ws.onopen = () => {
        retry = 0;
        setLive(true);
      };
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === "message") {
            queryClient.invalidateQueries({ queryKey: ["chat-conversations"] });
            if (data.conversation_id === activeId) {
              queryClient.invalidateQueries({
                queryKey: ["chat-messages", activeId],
              });
            }
          } else if (data.type === "conversation-updated") {
            queryClient.invalidateQueries({ queryKey: ["chat-conversations"] });
          } else if (data.type === "call") {
            // فاز ۶۱: رخدادهای تماس — incoming/answered/declined/cancelled/ended/survey_pending
            const c = data.call as CallSessionDto | undefined;
            const event = String(data.event || "");
            const openSurvey = (tplId: unknown, callObj: CallSessionDto | undefined) => {
              if (callObj?.callee_id === meId && tplId) {
                setSurveyCtx({ templateId: String(tplId), callId: callObj?.id ?? null });
              }
            };
            if (event === "incoming") {
              setCall(c ?? null);
              playIncomingBeep();
            } else if (event === "survey_pending") {
              setCall(c ?? null);
              openSurvey(data.template_id, c);
            } else if (event === "ended") {
              setCall(c ?? null);
              openSurvey(data.survey_template_id, c);
              setTimeout(() => setCall((cur) => (cur && c && cur.id === c.id ? null : cur)), 6000);
            } else if (c) {
              setCall(c);
            }
          } else if (data.type === "read" || data.type === "typing") {
            window.dispatchEvent(new CustomEvent("rosepsy-chat-event", { detail: data }));
          }
        } catch {
          /* پیام غیر JSON نادیده گرفته می‌شود */
        }
      };
      ws.onclose = () => {
        setLive(false);
        wsRef.current = null;
        if (!closed) {
          retry = Math.min(retry + 1, 6);
          timer = setTimeout(connect, 1000 * Math.pow(2, retry));
        }
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [queryClient, activeId, meId]);

  // ارسال typing از Composer (از طریق رویداد پنجره → WS فعال)
  useEffect(() => {
    const handler = (ev: Event) => {
      const d = (ev as CustomEvent).detail;
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN && d?.conversation_id) {
        ws.send(JSON.stringify({ type: "typing", conversation_id: d.conversation_id }));
      }
    };
    window.addEventListener("rosepsy-chat-typing", handler);
    return () => window.removeEventListener("rosepsy-chat-typing", handler);
  }, []);

  const invalidateThread = useCallback(
    (cid: string) => {
      queryClient.invalidateQueries({ queryKey: ["chat-messages", cid] });
      queryClient.invalidateQueries({ queryKey: ["chat-conversations"] });
    },
    [queryClient],
  );

  const sendText = useMutation({
    mutationFn: (p: { cid: string; body: string }) => sendTextMessage(p.cid, p.body),
    onSuccess: (_m, p) => invalidateThread(p.cid),
    onError: (e) => setError(errDetail(e)),
  });

  const sendVoice = useMutation({
    mutationFn: (p: { cid: string; blob: Blob; durationMs: number; mime: string }) =>
      sendVoiceMessage(p.cid, p.blob, p.durationMs, p.mime),
    onSuccess: (_m, p) => invalidateThread(p.cid),
    onError: (e) => setError(errDetail(e)),
  });

  // فاز ۶۱: آغاز تماس از سربرگ گفتگو (فقط گفتگوی دو نفره)
  const startCallMut = useMutation({
    mutationFn: (p: { cid: string }) => startCall(p.cid),
    onSuccess: (c) => setCall(c),
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Stack spacing={2} sx={{ height: "calc(100vh - 140px)", minHeight: 480 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" gap={2}>
        <Typography variant="h6" fontWeight={700}>
          گفتگوی آنلاین و مشاوره
        </Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip
            size="small"
            color={live ? "success" : "default"}
            label={live ? "متصل (زنده)" : "حالت همگام‌سازی دوره‌ای"}
            variant="outlined"
          />
          <Button variant="contained" startIcon={<ChatIcon />} onClick={() => setNewChatOpen(true)}>
            گفتگوی جدید
          </Button>
        </Stack>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      {/* فاز ۶۱: نوار وضعیت تماس — بالای صفحه همیشه نمایان است */}
      <CallBanner
        call={call}
        meId={meId}
        onChanged={(c) => setCall(c)}
        onClosed={() => setCall(null)}
        onError={setError}
        onSurvey={(tplId, callId) => setSurveyCtx({ templateId: tplId, callId })}
      />

      <Stack direction="row" spacing={2} sx={{ flex: 1, minHeight: 0 }}>
        {/* لیست گفتگوها */}
        <Paper variant="outlined" sx={{ width: 340, flexShrink: 0, overflowY: "auto" }}>
          {convs.isLoading && <CircularProgress size={24} sx={{ mx: "auto", display: "block", mt: 4 }} />}
          {!convs.isLoading && conversations.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ p: 3, textAlign: "center" }}>
              هنوز گفتگویی ندارید. با «گفتگوی جدید» با همکاران یا مشاوران گفتگو را شروع کنید.
            </Typography>
          )}
          {conversations.map((c) => (
            <Box
              key={c.id}
              onClick={() => setActiveId(c.id)}
              sx={{
                px: 1.5,
                py: 1.2,
                cursor: "pointer",
                borderBottom: 1,
                borderColor: "divider",
                bgcolor: c.id === activeId ? "action.selected" : "transparent",
                "&:hover": { bgcolor: "action.hover" },
              }}
            >
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Typography variant="body2" fontWeight={700} noWrap>
                  {c.kind === "group" ? "👥 " : ""}{c.title}
                </Typography>
                {c.unread > 0 && <Badge color="error" badgeContent={c.unread} />}
              </Box>
              <Typography variant="caption" color="text.secondary" noWrap sx={{ display: "block" }}>
                {c.last_message ? `${c.last_message.sender_name ? c.last_message.sender_name + ": " : ""}${c.last_message.preview}` : "—"}
              </Typography>
              {c.last_message_at && (
                <Typography variant="caption" color="text.disabled" sx={{ fontSize: 10 }}>
                  {formatJalaliDateTime(c.last_message_at)}
                </Typography>
              )}
            </Box>
          ))}
        </Paper>

        {/* ترد گفتگو */}
        {active ? (
          <Thread
            key={active.id}
            conversation={active}
            meId={meId}
            busy={sendText.isPending || sendVoice.isPending}
            onBack={() => setActiveId(null)}
            onSendText={(body) => sendText.mutate({ cid: active.id, body })}
            onSendVoice={(blob, ms, mime) => sendVoice.mutate({ cid: active.id, blob, durationMs: ms, mime })}
            onInvite={() => setInviteOpen(true)}
            onCallStart={() => startCallMut.mutate({ cid: active.id })}
            callStarting={startCallMut.isPending}
          />
        ) : (
          <Paper variant="outlined" sx={{ flex: 1, display: "grid", placeItems: "center" }}>
            <Typography variant="body2" color="text.secondary">
              یک گفتگو را از فهرست انتخاب کنید.
            </Typography>
          </Paper>
        )}
      </Stack>

      <NewChatDialog
        open={newChatOpen}
        onClose={() => setNewChatOpen(false)}
        onStarted={(cid) => {
          setNewChatOpen(false);
          setActiveId(cid);
          queryClient.invalidateQueries({ queryKey: ["chat-conversations"] });
        }}
        onError={setError}
      />

      {active && (
        <InviteDialog
          open={inviteOpen}
          conversation={active}
          onClose={() => setInviteOpen(false)}
          onDone={() => {
            setInviteOpen(false);
            setError(null);
            queryClient.invalidateQueries({ queryKey: ["chat-conversations"] });
            queryClient.invalidateQueries({ queryKey: ["chat-messages", active.id] });
          }}
          onError={setError}
        />
      )}

      {/* فاز ۶۱: نظرسنجی پس از پایان تماس */}
      <PostCallSurveyDialog
        templateId={surveyCtx?.templateId ?? null}
        callId={surveyCtx?.callId ?? null}
        onClose={() => setSurveyCtx(null)}
      />
    </Stack>
  );
}

// ---------------------------------------------------------------------------
function Thread({
  conversation,
  meId,
  onBack,
  onSendText,
  onSendVoice,
  onInvite,
  onCallStart,
  callStarting,
  busy,
}: {
  conversation: Conversation;
  meId: string;
  onBack: () => void;
  onSendText: (body: string) => void;
  onSendVoice: (blob: Blob, durationMs: number, mime: string) => void;
  onInvite: () => void;
  onCallStart: () => void;
  callStarting: boolean;
  busy: boolean;
}) {
  const [text, setText] = useState("");
  const [typingUsers, setTypingUsers] = useState<Record<string, number>>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastMsg = useRef<string | null>(null);

  const msgs = useQuery({
    queryKey: ["chat-messages", conversation.id],
    queryFn: () => fetchMessages(conversation.id),
    refetchInterval: POLL_MS,
  });

  const items: ChatMessage[] = useMemo(() => msgs.data ?? [], [msgs.data]);

  // اسکرول به پایین روی پیام تازه
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const last = items[items.length - 1];
    if (last && last.id !== lastMsg.current) {
      lastMsg.current = last.id;
      requestAnimationFrame(() => el.scrollTo({ top: el.scrollHeight, behavior: "smooth" }));
    }
  }, [items]);

  // علامت‌گذاری خوانده‌شدن
  useEffect(() => {
    const last = items[items.length - 1];
    if (!last) return;
    if (last.sender_id && last.sender_id !== meId) {
      markRead(conversation.id, last.id).catch(() => undefined);
    }
  }, [items, conversation.id, meId]);

  // شنوندهٔ رویدادهای typing/read از WS (از طریق CustomEvent)
  useEffect(() => {
    const handler = (ev: Event) => {
      const d = (ev as CustomEvent).detail;
      if (d?.conversation_id !== conversation.id) return;
      if (d.type === "typing" && d.display_name) {
        setTypingUsers((prev) => ({ ...prev, [d.display_name]: Date.now() }));
        setTimeout(() => {
          setTypingUsers((prev) => {
            const next = { ...prev };
            Object.keys(next).forEach((k) => {
              if (Date.now() - next[k] > 3200) delete next[k];
            });
            return next;
          });
        }, 3300);
      }
    };
    window.addEventListener("rosepsy-chat-event", handler);
    return () => window.removeEventListener("rosepsy-chat-event", handler);
  }, [conversation.id]);

  const typingLabel = Object.keys(typingUsers).join("، ");

  const submit = () => {
    const body = text.trim();
    if (!body) return;
    setText("");
    onSendText(body);
  };

  return (
    <Paper variant="outlined" sx={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
      {/* سربرگ */}
      <Box sx={{ p: 1.5, borderBottom: 1, borderColor: "divider", display: "flex", alignItems: "center", gap: 1 }}>
        <IconButton sx={{ display: { md: "none" } }} onClick={onBack}>
          <ArrowBackIcon />
        </IconButton>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="subtitle1" fontWeight={700} noWrap>
            {conversation.kind === "group" ? "اتاق مشاوره — " : ""}{conversation.title}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap>
            {conversation.members.map((m) => m.display_name ?? m.username).join("، ")}
          </Typography>
        </Box>
        <Box sx={{ flex: 1 }} />
        {/* فاز ۶۱: تماس تلفنی — فقط در گفتگوی دو نفره */}
        {conversation.kind === "dm" && (
          <Tooltip title="تماس تلفنی (پس از پایان تماس، نظرسنجی برای مراجع فعال می‌شود)">
            <span>
              <IconButton color="success" onClick={onCallStart} disabled={callStarting}>
                <PhoneRoundedIcon />
              </IconButton>
            </span>
          </Tooltip>
        )}
        <Button size="small" startIcon={<GroupAddIcon />} onClick={onInvite}>
          دعوت به مشاوره
        </Button>
      </Box>

      {/* پیام‌ها */}
      <Box ref={scrollRef} sx={{ flex: 1, overflowY: "auto", p: 2, bgcolor: "background.default" }}>
        {msgs.isLoading && <CircularProgress size={24} sx={{ mx: "auto", display: "block" }} />}
        {items.map((m) => {
          if (m.kind === "system") {
            return (
              <Typography key={m.id} variant="caption" color="text.secondary" sx={{ display: "block", textAlign: "center", my: 1 }}>
                {m.body}
              </Typography>
            );
          }
          const mine = m.sender_id === meId;
          return (
            <Box key={m.id} sx={{ display: "flex", justifyContent: mine ? "flex-start" : "flex-end", mb: 1 }}>
              <Box
                sx={{
                  maxWidth: "72%",
                  px: 1.5,
                  py: 1,
                  borderRadius: 2.5,
                  bgcolor: mine ? "primary.main" : "grey.200",
                  color: mine ? "primary.contrastText" : "text.primary",
                }}
              >
                {!mine && (
                  <Typography variant="caption" sx={{ display: "block", fontWeight: 700, mb: 0.5 }}>
                    {m.sender_name}
                  </Typography>
                )}
                {m.kind === "voice" && m.media ? (
                  <VoicePlayer media={m.media} mine={mine} />
                ) : (
                  <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                    {m.body}
                  </Typography>
                )}
                <Typography variant="caption" sx={{ display: "block", textAlign: "left", opacity: 0.7, fontSize: 10 }}>
                  {formatJalaliDateTime(m.created_at)}
                </Typography>
              </Box>
            </Box>
          );
        })}
      </Box>

      {/* نوار تایپ */}
      {typingLabel && (
        <Typography variant="caption" color="text.secondary" sx={{ px: 2, pb: 0.5 }}>
          {typingLabel} در حال نوشتن…
        </Typography>
      )}
      <Composer
        disabled={busy}
        onSend={submit}
        onVoice={(blob, ms, mime) => onSendVoice(blob, ms, mime)}
        onTyping={() => {
          wsSendTyping(conversation.id);
        }}
        text={text}
        setText={setText}
      />
    </Paper>
  );
}

// ارسال typing روی WS باز (fail-open)
function wsSendTyping(conversationId: string) {
  // رویداد از طریق ref سراسری نمی‌گذرد؛ ساده: استفاده از رویداد پنجره — WS در ChatPage
  window.dispatchEvent(new CustomEvent("rosepsy-chat-typing", { detail: { conversation_id: conversationId } }));
}

// ---------------------------------------------------------------------------
const Composer = ({
  text,
  setText,
  onSend,
  onVoice,
  onTyping,
  disabled,
}: {
  text: string;
  setText: (t: string) => void;
  onSend: () => void;
  onVoice: (blob: Blob, durationMs: number, mime: string) => void;
  onTyping: () => void;
  disabled: boolean;
}) => {
  // فاز ۶۱: ضبط با پیش‌نمایش (ارسال/حذف) + بارگذاری فایل صوتی + راهنمای میکروفون
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [previewBlob, setPreviewBlob] = useState<{ blob: Blob; ms: number; mime: string } | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAt = useRef(0);
  const lastTypingSent = useRef(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const canRecord = canRecordAudio();

  const startRec = async () => {
    if (!canRecord) {
      setHelpOpen(true);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeCandidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
      const mime = mimeCandidates.find((m) => MediaRecorder.isTypeSupported(m));
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunksRef.current = [];
      rec.ondataavailable = (e) => e.data.size > 0 && chunksRef.current.push(e.data);
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        const ms = Date.now() - startedAt.current;
        setRecording(false);
        // فاز ۶۱: پیش از ارسال، پیش‌نمایش و امکان حذف
        if (blob.size > 1024) setPreviewBlob({ blob, ms, mime: blob.type || "audio/webm" });
      };
      recorderRef.current = rec;
      startedAt.current = Date.now();
      setSeconds(0);
      setMicError(null);
      rec.start();
      setRecording(true);
    } catch (err) {
      // خطاها دیگر بی‌صدا نیستند — پیام روشن به کاربر
      const name = (err as { name?: string })?.name ?? "";
      if (name === "NotAllowedError" || name === "SecurityError") {
        setMicError("دسترسی به میکروفون داده نشد. از تنظیمات مرورگر اجازهٔ میکروفون را برای این سایت فعال کنید.");
      } else if (name === "NotFoundError") {
        setMicError("میکروفونی پیدا نشد. اتصال میکروفون را بررسی کنید.");
      } else {
        setMicError("ضبط صدا ممکن نشد. می‌توانید فایل صوتی ضبط‌شده را بارگذاری کنید.");
      }
      setRecording(false);
    }
  };

  const stopRec = () => {
    recorderRef.current?.stop();
    recorderRef.current = null;
  };

  const cancelRec = () => {
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") {
      rec.onstop = null;
      rec.stop();
      rec.stream?.getTracks().forEach((t) => t.stop());
    }
    recorderRef.current = null;
    setRecording(false);
  };

  const sendPreview = () => {
    if (previewBlob) onVoice(previewBlob.blob, previewBlob.ms, previewBlob.mime);
    setPreviewBlob(null);
  };

  const onPickFile = async (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("audio")) {
      setMicError("فقط فایل صوتی (mp3، wav، m4a، ogg، webm) قابل ارسال است.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setMicError("حجم فایل صوتی بیش از ۵ مگابایت است.");
      return;
    }
    onVoice(file, 0, file.type || "audio/mpeg");
  };

  useEffect(() => {
    if (!recording) return;
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [recording]);

  return (
    <Box sx={{ p: 1.5, borderTop: 1, borderColor: "divider" }}>
      {/* پیش‌نمایش پیام صوتی پیش از ارسال */}
      {previewBlob ? (
        <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mb: 1, p: 1, bgcolor: "#f6faf6", borderRadius: 1.5, border: "1px solid #dcedc8" }}>
          <Typography variant="caption" color="text.secondary">
            پیش‌نمایش پیام صوتی ({Math.max(1, Math.round(previewBlob.ms / 1000))} ثانیه)
          </Typography>
          <audio controls src={URL.createObjectURL(previewBlob.blob)} style={{ height: 34, flex: 1, maxWidth: 320 }} />
          <Button size="small" color="error" onClick={() => setPreviewBlob(null)}>حذف</Button>
          <Button size="small" variant="contained" startIcon={<SendIcon />} onClick={sendPreview}>
            ارسال
          </Button>
        </Stack>
      ) : null}

      {/* حالت ضبط زنده */}
      {recording ? (
        <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mb: 1, p: 1, bgcolor: "#fff5f5", borderRadius: 1.5, border: "1px solid #f3c1c1" }}>
          <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: "error.main", animation: "pulse 1s infinite", "@keyframes pulse": { "50%": { opacity: 0.3 } } }} />
          <Typography variant="body2" color="error.main" fontWeight={700}>
            در حال ضبط… {seconds}s
          </Typography>
          <Box sx={{ flex: 1 }} />
          <Button size="small" onClick={cancelRec}>لغو</Button>
          <Button size="small" variant="contained" color="error" startIcon={<StopIcon />} onClick={stopRec}>
            پایان ضبط
          </Button>
        </Stack>
      ) : null}

      {micError ? (
        <Alert severity="warning" onClose={() => setMicError(null)} sx={{ mb: 1 }}>
          {micError}{" "}
          <Button size="small" onClick={() => setHelpOpen(true)}>راهنمای فعال‌سازی</Button>
        </Alert>
      ) : null}

      <TextField
        fullWidth
        multiline
        maxRows={4}
        size="small"
        placeholder="پیام خود را بنویسید…"
        value={text}
        disabled={disabled}
        onChange={(e) => {
          setText(e.target.value);
          const now = Date.now();
          if (now - lastTypingSent.current > 2000) {
            lastTypingSent.current = now;
            onTyping();
          }
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (!disabled) onSend();
          }
        }}
        InputProps={{
          endAdornment: (
            <InputAdornment position="end">
              <Tooltip title="بارگذاری فایل صوتی (همیشه کار می‌کند)">
                <IconButton
                  disabled={disabled}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <AudioFileRoundedIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title={recording ? "پایان ضبط" : "ضبط پیام صوتی"}>
                <IconButton
                  color={recording ? "error" : "default"}
                  onClick={() => (recording ? stopRec() : startRec())}
                  disabled={disabled}
                >
                  {recording ? <StopIcon /> : <MicIcon />}
                </IconButton>
              </Tooltip>
              <IconButton color="primary" onClick={onSend} disabled={disabled || !text.trim()}>
                <SendIcon />
              </IconButton>
            </InputAdornment>
          ),
        }}
      />
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*,.mp3,.wav,.m4a,.ogg,.webm"
        hidden
        onChange={(e) => {
          onPickFile(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      <MicHelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} />
    </Box>
  );
};

// پخش‌کنندهٔ صوت — رسانه با هدر احراز هویت fetch و به objectURL تبدیل می‌شود
const objectUrlCache = new Map<string, string>();
function VoicePlayer({ media, mine }: { media: { url: string; duration_ms: number | null; bytes: number }; mine: boolean }) {
  const [src, setSrc] = useState<string | null>(objectUrlCache.get(media.url) ?? null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (src) return;
    const apiClientPromise = import("../api/client").then((m) => m.apiClient);
    apiClientPromise
      .then((client) => client.get(media.url, { responseType: "blob" }))
      .then((res) => {
        const url = URL.createObjectURL(res.data);
        objectUrlCache.set(media.url, url);
        setSrc(url);
      })
      .catch(() => setFailed(true));
  }, [media.url, src]);

  if (failed) return <Typography variant="caption">پخش صوت ممکن نشد</Typography>;
  if (!src) return <CircularProgress size={18} />;
  return (
    <audio controls preload="metadata" src={src} style={{ maxWidth: 240, height: 36 }} data-mine={mine ? 1 : 0} />
  );
}

// ---------------------------------------------------------------------------
function NewChatDialog({
  open,
  onClose,
  onStarted,
  onError,
}: {
  open: boolean;
  onClose: () => void;
  onStarted: (conversationId: string) => void;
  onError: (msg: string) => void;
}) {
  const [search, setSearch] = useState("");
  const directory = useQuery({
    queryKey: ["chat-directory", search],
    queryFn: () => fetchChatDirectory(search),
    enabled: open,
  });

  const start = useMutation({
    mutationFn: startConversation,
    onSuccess: (c) => onStarted(c.id),
    onError: (e) => onError(errDetail(e)),
  });

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>شروع گفتگوی دو نفره</DialogTitle>
      <DialogContent>
        <TextField
          autoFocus
          fullWidth
          size="small"
          placeholder="جست‌وجوی نام یا نام کاربری…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
          sx={{ mt: 1 }}
        />
        <Box sx={{ maxHeight: 320, overflowY: "auto", mt: 1 }}>
          {(directory.data ?? []).map((u) => (
            <Box
              key={u.id}
              onClick={() => start.mutate(u.id)}
              sx={{ px: 1.5, py: 1, borderRadius: 1, cursor: "pointer", "&:hover": { bgcolor: "action.hover" } }}
            >
              <Typography variant="body2" fontWeight={600}>
                {u.display_name}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {u.username} — {u.roles.map(roleTitle).join("، ") || "بدون نقش"}
              </Typography>
            </Box>
          ))}
          {directory.data?.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: "center" }}>
              کاربری یافت نشد.
            </Typography>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
function InviteDialog({
  open,
  conversation,
  onClose,
  onDone,
  onError,
}: {
  open: boolean;
  conversation: Conversation;
  onClose: () => void;
  onDone: (r: { added: { id: string; display_name: string }[]; was_dm: boolean }) => void;
  onError: (msg: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<DirectoryUser[]>([]);
  const [note, setNote] = useState("");
  const directory = useQuery({
    queryKey: ["chat-directory-invite", search],
    queryFn: () => fetchChatDirectory(search),
    enabled: open,
  });
  const memberIds = new Set(conversation.members.map((m) => m.user_id));

  const invite = useMutation({
    mutationFn: () => inviteToConversation(conversation.id, selected.map((u) => u.id), note.trim() || undefined),
    onSuccess: (r) => {
      setSelected([]);
      setNote("");
      onDone(r);
    },
    onError: (e) => onError(errDetail(e)),
  });

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>دعوت نفر دیگر به مشاوره</DialogTitle>
      <DialogContent>
        <Alert severity="info" sx={{ mt: 1, mb: 1.5 }}>
          با دعوت نفر سوم، این گفتگو به یک «اتاق مشاوره» گروهی تبدیل می‌شود و پیام‌های قبلی برای فرد دعوت‌شده قابل مشاهده است.
        </Alert>
        <TextField
          autoFocus
          fullWidth
          size="small"
          placeholder="جست‌وجوی کاربر…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
        />
        {selected.length > 0 && (
          <Stack direction="row" spacing={0.5} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
            {selected.map((u) => (
              <Chip
                key={u.id}
                size="small"
                label={u.display_name}
                onDelete={() => setSelected((prev) => prev.filter((x) => x.id !== u.id))}
              />
            ))}
          </Stack>
        )}
        <Box sx={{ maxHeight: 260, overflowY: "auto", mt: 1 }}>
          {(directory.data ?? [])
            .filter((u) => !memberIds.has(u.id))
            .map((u) => {
              const isSel = selected.some((s) => s.id === u.id);
              return (
                <Box
                  key={u.id}
                  onClick={() =>
                    setSelected((prev) =>
                      isSel ? prev.filter((x) => x.id !== u.id) : prev.length >= 10 ? prev : [...prev, u],
                    )
                  }
                  sx={{
                    px: 1.5,
                    py: 1,
                    borderRadius: 1,
                    cursor: "pointer",
                    bgcolor: isSel ? "action.selected" : "transparent",
                    "&:hover": { bgcolor: "action.hover" },
                  }}
                >
                  <Typography variant="body2" fontWeight={600}>
                    {u.display_name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {u.username} — {u.roles.map(roleTitle).join("، ") || "بدون نقش"}
                  </Typography>
                </Box>
              );
            })}
        </Box>
        <TextField
          fullWidth
          size="small"
          label="یادداشت دعوت (اختیاری)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          sx={{ mt: 1.5 }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button
          variant="contained"
          disabled={selected.length === 0 || invite.isPending}
          onClick={() => invite.mutate()}
        >
          {invite.isPending ? "در حال دعوت…" : `دعوت ${selected.length} نفر`}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// فاز ۶۱ - راهنمای فعال‌سازی میکروفون در سایت HTTP (زمینهٔ ناامن)
// مرورگرها getUserMedia را فقط در HTTPS/localhost می‌دهند؛ تا زمانی که ۴۴۳
// باز نشده، این راهنما + بارگذاری فایل صوتی جایگزین کاربردی است.
function MicHelpDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const addr = window.location.origin;
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>فعال‌سازی میکروفون برای ضبط پیام صوتی</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          <Alert severity="info">
            مرورگرها ضبط صدا را فقط در نشانی امن (HTTPS یا localhost) مجاز می‌کنند.
            تا زمانی که گواهی HTTPS فعال نشده، از یکی از دو راه زیر استفاده کنید.
          </Alert>
          <Paper variant="outlined" sx={{ p: 1.5 }}>
            <Typography fontWeight={700} variant="body2" sx={{ mb: 0.5 }}>
              راه ۱ — همیشه کار می‌کند: بارگذاری فایل صوتی
            </Typography>
            <Typography variant="body2" color="text.secondary">
              صدا را با «ضبط صوت ویندوز» یا گوشی ضبط کنید و با دکمهٔ کلیپ صوتی
              (کنار میکروفون در نوار نوشتن) فایل را ارسال کنید. mp3/wav/m4a/ogg تا ۵ مگابایت.
            </Typography>
          </Paper>
          <Paper variant="outlined" sx={{ p: 1.5 }}>
            <Typography fontWeight={700} variant="body2" sx={{ mb: 0.5 }}>
              راه ۲ — فعال‌سازی میکروفون در کروم (یک بار برای همیشه)
            </Typography>
            <Typography variant="body2" color="text.secondary" component="div">
              ۱) در نوار آدرس کروم این را باز کنید: <code>chrome://flags/#unsafely-treat-insecure-origin-as-secure</code><br />
              ۲) در کادر بازشده این نشانی را وارد کنید: <code>{addr}</code><br />
              ۳) گزینه را روی <b>Enabled</b> بگذارید و دکمهٔ <b>Relaunch</b> را بزنید.<br />
              ۴) پس از باز شدن دوبارهٔ مرورگر، دکمهٔ میکروفون کار خواهد کرد.
            </Typography>
          </Paper>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>متوجه شدم</Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// فاز ۶۱ - نوار وضعیت تماس تلفنی (زنگ/گفتگو/پایان) — همیشه بالای چت نمایان است
function fmtDur(sec: number) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function CallBanner({
  call,
  meId,
  onChanged,
  onClosed,
  onError,
  onSurvey,
}: {
  call: CallSessionDto | null;
  meId: string;
  onChanged: (c: CallSessionDto) => void;
  onClosed: () => void;
  onError: (msg: string) => void;
  onSurvey: (templateId: string, callId: string | null) => void;
}) {
  const [, forceTick] = useState(0);
  const isCallee = call?.callee_id === meId;

  // تیک‌تایمر برای نمایش مدت تماس جاری
  useEffect(() => {
    if (call?.status !== "ongoing") return;
    const t = setInterval(() => forceTick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [call?.status]);

  const act = useMutation({
    mutationFn: async (p: { action: "answer" | "decline" | "cancel" | "end" }) => {
      if (!call) throw new Error("تماسی فعال نیست");
      if (p.action === "answer") return answerCall(call.id);
      if (p.action === "decline") return declineCall(call.id);
      if (p.action === "cancel") return cancelCall(call.id);
      return endCall(call.id);
    },
    onSuccess: (c) => {
      if (c.status === "ended") {
        onClosed();
        if (isCallee && c.survey_template_id) onSurvey(c.survey_template_id, c.id);
      } else {
        onChanged(c);
      }
    },
    onError: (e) => onError(errDetail(e)),
  });

  if (!call) return null;

  const other = call.caller_id === meId ? call.callee_name : call.caller_name;
  const elapsed = call.answered_at
    ? Math.max(0, Math.floor((Date.now() - new Date(call.answered_at).getTime()) / 1000))
    : 0;

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        bgcolor: call.status === "ringing" ? "#fff8e6" : "#f2faf2",
        borderColor: call.status === "ringing" ? "#f0d090" : "#bfe3bf",
      }}
    >
      {call.status === "ringing" && !isCallee && (
        <>
          <Typography variant="body2" fontWeight={700}>
            📞 در حال زنگ زدن به {call.callee_name}…
          </Typography>
          <Box sx={{ flex: 1 }} />
          <Button size="small" color="error" variant="contained" startIcon={<CallEndRoundedIcon />} disabled={act.isPending} onClick={() => act.mutate({ action: "cancel" })}>
            لغو تماس
          </Button>
        </>
      )}
      {call.status === "ringing" && isCallee && (
        <>
          <Typography variant="body2" fontWeight={700}>
            📞 تماس ورودی از {call.caller_name}
          </Typography>
          <Box sx={{ flex: 1 }} />
          <Button
            size="small" color="success" variant="contained"
            disabled={act.isPending}
            onClick={() => act.mutate({ action: "answer" })}
          >
            پاسخ به تماس
          </Button>
          <Button size="small" color="error" variant="outlined" disabled={act.isPending} onClick={() => act.mutate({ action: "decline" })}>
            رد
          </Button>
        </>
      )}
      {call.status === "ongoing" && (
        <>
          <Typography variant="body2" fontWeight={700}>
            🎧 در حال تماس با {other} — مدت {fmtDur(elapsed)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            (گفتگوی تلفنی از بستر تلفن انجام می‌شود؛ مدت و نظرسنجی اینجا ثبت می‌شود)
          </Typography>
          <Box sx={{ flex: 1 }} />
          <Button size="small" color="error" variant="contained" startIcon={<CallEndRoundedIcon />} disabled={act.isPending} onClick={() => act.mutate({ action: "end" })}>
            پایان تماس
          </Button>
        </>
      )}
      {call.status === "ended" && (
        <Typography variant="body2" color="text.secondary">
          تماس پایان یافت — مدت {fmtDur(call.duration_sec)}
        </Typography>
      )}
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// فاز ۶۱ - نظرسنجی خودکار پس از پایان تماس (برای گیرندهٔ تماس)
function PostCallSurveyDialog({
  templateId,
  callId,
  onClose,
}: {
  templateId: string | null;
  callId: string | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [values, setValues] = useState<FormValues>({});
  const [error, setError] = useState<string | null>(null);

  const { data: template } = useQuery({
    queryKey: ["post-call-survey", templateId],
    queryFn: () => fetchFormTemplateForFill(templateId!),
    enabled: !!templateId,
  });

  const submit = useMutation({
    mutationFn: async () => {
      if (!template) throw new Error("فرم بارگذاری نشده است");
      const err = validateFormValues(template.fields ?? [], values);
      if (err) throw new Error(err);
      return submitFormResponse(template.id, values, callId ?? undefined);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-forms"] });
      onClose();
    },
    onError: (e) => setError(e instanceof Error ? e.message : errDetail(e)),
  });

  return (
    <Dialog open={!!templateId} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>نظرسنجی پس از تماس</DialogTitle>
      <DialogContent>
        {template ? (
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {template.description || "نظر شما به بهتر شدن خدمات مشاوره کمک می‌کند."}
            </Typography>
            <FormRenderer
              template={template}
              values={values}
              onChange={(id, v) => setValues((s) => ({ ...s, [id]: v }))}
            />
            {error ? <Alert severity="error">{error}</Alert> : null}
          </Stack>
        ) : (
          <Typography color="text.secondary" sx={{ py: 4, textAlign: "center" }}>در حال بارگذاری نظرسنجی…</Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>بعداً</Button>
        <Button variant="contained" disabled={submit.isPending} onClick={() => submit.mutate()}>
          {submit.isPending ? "در حال ارسال…" : "ثبت نظر"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
