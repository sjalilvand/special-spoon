// فاز ۳۵ - B23 سند جامع: نظرسنجی/شکایت/تیکت پشتیبانی
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem,
  Paper, Snackbar, Stack, Tab, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { errDetail } from "../api/client";
import {
  Complaint, Ticket, closeTicket, addTicketMessage, createComplaint, createTicket,
  fetchComplaints, fetchSurveySummary, fetchTicket, fetchTickets, reviewComplaint,
  submitSurvey,
} from "../api/support";

const stChip = (s: string) => {
  const map: Record<string, { label: string; color: "success" | "default" | "warning" | "error" | "info" }> = {
    new: { label: "جدید", color: "info" },
    in_review: { label: "در حال بررسی", color: "warning" },
    resolved: { label: "حل‌شده", color: "success" },
    rejected: { label: "رد‌شده", color: "error" },
    open: { label: "باز", color: "info" },
    answered: { label: "پاسخ داده شد", color: "success" },
    closed: { label: "بسته", color: "default" },
  };
  const it = map[s] ?? { label: s, color: "default" as const };
  return <Chip size="small" variant="outlined" label={it.label} color={it.color} />;
};

export default function SupportPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [surveyOpen, setSurveyOpen] = useState(false);
  const [complaintOpen, setComplaintOpen] = useState(false);
  const [ticketOpen, setTicketOpen] = useState(false);
  const [openTicket, setOpenTicket] = useState<Ticket | null>(null);

  const summary = useQuery({ queryKey: ["survey-summary"], queryFn: fetchSurveySummary, enabled: tab === 0 });
  const complaints = useQuery({ queryKey: ["complaints"], queryFn: fetchComplaints, enabled: tab === 1 });
  const tickets = useQuery({ queryKey: ["tickets"], queryFn: fetchTickets, enabled: tab === 2 });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["survey-summary"] });
    qc.invalidateQueries({ queryKey: ["complaints"] });
    qc.invalidateQueries({ queryKey: ["tickets"] });
  };

  const surveyMut = useMutation({
    mutationFn: ({ sessionId, score, comment }: { sessionId: string; score: number; comment?: string }) =>
      submitSurvey(sessionId, { score, comment }),
    onSuccess: () => { invalidate(); setSurveyOpen(false); setOkMsg("نظرسنجی ثبت شد — سپاسگزاریم"); },
    onError: (e) => setError(errDetail(e)),
  });
  const complaintMut = useMutation({
    mutationFn: createComplaint,
    onSuccess: () => { invalidate(); setComplaintOpen(false); setOkMsg("شکایت ثبت شد و در جریان بررسی است"); },
    onError: (e) => setError(errDetail(e)),
  });
  const reviewMut = useMutation({
    mutationFn: ({ id, status, note }: { id: string; status: string; note?: string }) =>
      reviewComplaint(id, { status, resolution_note: note }),
    onSuccess: (c) => { invalidate(); setOkMsg(`شکایت به وضعیت «${c.status}» رفت`); },
    onError: (e) => setError(errDetail(e)),
  });
  const ticketMut = useMutation({
    mutationFn: createTicket,
    onSuccess: () => { invalidate(); setTicketOpen(false); setOkMsg("تیکت ثبت شد"); },
    onError: (e) => setError(errDetail(e)),
  });
  const msgMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: string }) => addTicketMessage(id, body),
    onSuccess: (t) => { invalidate(); setOkMsg(`پاسخ ثبت شد — وضعیت: ${t.status}`); },
    onError: (e) => setError(errDetail(e)),
  });
  const closeMut = useMutation({
    mutationFn: closeTicket,
    onSuccess: () => { invalidate(); setOpenTicket(null); setOkMsg("تیکت بسته شد"); },
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={800}>پشتیبانی (B23)</Typography>
        <Box flexGrow={1} />
        {tab === 0 && <Button variant="contained" onClick={() => setSurveyOpen(true)}>ثبت نظرسنجی جلسه</Button>}
        {tab === 1 && <Button variant="contained" onClick={() => setComplaintOpen(true)}>ثبت شکایت</Button>}
        {tab === 2 && <Button variant="contained" onClick={() => setTicketOpen(true)}>تیکت جدید</Button>}
      </Box>
      <Paper sx={{ p: 1.5 }}>
        <Stack direction="row" spacing={1}>
          <Tab label="نظرسنجی" onClick={() => setTab(0)} />
          <Tab label="شکایات" onClick={() => setTab(1)} />
          <Tab label="تیکت‌ها" onClick={() => setTab(2)} />
        </Stack>
      </Paper>

      {/* نظرسنجی */}
      {tab === 0 && summary.data && (
        <Stack spacing={2}>
          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
            <Paper variant="outlined" sx={{ p: 1.5, minWidth: 160 }}>
              <Typography variant="caption">کل نظرسنجی‌ها</Typography>
              <Typography fontWeight={800}>{summary.data.total.toLocaleString("fa-IR")}</Typography>
            </Paper>
            <Paper variant="outlined" sx={{ p: 1.5, minWidth: 160 }}>
              <Typography variant="caption">میانگین رضایت</Typography>
              <Typography fontWeight={800} color="success.main">
                {summary.data.average.toLocaleString("fa-IR")} از ۵
              </Typography>
            </Paper>
            {[1, 2, 3, 4, 5].map((n) => (
              <Paper key={n} variant="outlined" sx={{ p: 1.5, minWidth: 90 }}>
                <Typography variant="caption">{n} ستاره</Typography>
                <Typography fontWeight={700}>{(summary.data.distribution[String(n)] ?? 0).toLocaleString("fa-IR")}</Typography>
              </Paper>
            ))}
          </Stack>
          {summary.data.recent_comments.length > 0 && (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead><TableRow><TableCell>امتیاز</TableCell><TableCell>نظر</TableCell></TableRow></TableHead>
                <TableBody>
                  {summary.data.recent_comments.map((c, i) => (
                    <TableRow key={i}><TableCell>{c.score}</TableCell><TableCell>{c.comment}</TableCell></TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Stack>
      )}

      {/* شکایات */}
      {tab === 1 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>موضوع</TableCell><TableCell>وضعیت</TableCell><TableCell>یادداشت بررسی</TableCell><TableCell>اقدام</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(complaints.data ?? []).map((c: Complaint) => (
                <TableRow key={c.id}>
                  <TableCell>{c.subject}</TableCell>
                  <TableCell>{stChip(c.status)}</TableCell>
                  <TableCell>{c.resolution_note ?? "—"}</TableCell>
                  <TableCell>
                    {c.status === "new" && (
                      <Button size="small" onClick={() => reviewMut.mutate({ id: c.id, status: "in_review" })}>
                        شروع بررسی
                      </Button>
                    )}
                    {c.status === "in_review" && (
                      <Stack direction="row" spacing={0.5}>
                        <Button size="small" color="success"
                          onClick={() => reviewMut.mutate({ id: c.id, status: "resolved", note: "بررسی و حل شد" })}>
                          حل
                        </Button>
                        <Button size="small" color="error"
                          onClick={() => reviewMut.mutate({ id: c.id, status: "rejected", note: "رد شد" })}>
                          رد
                        </Button>
                      </Stack>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {!complaints.data?.length && <TableRow><TableCell colSpan={4}>موردی نیست</TableCell></TableRow>}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* تیکت‌ها */}
      {tab === 2 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>موضوع</TableCell><TableCell>اولویت</TableCell><TableCell>وضعیت</TableCell>
                <TableCell>پیام‌ها</TableCell><TableCell> </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(tickets.data ?? []).map((t: Ticket) => (
                <TableRow key={t.id}>
                  <TableCell>{t.subject}</TableCell>
                  <TableCell>{t.priority === "high" ? <Chip size="small" color="error" label="فوری" /> : "عادی"}</TableCell>
                  <TableCell>{stChip(t.status)}</TableCell>
                  <TableCell>{t.messages_count}</TableCell>
                  <TableCell>
                    <Button size="small" onClick={async () => {
                      const full = await fetchTicket(t.id);
                      setOpenTicket(full);
                    }}>نخ گفتگو</Button>
                  </TableCell>
                </TableRow>
              ))}
              {!tickets.data?.length && <TableRow><TableCell colSpan={5}>موردی نیست</TableCell></TableRow>}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* دیالوگ نظرسنجی */}
      <SurveyDialog open={surveyOpen} onClose={() => setSurveyOpen(false)}
        onSubmit={(p) => surveyMut.mutate(p as never)} loading={surveyMut.isPending} />
      {/* دیالوگ شکایت */}
      <ComplaintDialog open={complaintOpen} onClose={() => setComplaintOpen(false)}
        onSubmit={(p) => complaintMut.mutate(p)} loading={complaintMut.isPending} />
      {/* دیالوگ تیکت جدید */}
      <TicketDialog open={ticketOpen} onClose={() => setTicketOpen(false)}
        onSubmit={(p) => ticketMut.mutate(p)} loading={ticketMut.isPending} />
      {/* نخ تیکت */}
      {openTicket && (
        <Dialog open onClose={() => setOpenTicket(null)} maxWidth="sm" fullWidth>
          <DialogTitle>{openTicket.subject} — {stChip(openTicket.status)}</DialogTitle>
          <DialogContent>
            <Stack spacing={1} mt={1}>
              {openTicket.messages?.map((m) => (
                <Paper key={m.id} variant="outlined" sx={{ p: 1, bgcolor: m.is_staff ? "action.hover" : "background.paper" }}>
                  <Typography variant="caption">{m.is_staff ? "پشتیبانی" : "کاربر"}</Typography>
                  <Typography>{m.body}</Typography>
                </Paper>
              ))}
              {openTicket.status !== "closed" && (
                <TicketReplyForm onSend={(body) => msgMut.mutate({ id: openTicket.id, body })} loading={msgMut.isPending} />
              )}
            </Stack>
          </DialogContent>
          <DialogActions>
            {openTicket.status !== "closed" && (
              <Button color="error" onClick={() => closeMut.mutate(openTicket.id)}>بستن تیکت</Button>
            )}
            <Button onClick={() => setOpenTicket(null)}>بستن</Button>
          </DialogActions>
        </Dialog>
      )}

      <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)}>
        <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>
      </Snackbar>
      <Snackbar open={!!okMsg} autoHideDuration={4000} onClose={() => setOkMsg(null)}>
        <Alert severity="success" onClose={() => setOkMsg(null)}>{okMsg}</Alert>
      </Snackbar>
    </Stack>
  );
}

function SurveyDialog({ open, onClose, onSubmit, loading }: {
  open: boolean; onClose: () => void; loading: boolean;
  onSubmit: (p: { sessionId: string; score: number; comment?: string }) => void;
}) {
  const [sessionId, setSessionId] = useState("");
  const [score, setScore] = useState(5);
  const [comment, setComment] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({ sessionId: sessionId.trim(), score, comment: comment || undefined });
    setSessionId(""); setScore(5); setComment("");
  };
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>نظرسنجی رضایت پس از جلسه (یک‌بارمصرف)</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField required label="شناسه جلسه (UUID)" dir="ltr" value={sessionId}
              onChange={(e) => setSessionId(e.target.value)} />
            <TextField select label="امتیاز (۱ تا ۵)" value={score}
              onChange={(e) => setScore(Number(e.target.value))}>
              {[1, 2, 3, 4, 5].map((n) => <MenuItem key={n} value={n}>{n}</MenuItem>)}
            </TextField>
            <TextField label="نظر (اختیاری)" multiline minRows={2} value={comment}
              onChange={(e) => setComment(e.target.value)} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={loading}>ثبت</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function ComplaintDialog({ open, onClose, onSubmit, loading }: {
  open: boolean; onClose: () => void; loading: boolean;
  onSubmit: (p: { subject: string; body: string }) => void;
}) {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({ subject: subject.trim(), body });
    setSubject(""); setBody("");
  };
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>ثبت شکایت</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField required label="موضوع" value={subject} onChange={(e) => setSubject(e.target.value)} />
            <TextField required label="شرح کامل" multiline minRows={4} value={body}
              onChange={(e) => setBody(e.target.value)} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={loading}>ثبت شکایت</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function TicketDialog({ open, onClose, onSubmit, loading }: {
  open: boolean; onClose: () => void; loading: boolean;
  onSubmit: (p: { subject: string; body: string; priority: string }) => void;
}) {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState("normal");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({ subject: subject.trim(), body, priority });
    setSubject(""); setBody(""); setPriority("normal");
  };
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>تیکت پشتیبانی جدید</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField required label="موضوع" value={subject} onChange={(e) => setSubject(e.target.value)} />
            <TextField required label="شرح" multiline minRows={3} value={body} onChange={(e) => setBody(e.target.value)} />
            <TextField select label="اولویت" value={priority} onChange={(e) => setPriority(e.target.value)}>
              <MenuItem value="normal">عادی</MenuItem>
              <MenuItem value="high">فوری</MenuItem>
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={loading}>ثبت</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function TicketReplyForm({ onSend, loading }: { onSend: (body: string) => void; loading: boolean }) {
  const [body, setBody] = useState("");
  return (
    <Stack direction="row" spacing={1}>
      <TextField size="small" fullWidth placeholder="پاسخ…" value={body}
        onChange={(e) => setBody(e.target.value)} />
      <Button variant="contained" disabled={!body.trim() || loading}
        onClick={() => { onSend(body.trim()); setBody(""); }}>
        ارسال
      </Button>
    </Stack>
  );
}
