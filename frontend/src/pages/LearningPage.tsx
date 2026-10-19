// فاز ۳۴ - B33/B34/B35/B36 سند جامع: محتوا، دوره، آزمون و گواهی — روی دسته‌بندی B32
import {
  Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Paper,
  Snackbar, Alert, Stack, Tab, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { errDetail } from "../api/client";
import { fetchTopics, Topic } from "../api/topics";
import {
  Certificate, ContentItem, Course, CourseSession, Exam, Enrollment, ExamQuestion,
  createContent, createCourse, createCourseSession, createExam, createExamQuestion,
  deleteContent, deleteCourse, deleteCourseSession, deleteExam, deleteExamQuestion,
  fetchCertificates, fetchContents, fetchCourses, fetchEnrollments,
  fetchExamQuestions, fetchExams, issueCertificate, revokeCertificate, updateContent,
  updateCourse, updateEnrollment, updateExam, verifyCertificate,
} from "../api/learning";

type MutVars = { kind: string; id?: string; payload?: Record<string, unknown> };

const fa = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : n.toLocaleString("fa-IR");

const statusChip = (s: string) => {
  const map: Record<string, { label: string; color: "success" | "default" | "warning" | "error" | "info" }> = {
    published: { label: "منتشرشده", color: "success" },
    draft: { label: "پیش‌نویس", color: "default" },
    pending: { label: "در انتظار پرداخت", color: "warning" },
    active: { label: "فعال", color: "success" },
    completed: { label: "تکمیل", color: "info" },
    cancelled: { label: "لغو", color: "error" },
    passed: { label: "قبول", color: "success" },
    failed: { label: "مردود", color: "error" },
    in_progress: { label: "در جریان", color: "warning" },
    issued: { label: "صادرشده", color: "info" },
    settled: { label: "تسویه", color: "success" },
  };
  const it = map[s] ?? { label: s, color: "default" as const };
  return <Chip size="small" label={it.label} color={it.color} variant="outlined" />;
};

export default function LearningPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [enrollCourse, setEnrollCourse] = useState<Course | null>(null);
  const [sessionCourse, setSessionCourse] = useState<Course | null>(null);
  const [questionExam, setQuestionExam] = useState<Exam | null>(null);
  const [issueOpen, setIssueOpen] = useState(false);
  const [verifyNumber, setVerifyNumber] = useState("");
  const [verifyResult, setVerifyResult] = useState<string | null>(null);

  const topics = useQuery({ queryKey: ["topics"], queryFn: () => fetchTopics(true) });
  const contents = useQuery({ queryKey: ["contents"], queryFn: () => fetchContents(true), enabled: tab === 0 });
  const courses = useQuery({ queryKey: ["courses"], queryFn: () => fetchCourses(true), enabled: tab === 1 });
  const exams = useQuery({ queryKey: ["exams"], queryFn: () => fetchExams(true), enabled: tab === 2 });
  const certificates = useQuery({ queryKey: ["certificates"], queryFn: () => fetchCertificates(), enabled: tab === 3 });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["contents"] });
    qc.invalidateQueries({ queryKey: ["courses"] });
    qc.invalidateQueries({ queryKey: ["exams"] });
    qc.invalidateQueries({ queryKey: ["certificates"] });
    qc.invalidateQueries({ queryKey: ["enrollments"] });
    qc.invalidateQueries({ queryKey: ["exam-questions"] });
  };

  // محتوا
  const contentMut = useMutation<unknown, Error, MutVars>({
    mutationFn: ({ kind, id, payload }) => {
      if (kind === "create") return createContent(payload!);
      if (kind === "update") return updateContent(id!, payload!);
      return deleteContent(id!);
    },
    onSuccess: (_d, v) => { invalidate(); setCreateOpen(false); setOkMsg(v.kind === "delete" ? "محتوا حذف شد" : "محتوا ذخیره شد"); },
    onError: (e) => setError(errDetail(e)),
  });

  // دوره
  const courseMut = useMutation<unknown, Error, MutVars>({
    mutationFn: ({ kind, id, payload }) => {
      if (kind === "create") return createCourse(payload!);
      if (kind === "update") return updateCourse(id!, payload!);
      if (kind === "delete") return deleteCourse(id!);
      if (kind === "session") return createCourseSession(id!, payload!);
      return deleteCourseSession(id!, (payload as { session_id: string }).session_id);
    },
    onSuccess: (_d, v) => {
      invalidate(); setCreateOpen(false); setSessionCourse(null);
      setOkMsg(v.kind === "delete" ? "دوره حذف شد" : v.kind === "session" ? "جلسه افزوده شد" : "ذخیره شد");
    },
    onError: (e) => setError(errDetail(e)),
  });

  // آزمون
  const examMut = useMutation<unknown, Error, MutVars>({
    mutationFn: ({ kind, id, payload }) => {
      if (kind === "create") return createExam(payload!);
      if (kind === "update") return updateExam(id!, payload!);
      if (kind === "delete") return deleteExam(id!);
      if (kind === "question") return createExamQuestion(id!, payload!);
      return deleteExamQuestion(id!, (payload as { question_id: string }).question_id);
    },
    onSuccess: (_d, v) => {
      invalidate(); setCreateOpen(false); setQuestionExam(null);
      setOkMsg(v.kind === "delete" ? "آزمون حذف شد" : v.kind === "question" ? "سؤال افزوده شد (پاسخ صحیح فقط سمت سرور)" : "ذخیره شد");
    },
    onError: (e) => setError(errDetail(e)),
  });

  const enrollmentMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateEnrollment(id, { status }),
    onSuccess: (d) => {
      invalidate();
      setOkMsg(d.certificates?.length ? "ثبت‌نام به‌روزرسانی شد؛ گواهی دوره صادر شد" : "ثبت‌نام به‌روزرسانی شد");
    },
    onError: (e) => setError(errDetail(e)),
  });

  const certMut = useMutation<unknown, Error, MutVars>({
    mutationFn: ({ kind, id, payload }) => {
      if (kind === "issue") return issueCertificate(payload!);
      return revokeCertificate(id!, (payload as { reason?: string })?.reason);
    },
    onSuccess: (d, v) => {
      invalidate(); setIssueOpen(false);
      const existed = (d as { already_existed?: boolean } | undefined)?.already_existed ?? false;
      setOkMsg(v.kind === "issue"
        ? (existed ? "گواهی تکراری بود؛ گواهی موجود برگردانده شد" : "گواهی صادر شد")
        : "گواهی باطل شد (verify عمومی نامعتبر می‌شود)");
    },
    onError: (e) => setError(errDetail(e)),
  });

  const doVerify = async () => {
    setVerifyResult(null);
    try {
      const res = await verifyCertificate(verifyNumber.trim());
      setVerifyResult(res.valid
        ? `معتبر ✓ ${res.title} — ${res.holder_name ?? ""}`
        : "نامعتبر — این گواهی باطل شده است");
    } catch (e) {
      setVerifyResult(errDetail(e));
    }
  };

  const topicsList = topics.data ?? [];

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={800}>محتوا و دوره‌ها (B33–B36)</Typography>
        <Chip size="small" label="روی دسته‌بندی B32" variant="outlined" />
        <Box flexGrow={1} />
        {tab === 0 && <Button variant="contained" onClick={() => setCreateOpen(true)}>محتوای جدید</Button>}
        {tab === 1 && <Button variant="contained" onClick={() => setCreateOpen(true)}>دوره جدید</Button>}
        {tab === 2 && <Button variant="contained" onClick={() => setCreateOpen(true)}>آزمون جدید</Button>}
        {tab === 3 && <Button variant="contained" onClick={() => setIssueOpen(true)}>صدور گواهی</Button>}
      </Box>

      <Paper sx={{ p: 1.5 }}>
        <Stack direction="row" spacing={1}>
          <Tab label="محتوا (B33)" onClick={() => setTab(0)} />
          <Tab label="دوره‌ها (B34)" onClick={() => setTab(1)} />
          <Tab label="آزمون‌ها (B35)" onClick={() => setTab(2)} />
          <Tab label="گواهی‌ها (B36)" onClick={() => setTab(3)} />
        </Stack>
      </Paper>

      {/* ---------------- B33 محتوا ---------------- */}
      {tab === 0 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>عنوان</TableCell><TableCell>slug</TableCell><TableCell>دسته</TableCell>
                <TableCell>وضعیت</TableCell><TableCell>انتشار</TableCell><TableCell> </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(contents.data ?? []).map((c: ContentItem) => (
                <TableRow key={c.id}>
                  <TableCell>{c.title}</TableCell>
                  <TableCell><code>{c.slug}</code></TableCell>
                  <TableCell>{c.topic_name ?? "—"}</TableCell>
                  <TableCell>{statusChip(c.status)}</TableCell>
                  <TableCell>{c.published_at ? c.published_at.slice(0, 10) : "—"}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5}>
                      <Button size="small" variant="outlined"
                        disabled={c.status === "published"}
                        onClick={() => contentMut.mutate({ kind: "update", id: c.id, payload: { status: "published" } })}>
                        انتشار
                      </Button>
                      <Button size="small" color="error"
                        onClick={() => contentMut.mutate({ kind: "delete", id: c.id })}>
                        حذف
                      </Button>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
              {!contents.data?.length && <TableRow><TableCell colSpan={6}>موردی نیست</TableCell></TableRow>}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* ---------------- B34 دوره‌ها ---------------- */}
      {tab === 1 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>عنوان</TableCell><TableCell>دسته</TableCell><TableCell>قیمت</TableCell>
                <TableCell>ظرفیت</TableCell><TableCell>وضعیت</TableCell><TableCell>جلسات</TableCell><TableCell> </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(courses.data ?? []).map((c: Course) => (
                <TableRow key={c.id}>
                  <TableCell>{c.title}</TableCell>
                  <TableCell>{c.topic_name ?? "—"}</TableCell>
                  <TableCell>{c.is_free ? "رایگان" : `${fa(c.price_amount)} ریال`}</TableCell>
                  <TableCell>{c.capacity ? `${fa(c.enrolled_count ?? 0)}/${fa(c.capacity)}` : "بی‌نهایت"}</TableCell>
                  <TableCell>{statusChip(c.status)}</TableCell>
                  <TableCell>{fa(c.sessions?.length ?? 0)} جلسه</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5}>
                      <Button size="small" variant="outlined"
                        disabled={c.status === "published"}
                        onClick={() => courseMut.mutate({ kind: "update", id: c.id, payload: { status: "published" } })}>
                        انتشار
                      </Button>
                      <Button size="small" onClick={() => setSessionCourse(c)}>جلسات</Button>
                      <Button size="small" onClick={() => setEnrollCourse(c)}>ثبت‌نام‌ها</Button>
                      <Button size="small" color="error"
                        onClick={() => courseMut.mutate({ kind: "delete", id: c.id })}>حذف</Button>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
              {!courses.data?.length && <TableRow><TableCell colSpan={7}>موردی نیست</TableCell></TableRow>}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* ---------------- B35 آزمون‌ها ---------------- */}
      {tab === 2 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>عنوان</TableCell><TableCell>دوره مرتبط</TableCell><TableCell>سؤال</TableCell>
                <TableCell>حد قبولی</TableCell><TableCell>سقف تلاش</TableCell><TableCell>وضعیت</TableCell><TableCell> </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(exams.data ?? []).map((e: Exam) => (
                <TableRow key={e.id}>
                  <TableCell>{e.title}</TableCell>
                  <TableCell>{e.course_title ?? "مستقل"}</TableCell>
                  <TableCell>{fa(e.question_count ?? 0)}</TableCell>
                  <TableCell>{fa(e.pass_percent)}٪</TableCell>
                  <TableCell>{fa(e.max_attempts)}</TableCell>
                  <TableCell>{statusChip(e.status)}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5}>
                      <Button size="small" variant="outlined"
                        disabled={e.status === "published"}
                        onClick={() => examMut.mutate({ kind: "update", id: e.id, payload: { status: "published" } })}>
                        انتشار
                      </Button>
                      <Button size="small" onClick={() => setQuestionExam(e)}>سؤال‌ها</Button>
                      <Button size="small" color="error"
                        onClick={() => examMut.mutate({ kind: "delete", id: e.id })}>حذف</Button>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
              {!exams.data?.length && <TableRow><TableCell colSpan={7}>موردی نیست</TableCell></TableRow>}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* ---------------- B36 گواهی‌ها ---------------- */}
      {tab === 3 && (
        <Stack spacing={2}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle2" fontWeight={700} mb={1}>اعتبارسنجی عمومی گواهی (شماره یکتا)</Typography>
            <Stack direction="row" spacing={1}>
              <TextField size="small" placeholder="CERT-1404-000001" value={verifyNumber}
                onChange={(e) => setVerifyNumber(e.target.value)} sx={{ maxWidth: 320 }} />
              <Button variant="outlined" onClick={doVerify} disabled={verifyNumber.trim().length < 4}>
                بررسی
              </Button>
            </Stack>
            {verifyResult && <Alert severity={verifyResult.startsWith("معتبر") ? "success" : "warning"} sx={{ mt: 1 }}>{verifyResult}</Alert>}
          </Paper>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>شماره</TableCell><TableCell>عنوان</TableCell><TableCell>دارنده</TableCell>
                  <TableCell>وضعیت</TableCell><TableCell> </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(certificates.data ?? []).map((c: Certificate) => (
                  <TableRow key={c.id}>
                    <TableCell><code>{c.certificate_number}</code></TableCell>
                    <TableCell>{c.title}</TableCell>
                    <TableCell>{c.holder_name ?? c.user_id.slice(0, 8)}</TableCell>
                    <TableCell>{c.revoked ? <Chip size="small" label="باطل‌شده" color="error" /> : <Chip size="small" label="معتبر" color="success" />}</TableCell>
                    <TableCell>
                      {!c.revoked && (
                        <Button size="small" color="error"
                          onClick={() => certMut.mutate({ kind: "revoke", id: c.id, payload: { reason: "ابطال دستی مدیر" } })}>
                          ابطال
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
                {!certificates.data?.length && <TableRow><TableCell colSpan={5}>موردی نیست</TableCell></TableRow>}
              </TableBody>
            </Table>
          </TableContainer>
        </Stack>
      )}

      {/* ---------------- دیالوگ ایجاد محتوا/دوره/آزمون ---------------- */}
      <CreateDialog
        open={createOpen}
        tab={tab}
        topics={topicsList}
        onClose={() => setCreateOpen(false)}
        onSubmit={(payload) => {
          if (tab === 0) contentMut.mutate({ kind: "create", payload });
          else if (tab === 1) courseMut.mutate({ kind: "create", payload });
          else examMut.mutate({ kind: "create", payload });
        }}
      />

      {/* جلسات دوره */}
      {sessionCourse && (
        <SessionsDialog course={sessionCourse} onClose={() => setSessionCourse(null)}
          onAdd={(payload) => courseMut.mutate({ kind: "session", id: sessionCourse.id, payload })}
          onDelete={(sessionId) => courseMut.mutate({ kind: "del-session", id: sessionCourse.id, payload: { session_id: sessionId } })}
        />
      )}

      {/* ثبت‌نام‌های دوره */}
      {enrollCourse && (
        <EnrollmentsDialog course={enrollCourse} onClose={() => setEnrollCourse(null)}
          onSetStatus={(id, status) => enrollmentMut.mutate({ id, status })}
        />
      )}

      {/* سؤال‌های آزمون */}
      {questionExam && (
        <QuestionsDialog exam={questionExam} onClose={() => setQuestionExam(null)}
          onAdd={(payload) => examMut.mutate({ kind: "question", id: questionExam.id, payload })}
          onDelete={(qid) => examMut.mutate({ kind: "del-question", id: questionExam.id, payload: { question_id: qid } })}
        />
      )}

      {/* صدور گواهی دستی */}
      <IssueDialog open={issueOpen} courses={courses.data ?? []} exams={exams.data ?? []}
        onClose={() => setIssueOpen(false)}
        onSubmit={(payload) => certMut.mutate({ kind: "issue", payload })}
      />

      <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)}>
        <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>
      </Snackbar>
      <Snackbar open={!!okMsg} autoHideDuration={4000} onClose={() => setOkMsg(null)}>
        <Alert severity="success" onClose={() => setOkMsg(null)}>{okMsg}</Alert>
      </Snackbar>
    </Stack>
  );
}

// ---------------------------------------------------------------- دیالوگ ایجاد
function CreateDialog({ open, tab, topics, onClose, onSubmit }: {
  open: boolean;
  tab: number;
  topics: Topic[];
  onClose: () => void;
  onSubmit: (payload: Record<string, unknown>) => void;
}) {
  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const [topicId, setTopicId] = useState("");
  const [body, setBody] = useState("");
  const [price, setPrice] = useState("0");
  const [capacity, setCapacity] = useState("");
  const [passPercent, setPassPercent] = useState("60");
  const [maxAttempts, setMaxAttempts] = useState("1");
  const [duration, setDuration] = useState("30");
  const label = tab === 0 ? "محتوای جدید" : tab === 1 ? "دوره جدید" : "آزمون جدید";

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const base: Record<string, unknown> = { slug: slug.trim(), title: title.trim() };
    if (topicId) base.topic_id = topicId;
    if (tab === 0) base.body = body;
    if (tab === 1) {
      base.price_amount = Number(price) || 0;
      if (capacity) base.capacity = Number(capacity);
    }
    if (tab === 2) {
      base.pass_percent = Number(passPercent) || 60;
      base.max_attempts = Number(maxAttempts) || 1;
      base.duration_minutes = Number(duration) || 30;
    }
    onSubmit(base);
    setSlug(""); setTitle(""); setTopicId(""); setBody(""); setPrice("0"); setCapacity("");
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>{label} — اتصال به دسته موضوعی B32</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField required label="slug (لاتین کوچک)" value={slug} onChange={(e) => setSlug(e.target.value)} />
            <TextField required label="عنوان" value={title} onChange={(e) => setTitle(e.target.value)} />
            <TextField select label="دسته موضوعی (اختیاری)" value={topicId} onChange={(e) => setTopicId(e.target.value)}>
              <MenuItem value="">— بدون دسته —</MenuItem>
              {topics.map((t) => <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>)}
            </TextField>
            {tab === 0 && (
              <TextField label="متن" value={body} onChange={(e) => setBody(e.target.value)} multiline minRows={4} />
            )}
            {tab === 1 && (
              <>
                <TextField label="قیمت (ریال — ۰ = رایگان)" type="number" value={price} onChange={(e) => setPrice(e.target.value)} />
                <TextField label="ظرفیت (خالی = بی‌نهایت)" type="number" value={capacity} onChange={(e) => setCapacity(e.target.value)} />
              </>
            )}
            {tab === 2 && (
              <>
                <TextField label="حد قبولی (٪)" type="number" value={passPercent} onChange={(e) => setPassPercent(e.target.value)} />
                <TextField label="سقف تلاش" type="number" value={maxAttempts} onChange={(e) => setMaxAttempts(e.target.value)} />
                <TextField label="مدت (دقیقه)" type="number" value={duration} onChange={(e) => setDuration(e.target.value)} />
              </>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained">ایجاد</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------- جلسات دوره
function SessionsDialog({ course, onClose, onAdd, onDelete }: {
  course: Course;
  onClose: () => void;
  onAdd: (payload: Record<string, unknown>) => void;
  onDelete: (sessionId: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [when, setWhen] = useState("");
  const qc = useQueryClient();
  const sessionsQuery = useQuery({
    queryKey: ["courses"],
    queryFn: () => fetchCourses(true),
    select: (data: Course[]) => data.find((c) => c.id === course.id)?.sessions ?? [],
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onAdd({ title: title.trim(), session_date: new Date(when).toISOString() });
    setTitle(""); setWhen("");
    void qc;
  };
  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>جلسات دوره «{course.title}»</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <Table size="small">
              <TableHead><TableRow><TableCell>عنوان</TableCell><TableCell>زمان</TableCell><TableCell> </TableCell></TableRow></TableHead>
              <TableBody>
                {(sessionsQuery.data ?? []).map((s: CourseSession) => (
                  <TableRow key={s.id}>
                    <TableCell>{s.title}</TableCell>
                    <TableCell>{new Date(s.session_date).toLocaleString("fa-IR")}</TableCell>
                    <TableCell><Button size="small" color="error" onClick={() => onDelete(s.id)}>حذف</Button></TableCell>
                  </TableRow>
                ))}
                {!sessionsQuery.data?.length && <TableRow><TableCell colSpan={3}>جلسه‌ای ثبت نشده</TableCell></TableRow>}
              </TableBody>
            </Table>
            <TextField required label="عنوان جلسه" value={title} onChange={(e) => setTitle(e.target.value)} />
            <TextField required label="زمان جلسه" type="datetime-local" value={when}
              onChange={(e) => setWhen(e.target.value)}
              InputLabelProps={{ shrink: true }} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>بستن</Button>
          <Button type="submit" variant="contained">افزودن جلسه</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------- ثبت‌نام‌ها
function EnrollmentsDialog({ course, onClose, onSetStatus }: {
  course: Course;
  onClose: () => void;
  onSetStatus: (id: string, status: string) => void;
}) {
  const q = useQuery({ queryKey: ["enrollments", course.id], queryFn: () => fetchEnrollments(course.id) });
  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>ثبت‌نام‌های دوره «{course.title}»</DialogTitle>
      <DialogContent>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>کاربر</TableCell><TableCell>وضعیت</TableCell><TableCell>سفارش</TableCell><TableCell>اقدام</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(q.data ?? []).map((e: Enrollment) => (
              <TableRow key={e.id}>
                <TableCell>{e.display_name ?? e.username ?? e.user_id.slice(0, 8)}</TableCell>
                <TableCell>{statusChip(e.status)}</TableCell>
                <TableCell>{e.order_number ?? "—"}</TableCell>
                <TableCell>
                  <Stack direction="row" spacing={0.5}>
                    {e.status === "pending" && (
                      <Button size="small" onClick={() => onSetStatus(e.id, "active")}>فعال‌سازی</Button>
                    )}
                    {e.status !== "completed" && (
                      <Button size="small" variant="outlined"
                        onClick={() => onSetStatus(e.id, "completed")}>
                        تکمیل (صدور گواهی)
                      </Button>
                    )}
                    {e.status !== "cancelled" && (
                      <Button size="small" color="error" onClick={() => onSetStatus(e.id, "cancelled")}>لغو</Button>
                    )}
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
            {!q.data?.length && <TableRow><TableCell colSpan={4}>ثبت‌نامی نیست</TableCell></TableRow>}
          </TableBody>
        </Table>
      </DialogContent>
      <DialogActions><Button onClick={onClose}>بستن</Button></DialogActions>
    </Dialog>
  );
}

// ---------------------------------------------------------------- سؤال‌های آزمون
function QuestionsDialog({ exam, onClose, onAdd, onDelete }: {
  exam: Exam;
  onClose: () => void;
  onAdd: (payload: Record<string, unknown>) => void;
  onDelete: (qid: string) => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [opts, setOpts] = useState("گزینه ۱\nگزینه ۲");
  const [correct, setCorrect] = useState("0");
  const q = useQuery({ queryKey: ["exam-questions", exam.id], queryFn: () => fetchExamQuestions(exam.id) });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const options = opts.split("\n").map((s) => s.trim()).filter(Boolean);
    onAdd({ prompt: prompt.trim(), options, correct_index: Number(correct) || 0 });
    setPrompt("");
  };
  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>سؤال‌های آزمون «{exam.title}» — پاسخ صحیح فقط سمت سرور</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>سؤال</TableCell><TableCell>گزینه‌ها</TableCell><TableCell>پاسخ صحیح</TableCell><TableCell> </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(q.data ?? []).map((item: ExamQuestion) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.prompt}</TableCell>
                    <TableCell>{item.options.join(" / ")}</TableCell>
                    <TableCell>{item.correct_index !== undefined ? item.options[item.correct_index] : "—"}</TableCell>
                    <TableCell><Button size="small" color="error" onClick={() => onDelete(item.id)}>حذف</Button></TableCell>
                  </TableRow>
                ))}
                {!q.data?.length && <TableRow><TableCell colSpan={4}>سؤالی نیست</TableCell></TableRow>}
              </TableBody>
            </Table>
            <TextField required label="متن سؤال" value={prompt} onChange={(e) => setPrompt(e.target.value)} multiline minRows={2} />
            <TextField label="گزینه‌ها (هر خط یک گزینه، ۲ تا ۶)" value={opts} onChange={(e) => setOpts(e.target.value)} multiline minRows={3} />
            <TextField label="اندیس پاسخ صحیح (از صفر)" type="number" value={correct} onChange={(e) => setCorrect(e.target.value)} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>بستن</Button>
          <Button type="submit" variant="contained">افزودن سؤال</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------- صدور گواهی دستی
function IssueDialog({ open, courses, exams, onClose, onSubmit }: {
  open: boolean;
  courses: Course[];
  exams: Exam[];
  onClose: () => void;
  onSubmit: (payload: Record<string, unknown>) => void;
}) {
  const [userId, setUserId] = useState("");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<"course" | "exam">("course");
  const [refId, setRefId] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const payload: Record<string, unknown> = { user_id: userId.trim(), title: title.trim() };
    if (kind === "course" && refId) payload.course_id = refId;
    if (kind === "exam" && refId) payload.exam_id = refId;
    onSubmit(payload);
  };
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>صدور دستی گواهی (idempotent)</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField required label="شناسه کاربر (UUID)" value={userId} onChange={(e) => setUserId(e.target.value)} />
            <TextField required label="عنوان گواهی" value={title} onChange={(e) => setTitle(e.target.value)} />
            <TextField select label="نوع مرجع" value={kind} onChange={(e) => setKind(e.target.value as "course" | "exam")}>
              <MenuItem value="course">دوره</MenuItem>
              <MenuItem value="exam">آزمون</MenuItem>
            </TextField>
            <TextField select required label="مرجع" value={refId} onChange={(e) => setRefId(e.target.value)}>
              {(kind === "course" ? courses.map((c) => ({ id: c.id, label: c.title }))
                : exams.map((x) => ({ id: x.id, label: x.title }))
              ).map((o) => <MenuItem key={o.id} value={o.id}>{o.label}</MenuItem>)}
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained">صدور</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
