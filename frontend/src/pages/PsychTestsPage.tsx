// فاز ۳۵ - B37 سند جامع: تست روان‌شناسی و تفسیر — D08: انتشار فقط با تأیید ناظر علمی
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem,
  Paper, Snackbar, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Tab, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { errDetail } from "../api/client";
import { fetchTopics } from "../api/topics";
import {
  PsychAttempt, PsychInterpretation, PsychQuestion, PsychTest,
  addInterpretation, addPsychQuestion, createPsychTest, fetchInterpretations,
  fetchPsychAttempts, fetchPsychQuestions, fetchPsychTests, fetchMyPsychResults,
  reviewPsychTest, submitPsychTestForReview, updatePsychTest,
} from "../api/psych";

const stChip = (s: string) => {
  const map: Record<string, { label: string; color: "success" | "default" | "warning" | "error" | "info" }> = {
    draft: { label: "پیش‌نویس", color: "default" },
    pending_review: { label: "در انتظار ناظر علمی", color: "warning" },
    published: { label: "منتشرشده (تأیید ناظر)", color: "success" },
    rejected: { label: "رد‌شده", color: "error" },
  };
  const it = map[s] ?? { label: s, color: "default" as const };
  return <Chip size="small" variant="outlined" label={it.label} color={it.color} />;
};

export default function PsychTestsPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [detail, setDetail] = useState<PsychTest | null>(null);
  const [rejectOpen, setRejectOpen] = useState<PsychTest | null>(null);

  const tests = useQuery({ queryKey: ["psych-tests"], queryFn: fetchPsychTests });
  const myResults = useQuery({ queryKey: ["my-psych-results"], queryFn: fetchMyPsychResults, enabled: tab === 1 });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["psych-tests"] });
    qc.invalidateQueries({ queryKey: ["psych-questions"] });
    qc.invalidateQueries({ queryKey: ["psych-interps"] });
    qc.invalidateQueries({ queryKey: ["my-psych-results"] });
  };

  const createMut = useMutation({
    mutationFn: createPsychTest,
    onSuccess: () => { invalidate(); setCreateOpen(false); setOkMsg("ابزار پیش‌نویس ایجاد شد"); },
    onError: (e) => setError(errDetail(e)),
  });
  const submitReviewMut = useMutation({
    mutationFn: submitPsychTestForReview,
    onSuccess: () => { invalidate(); setOkMsg("برای بازبینی ناظر علمی ارسال شد"); },
    onError: (e) => setError(errDetail(e)),
  });
  const reviewMut = useMutation({
    mutationFn: ({ id, approve, note }: { id: string; approve: boolean; note?: string }) =>
      reviewPsychTest(id, { approve, note }),
    onSuccess: (t) => {
      invalidate(); setRejectOpen(null);
      setOkMsg(t.status === "published" ? "ابزار با تأیید ناظر علمی منتشر شد" : "ابزار رد شد");
    },
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={800}>تست روان‌شناسی (B37)</Typography>
        <Chip size="small" variant="outlined" label="D08: انتشار فقط با ناظر علمی" />
        <Box flexGrow={1} />
        {tab === 0 && <Button variant="contained" onClick={() => setCreateOpen(true)}>ابزار جدید</Button>}
      </Box>
      <Alert severity="info">
        چرخه ابزار: پیش‌نویس → ارسال برای بازبینی → تأیید/رد ناظر علمی. ویرایش ابزار منتشرشده
        آن را به پیش‌نویس برمی‌گرداند و باید دوباره تأیید شود. تفسیر فقط از بازه‌های ثبت‌شده است.
      </Alert>
      <Paper sx={{ p: 1.5 }}>
        <Stack direction="row" spacing={1}>
          <Tab label="ابزارها" onClick={() => setTab(0)} />
          <Tab label="نتایج من" onClick={() => setTab(1)} />
        </Stack>
      </Paper>

      {tab === 0 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>عنوان</TableCell><TableCell>سؤال</TableCell><TableCell>بازه تفسیر</TableCell>
                <TableCell>وضعیت</TableCell><TableCell>یادداشت ناظر</TableCell><TableCell>اقدام</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(tests.data ?? []).map((t: PsychTest) => (
                <TableRow key={t.id}>
                  <TableCell>{t.title}</TableCell>
                  <TableCell>{t.question_count}</TableCell>
                  <TableCell>{t.interpretation_count}</TableCell>
                  <TableCell>{stChip(t.status)}</TableCell>
                  <TableCell>{t.review_note ?? "—"}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5}>
                      <Button size="small" onClick={() => setDetail(t)}>مدیریت</Button>
                      {t.status === "draft" || t.status === "rejected" ? (
                        <Button size="small" variant="outlined"
                          onClick={() => submitReviewMut.mutate(t.id)}>ارسال برای بازبینی</Button>
                      ) : null}
                      {t.status === "pending_review" && (
                        <>
                          <Button size="small" color="success"
                            onClick={() => reviewMut.mutate({ id: t.id, approve: true, note: "تأیید علمی" })}>
                            تأیید (ناظر)
                          </Button>
                          <Button size="small" color="error" onClick={() => setRejectOpen(t)}>رد</Button>
                        </>
                      )}
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
              {!tests.data?.length && <TableRow><TableCell colSpan={6}>ابزاری نیست</TableCell></TableRow>}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {tab === 1 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow><TableCell>ابزار</TableCell><TableCell>نمره</TableCell><TableCell>تفسیر</TableCell></TableRow>
            </TableHead>
            <TableBody>
              {(myResults.data ?? []).map((a: PsychAttempt) => (
                <TableRow key={a.id}>
                  <TableCell>{a.test_title}</TableCell>
                  <TableCell>{a.score}</TableCell>
                  <TableCell>{a.interpretation_label} — {a.interpretation_guidance ?? ""}</TableCell>
                </TableRow>
              ))}
              {!myResults.data?.length && <TableRow><TableCell colSpan={3}>نتیجه‌ای ندارید</TableCell></TableRow>}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <CreateTestDialog open={createOpen} onClose={() => setCreateOpen(false)}
        onSubmit={(p) => createMut.mutate(p)} loading={createMut.isPending} />

      {detail && (
        <TestDetailDialog test={detail} onClose={() => setDetail(null)}
          onChanged={() => { invalidate(); qc.invalidateQueries({ queryKey: ["psych-tests"] }); }} />
      )}

      {rejectOpen && (
        <RejectDialog loading={reviewMut.isPending}
          onClose={() => setRejectOpen(null)}
          onSubmit={(note) => reviewMut.mutate({ id: rejectOpen.id, approve: false, note })} />
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

function CreateTestDialog({ open, onClose, onSubmit, loading }: {
  open: boolean; onClose: () => void; loading: boolean;
  onSubmit: (p: Record<string, unknown>) => void;
}) {
  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const topics = useQuery({ queryKey: ["topics"], queryFn: () => fetchTopics(true) });
  const [topicId, setTopicId] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({ slug: slug.trim(), title: title.trim(), description, topic_id: topicId || null });
    setSlug(""); setTitle(""); setDescription(""); setTopicId("");
  };
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>ابزار تست جدید (پیش‌نویس)</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField required label="slug (لاتین کوچک)" dir="ltr" value={slug} onChange={(e) => setSlug(e.target.value)} />
            <TextField required label="عنوان ابزار" value={title} onChange={(e) => setTitle(e.target.value)} />
            <TextField label="توضیح" multiline minRows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
            <TextField select label="دسته موضوعی (اختیاری)" value={topicId} onChange={(e) => setTopicId(e.target.value)}>
              <MenuItem value="">— بدون دسته —</MenuItem>
              {(topics.data ?? []).map((t) => <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>)}
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={loading}>ایجاد</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function TestDetailDialog({ test, onClose, onChanged }: {
  test: PsychTest; onClose: () => void; onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const questions = useQuery({ queryKey: ["psych-questions", test.id], queryFn: () => fetchPsychQuestions(test.id) });
  const interps = useQuery({ queryKey: ["psych-interps", test.id], queryFn: () => fetchInterpretations(test.id) });
  const attempts = useQuery({ queryKey: ["psych-attempts", test.id], queryFn: () => fetchPsychAttempts(test.id) });

  const qMut = useMutation({
    mutationFn: (p: { prompt: string; options: { label: string; score: number }[] }) => addPsychQuestion(test.id, p),
    onSuccess: () => onChanged(),
    onError: (e) => setError(errDetail(e)),
  });
  const iMut = useMutation({
    mutationFn: (p: { score_min: number; score_max: number; label: string }) => addInterpretation(test.id, p),
    onSuccess: () => onChanged(),
    onError: (e) => setError(errDetail(e)),
  });
  const updMut = useMutation({
    mutationFn: (p: Record<string, unknown>) => updatePsychTest(test.id, p),
    onSuccess: () => onChanged(),
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>مدیریت «{test.title}» — {stChip(test.status)}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          {error && <Alert severity="error">{error}</Alert>}
          <QuestionAddForm onSubmit={(p) => qMut.mutate(p)} />
          <Table size="small">
            <TableHead><TableRow><TableCell>سؤال</TableCell><TableCell>گزینه‌ها (امتیاز)</TableCell></TableRow></TableHead>
            <TableBody>
              {(questions.data ?? []).map((q: PsychQuestion) => (
                <TableRow key={q.id}>
                  <TableCell>{q.prompt}</TableCell>
                  <TableCell>{q.options.map((o) => `${o.label} (${o.score})`).join(" / ")}</TableCell>
                </TableRow>
              ))}
              {!questions.data?.length && <TableRow><TableCell colSpan={2}>سؤالی نیست</TableCell></TableRow>}
            </TableBody>
          </Table>
          <InterpAddForm onSubmit={(p) => iMut.mutate(p)} />
          <Table size="small">
            <TableHead><TableRow><TableCell>بازه</TableCell><TableCell>تفسیر</TableCell></TableRow></TableHead>
            <TableBody>
              {(interps.data ?? []).map((i: PsychInterpretation) => (
                <TableRow key={i.id}>
                  <TableCell>{i.score_min} تا {i.score_max}</TableCell>
                  <TableCell>{i.label}</TableCell>
                </TableRow>
              ))}
              {!interps.data?.length && <TableRow><TableCell colSpan={2}>بازه‌ای نیست</TableCell></TableRow>}
            </TableBody>
          </Table>
          <Typography variant="subtitle2" fontWeight={700}>اجراها ({attempts.data?.length ?? 0})</Typography>
          <Table size="small">
            <TableHead><TableRow><TableCell>کاربر</TableCell><TableCell>نمره</TableCell><TableCell>تفسیر</TableCell></TableRow></TableHead>
            <TableBody>
              {(attempts.data ?? []).map((a: PsychAttempt) => (
                <TableRow key={a.id}>
                  <TableCell dir="ltr" sx={{ fontSize: 11 }}>{a.user_id.slice(0, 8)}…</TableCell>
                  <TableCell>{a.score}</TableCell>
                  <TableCell>{a.interpretation_label}</TableCell>
                </TableRow>
              ))}
              {!(attempts.data ?? []).length && <TableRow><TableCell colSpan={3}>اجرایی ثبت نشده</TableCell></TableRow>}
            </TableBody>
          </Table>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => updMut.mutate({})}>ذخیره (بازگشت به پیش‌نویس اگر منتشر شده)</Button>
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}

function QuestionAddForm({ onSubmit }: { onSubmit: (p: { prompt: string; options: { label: string; score: number }[] }) => void }) {
  const [prompt, setPrompt] = useState("");
  const [raw, setRaw] = useState("گزینه ۱: 0\nگزینه ۲: 1\nگزینه ۳: 2\nگزینه ۴: 3");
  const submit = () => {
    const options = raw.split("\n").map((line) => {
      const [label, score] = line.split(":");
      return { label: (label ?? "").trim(), score: Number((score ?? 0).trim()) || 0 };
    }).filter((o) => o.label);
    if (!prompt.trim() || options.length < 2) return;
    onSubmit({ prompt: prompt.trim(), options });
    setPrompt("");
  };
  return (
    <Paper variant="outlined" sx={{ p: 1.5 }}>
      <Typography variant="subtitle2" fontWeight={700} mb={1}>افزودن سؤال</Typography>
      <Stack spacing={1}>
        <TextField size="small" label="متن سؤال" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        <TextField size="small" label="گزینه‌ها (هر خط: برچسب: امتیاز)" value={raw}
          onChange={(e) => setRaw(e.target.value)} multiline minRows={3} />
        <Button variant="contained" onClick={submit}>افزودن سؤال</Button>
      </Stack>
    </Paper>
  );
}

function InterpAddForm({ onSubmit }: {
  onSubmit: (p: { score_min: number; score_max: number; label: string }) => void;
}) {
  const [min, setMin] = useState("0");
  const [max, setMax] = useState("4");
  const [label, setLabel] = useState("");
  const submit = () => {
    if (!label.trim()) return;
    onSubmit({ score_min: Number(min) || 0, score_max: Number(max) || 0, label: label.trim() });
    setLabel("");
  };
  return (
    <Paper variant="outlined" sx={{ p: 1.5 }}>
      <Typography variant="subtitle2" fontWeight={700} mb={1}>افزودن بازه تفسیر</Typography>
      <Stack direction="row" spacing={1}>
        <TextField size="small" label="از نمره" type="number" value={min} onChange={(e) => setMin(e.target.value)} />
        <TextField size="small" label="تا نمره" type="number" value={max} onChange={(e) => setMax(e.target.value)} />
        <TextField size="small" label="برچسب تفسیر" value={label} onChange={(e) => setLabel(e.target.value)} />
        <Button variant="contained" onClick={submit}>افزودن</Button>
      </Stack>
    </Paper>
  );
}

function RejectDialog({ onClose, onSubmit, loading }: {
  onClose: () => void; loading: boolean; onSubmit: (note: string) => void;
}) {
  const [note, setNote] = useState("");
  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={(e) => { e.preventDefault(); onSubmit(note.trim()); }}>
        <DialogTitle>رد ابزار — یادداشت ناظر علمی الزامی است</DialogTitle>
        <DialogContent>
          <TextField required multiline minRows={3} fullWidth value={note}
            onChange={(e) => setNote(e.target.value)} label="یادداشت" />
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" color="error" variant="contained" disabled={loading}>رد ابزار</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
