// فاز ۸۳ — فرم‌ساز گرافیکی ابزار آزمون: محیط کامل ویرایش برای مدیر
// (مشخصات + سؤال‌ها/گزینه‌ها/تصویر + بازه‌های تفسیر + درخت مقیاس‌های گزارش تحلیلی)
// با «پیش‌نمایش زندهٔ تجربهٔ کاربر» قبل از اعمال روی فرم اصلی.
// ذخیره = جایگزینی کامل سمت سرور (PUT) + بازگشت ابزار منتشرشده به پیش‌نویس (D08).
import {
  Alert, Box, Button, Chip, CircularProgress, Divider, FormControl, IconButton, InputLabel,
  LinearProgress, MenuItem, Paper, Select, Snackbar, Stack, Tab, Tabs, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { errDetail } from "../api/client";
import { fetchTopics } from "../api/topics";
import {
  PsychQuestion, PsychScaleNode, PsychTest, ScaleLevel,
  fetchInterpretations, fetchPsychQuestions, fetchPsychScales, fetchPsychTests,
  putPsychInterpretations, putPsychQuestions, putPsychScales, ScaleReplaceNode,
  updatePsychTest, uploadPsychQuestionImage,
} from "../api/psych";
import { OptionsEditor, OptionRow } from "../components/FormKit";
import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import ArrowUpwardRoundedIcon from "@mui/icons-material/ArrowUpwardRounded";
import ArrowDownwardRoundedIcon from "@mui/icons-material/ArrowDownwardRounded";
import AddCircleOutlineRoundedIcon from "@mui/icons-material/AddCircleOutlineRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import EditRoundedIcon from "@mui/icons-material/EditRounded";
import VisibilityRoundedIcon from "@mui/icons-material/VisibilityRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import CircleRoundedIcon from "@mui/icons-material/CircleRounded";
import ImageIcon from "@mui/icons-material/ImageRounded";

type Direction = "higher_worse" | "higher_better" | "balanced";

interface DraftQ {
  id?: string;
  prompt: string;
  options: OptionRow[];
  subscale: string;
  image_path: string | null;
  image_url: string | null;
}

interface DraftI {
  id?: string;
  score_min: number;
  score_max: number;
  label: string;
  guidance: string;
}

interface DraftS {
  key: string;
  title: string;
  description: string;
  match_names: string; // ورودی آزاد: نام‌ها با کاما
  levels: ScaleLevel[];
  direction: Direction;
  color: string;
  children: DraftS[];
}

const DIRECTION_TITLES: Record<Direction, string> = {
  higher_worse: "نمرهٔ بالاتر = مشکل بیشتر (بالینی)",
  higher_better: "نمرهٔ بالاتر = توانمندی بیشتر",
  balanced: "دوسویه (صفات شخصیتی)",
};

const emptyScale = (): DraftS => ({
  key: "", title: "", description: "", match_names: "",
  levels: [{ min: 0, max: 0, label: "", text: "", guidance: "" }],
  direction: "balanced", color: "#b04a5a", children: [],
});

const fromQRows = (rows: PsychQuestion[]): DraftQ[] =>
  rows.map((q) => ({
    id: q.id, prompt: q.prompt, options: (q.options ?? []).map((o) => ({ ...o })),
    subscale: q.subscale ?? "",
    // فاز ۸۳ - image_path از سرور برمی‌گردد تا ذخیرهٔ بعدی تصویر موجود را پاک نکند
    image_path: q.image_path ?? null,
    image_url: q.image_url ?? null,
  }));

const fromSNode = (n: PsychScaleNode): DraftS => ({
  key: n.key, title: n.title, description: n.description ?? "",
  match_names: (n.match_names ?? []).join("، "),
  levels: (n.levels ?? []).map((l) => ({ ...l })),
  direction: n.direction, color: n.color ?? "", children: n.children.map(fromSNode),
});

const toServerScales = (s: DraftS[]): ScaleReplaceNode[] =>
  s.map((n) => ({
    key: n.key.trim(), title: n.title.trim(), description: n.description.trim() || null,
    match_names: n.match_names.split(/[،,]/).map((m) => m.trim()).filter(Boolean),
    levels: n.levels.map((l) => ({ ...l })),
    direction: n.direction,
    color: n.color.trim() || null,
    children: toServerScales(n.children),
  }));

/** نام‌های زیرمقیاس موجود در فرم — برای پیشنهاد اتصال مقیاس به سؤال */
const collectScaleNames = (scales: DraftS[], questions: DraftQ[]): string[] => {
  const names = new Set<string>();
  const walk = (nodes: DraftS[]) => {
    for (const n of nodes) {
      n.match_names.split(/[،,]/).map((m) => m.trim()).filter(Boolean).forEach((m) => names.add(m));
      walk(n.children);
    }
  };
  walk(scales);
  questions.forEach((q) => q.subscale.trim() && names.add(q.subscale.trim()));
  return [...names];
};

// ------------------------------------------------------- فاز ۸۳ج: لانچر فرم‌ساز
// ورود از منوی «فرم‌ساز آزمون‌ها» (گروه سامانه و پشتیبانی) بدون شناسهٔ ابزار —
// ابتدا ابزار انتخاب می‌شود، بعد ویرایشگر پنج‌تبی باز می‌شود.
const STATUS_LABEL: Record<string, string> = {
  draft: "پیش‌نویس", pending_review: "در انتظار تأیید ناظر",
  published: "منتشرشده", rejected: "ردشده",
};

function BuilderLauncher({ tests }: { tests: PsychTest[] }) {
  const navigate = useNavigate();
  return (
    <Box sx={{ maxWidth: 860, mx: "auto", p: { xs: 2, md: 3 } }}>
      <Typography variant="h6" fontWeight={800} mb={1}>فرم‌ساز آزمون‌ها</Typography>
      <Typography variant="body2" color="text.secondary" mb={2}>
        ابزار موردنظر را انتخاب کنید — ویرایش کامل فرم (مشخصات، سؤال‌ها، بازه‌های تفسیر،
        مقیاس‌ها) با پیش‌نمایش زندهٔ تجربهٔ کاربر، قبل از اعمال روی فرم اصلی.
      </Typography>
      {tests.length === 0 ? (
        <Alert severity="info">هنوز ابزاری ثبت نشده است — از «مرکز آزمون روان‌شناسی» یک ابزار بسازید.</Alert>
      ) : (
        <Stack spacing={1.5}>
          {tests.map((t) => (
            <Paper key={t.id} variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" alignItems="center" spacing={1.5} flexWrap="wrap" useFlexGap>
                <Typography variant="subtitle2" fontWeight={800}>{t.title}</Typography>
                <Chip size="small" variant="outlined" label={STATUS_LABEL[t.status] ?? t.status} />
                <Chip size="small" variant="outlined"
                  label={`${(t.question_count ?? 0).toLocaleString("fa-IR")} سؤال`} />
                <Box flexGrow={1} />
                <Button variant="contained" size="small" startIcon={<EditRoundedIcon />}
                  onClick={() => navigate(`/psych-tests/${t.id}/builder`)}>
                  ویرایش فرم
                </Button>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}
    </Box>
  );
}

export default function PsychTestBuilderPage() {
  const { testId = "" } = useParams<{ testId: string }>();
  const qc = useQueryClient();

  const tests = useQuery({ queryKey: ["psych-tests"], queryFn: fetchPsychTests });
  const test: PsychTest | undefined = useMemo(
    () => tests.data?.find((t) => t.id === testId), [tests.data, testId],
  );
  const topics = useQuery({ queryKey: ["topics"], queryFn: () => fetchTopics(true) });

  // ---------- draft state (ویرایش محلی تا «ذخیرهٔ تغییرات») ----------
  const [meta, setMeta] = useState({
    title: "", description: "", topic_id: "", code: "", age_range: "",
    estimated_minutes: "", accent_color: "#8a3342",
  });
  const [questions, setQuestions] = useState<DraftQ[]>([]);
  const [interps, setInterps] = useState<DraftI[]>([]);
  const [scales, setScales] = useState<DraftS[]>([]);
  const [dirty, setDirty] = useState(false);
  const [tab, setTab] = useState(0);
  const [snack, setSnack] = useState<{ msg: string; ok: boolean } | null>(null);
  const loadedRef = useRef(false);

  useEffect(() => {
    if (loadedRef.current || !tests.data || !test) return;
    setMeta({
      title: test.title, description: test.description ?? "",
      topic_id: test.topic_id ?? "", code: test.code ?? "",
      age_range: test.age_range ?? "",
      estimated_minutes: test.estimated_minutes != null ? String(test.estimated_minutes) : "",
      accent_color: test.accent_color ?? "#8a3342",
    });
    loadedRef.current = true;
  }, [tests.data, test]);

  const mark = () => setDirty(true);

  // سؤال‌ها / بازه‌ها / مقیاس‌ها از سرور — فاز ۸۳ج: در حالت لانچر (بدون شناسه)
  // این فراخوانی‌ها غیرفعال می‌شوند تا به URL خراب نزنند
  const qRows = useQuery({ queryKey: ["psych-questions", testId], queryFn: () => fetchPsychQuestions(testId), enabled: !!testId });
  const iRows = useQuery({ queryKey: ["psych-interps", testId], queryFn: () => fetchInterpretations(testId), enabled: !!testId });
  const sRows = useQuery({ queryKey: ["psych-scales", testId], queryFn: () => fetchPsychScales(testId), enabled: !!testId });
  useEffect(() => {
    if (loadedRef.current) return;
    if (qRows.data) setQuestions(fromQRows(qRows.data));
    if (iRows.data) setInterps(iRows.data.map((i) => ({
      id: i.id, score_min: i.score_min, score_max: i.score_max,
      label: i.label, guidance: i.guidance ?? "",
    })));
    if (sRows.data) setScales(sRows.data.map(fromSNode));
  }, [qRows.data, iRows.data, sRows.data]);
  const stillLoading = !tests.data || !qRows.data || !iRows.data || !sRows.data;

  // نام‌های زیرمقیاس موجود در فرم (پیشنهاد اتصال مقیاس به سؤال) — بدون useMemo تا
  // ترتیب هوک‌ها مستقل از وضعیت لود ثابت بماند (قاعدهٔ React)
  const scaleNames = collectScaleNames(scales, questions);

  // ---------- ذخیره (اعمال روی فرم اصلی) ----------
  const saveMut = useMutation({
    mutationFn: async () => {
      await updatePsychTest(testId, {
        title: meta.title.trim(),
        description: meta.description.trim() || null,
        topic_id: meta.topic_id || null,
        code: meta.code.trim() || null,
        age_range: meta.age_range.trim() || null,
        estimated_minutes: meta.estimated_minutes ? Number(meta.estimated_minutes) : null,
        accent_color: meta.accent_color.trim() || null,
      });
      const qres = await putPsychQuestions(testId, questions.map((q) => ({
        id: q.id ?? null, prompt: q.prompt.trim(),
        options: q.options.map((o) => ({ label: o.label.trim(), score: Number(o.score) || 0 })),
        subscale: q.subscale.trim() || null, image_path: q.image_path,
      })));
      const ires = await putPsychInterpretations(testId, interps.map((i) => ({
        id: i.id ?? null, score_min: Number(i.score_min) || 0, score_max: Number(i.score_max) || 0,
        label: i.label.trim(), guidance: i.guidance.trim() || null,
      })));
      const sres = await putPsychScales(testId, toServerScales(scales));
      return { qres, ires, sres };
    },
    onSuccess: ({ qres, ires, sres }) => {
      setQuestions(fromQRows(qres));
      setInterps(ires.map((i) => ({ id: i.id, score_min: i.score_min, score_max: i.score_max, label: i.label, guidance: i.guidance ?? "" })));
      setScales(sres.map(fromSNode));
      setDirty(false);
      setSnack({ msg: "تغییرات روی فرم اصلی اعمال شد", ok: true });
      void qc.invalidateQueries({ queryKey: ["psych-tests"] });
      void qc.invalidateQueries({ queryKey: ["psych-questions", testId] });
      void qc.invalidateQueries({ queryKey: ["psych-interps", testId] });
      void qc.invalidateQueries({ queryKey: ["psych-scales", testId] });
    },
    onError: (e) => setSnack({ msg: errDetail(e), ok: false }),
  });

  if (!testId) {
    // فاز ۸۳ج - لانچر: ورود از منو بدون شناسهٔ ابزار (همهٔ هوک‌ها قبل از این
    // بازگشت اجرا شده‌اند — قاعدهٔ React حفظ است)
    return <BuilderLauncher tests={tests.data ?? []} />;
  }
  if (stillLoading) {
    return <CircularProgress sx={{ display: "block", mx: "auto", mt: 8 }} />;
  }
  if (!test) {
    return <Alert severity="error" sx={{ mt: 4 }}>ابزار یافت نشد.</Alert>;
  }

  const move = <T,>(arr: T[], i: number, dir: -1 | 1): T[] => {
    const j = i + dir;
    if (j < 0 || j >= arr.length) return arr;
    const copy = [...arr];
    [copy[i], copy[j]] = [copy[j], copy[i]];
    return copy;
  };

  const updateQ = (i: number, patch: Partial<DraftQ>) => {
    setQuestions((p) => p.map((q, idx) => (idx === i ? { ...q, ...patch } : q)));
    mark();
  };

  return (
    <Stack sx={{ maxWidth: 1080, mx: "auto", py: { xs: 2, md: 3 } }} spacing={2}>
      {/* ---------- هدر ---------- */}
      <Paper sx={{ p: 2, position: "sticky", top: { xs: 56, md: 64 }, zIndex: 5 }}>
        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
          <EditRoundedIcon color="primary" />
          <Box flexGrow={1} minWidth={120}>
            <Typography variant="subtitle1" fontWeight={800} noWrap>
              فرم‌ساز گرافیکی «{test.title}»
            </Typography>
            <Typography variant="caption" color="text.secondary">
              ویرایش کامل فرم اصلی + پیش‌نمایش زنده — تغییرات تا «ذخیره» اعمال نمی‌شود
            </Typography>
          </Box>
          <Chip size="small" label={test.status === "published" ? "منتشرشده" : test.status === "draft" ? "پیش‌نویس" : test.status === "pending_review" ? "در انتظار بازبینی" : "ردشده"}
            color={test.status === "published" ? "success" : test.status === "draft" ? "default" : "warning"} variant="outlined" />
          <Button variant="outlined" startIcon={<VisibilityRoundedIcon />}
            onClick={() => { setTab(4); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
            پیش‌نمایش
          </Button>
          <Button variant="contained" disabled={!dirty || saveMut.isPending}
            onClick={() => saveMut.mutate()}>
            {saveMut.isPending ? "در حال اعمال…" : "ذخیرهٔ تغییرات"}
          </Button>
        </Stack>
        {dirty && <LinearProgress sx={{ mt: 1.5, height: 4, borderRadius: 99 }} />}
      </Paper>

      {test.status === "published" && (
        <Alert severity="warning">
          این ابزار منتشرشده است؛ ذخیرهٔ هر تغییر، آن را به «پیش‌نویس» برمی‌گرداند و انتشار مجدد
          نیازمند تأیید دوبارهٔ ناظر علمی است (قاعدهٔ D08).
        </Alert>
      )}

      <Paper sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Tabs value={tab} onChange={(_e, v) => setTab(v)} variant="fullWidth">
          <Tab label="مشخصات" />
          <Tab label={`سؤال‌ها (${questions.length.toLocaleString("fa-IR")})`} />
          <Tab label={`بازه‌های تفسیر (${interps.length.toLocaleString("fa-IR")})`} />
          <Tab label={`مقیاس‌ها (${scales.length.toLocaleString("fa-IR")})`} />
          <Tab label="پیش‌نمایش زنده" />
        </Tabs>
      </Paper>

      {/* ---------- تب ۱: مشخصات ---------- */}
      {tab === 0 && (
        <Paper sx={{ p: { xs: 2, md: 3 } }} component="form" onSubmit={(e) => { e.preventDefault(); saveMut.mutate(); }}>
          <Stack spacing={2.5}>
            <TextField label="عنوان ابزار" value={meta.title}
              onChange={(e) => { setMeta((p) => ({ ...p, title: e.target.value })); mark(); }} />
            <TextField label="توضیح صفحهٔ ورودی آزمون" value={meta.description} multiline minRows={3}
              onChange={(e) => { setMeta((p) => ({ ...p, description: e.target.value })); mark(); }} />
            <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
              <FormControl fullWidth>
                <InputLabel>دسته موضوعی</InputLabel>
                <Select label="دسته موضوعی" value={meta.topic_id}
                  onChange={(e) => { setMeta((p) => ({ ...p, topic_id: e.target.value })); mark(); }}>
                  <MenuItem value="">— بدون دسته —</MenuItem>
                  {(topics.data ?? []).map((t) => (
                    <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField label="کد ابزار (مثل GHQ-28)" value={meta.code}
                onChange={(e) => { setMeta((p) => ({ ...p, code: e.target.value })); mark(); }} />
            </Stack>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
              <TextField fullWidth label="محدوده سنی" value={meta.age_range}
                onChange={(e) => { setMeta((p) => ({ ...p, age_range: e.target.value })); mark(); }} />
              <TextField fullWidth label="مدت تخمینی (دقیقه)" type="number" value={meta.estimated_minutes}
                onChange={(e) => { setMeta((p) => ({ ...p, estimated_minutes: e.target.value })); mark(); }} />
              <TextField fullWidth label="رنگ کارت کاتالوگ" type="color" value={meta.accent_color}
                onChange={(e) => { setMeta((p) => ({ ...p, accent_color: e.target.value })); mark(); }}
                InputProps={{ sx: { height: 56 } }} />
            </Stack>
            <Typography variant="caption" color="text.secondary">
              slug («{test.slug}») ثابت است و تغییر نمی‌کند؛ نشانی اجرای آزمون بر پایهٔ آن است.
            </Typography>
          </Stack>
        </Paper>
      )}

      {/* ---------- تب ۲: سؤال‌ها ---------- */}
      {tab === 1 && (
        <Stack spacing={2}>
          {questions.map((q, i) => (
            <Paper key={q.id ?? `new-${i}`} variant="outlined" sx={{ p: { xs: 1.75, md: 2.5 } }}>
              <Stack direction="row" spacing={1} alignItems="center" mb={1.5}>
                <Box sx={{ width: 30, height: 30, borderRadius: 1.5, bgcolor: "primary.main", color: "#fff",
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 800 }}>
                  {(i + 1).toLocaleString("fa-IR")}
                </Box>
                <Typography variant="subtitle2" fontWeight={800} flexGrow={1}>سؤال {(i + 1).toLocaleString("fa-IR")}</Typography>
                <IconButton size="small" disabled={i === 0} onClick={() => { setQuestions((p) => move(p, i, -1)); mark(); }}>
                  <ArrowUpwardRoundedIcon fontSize="small" />
                </IconButton>
                <IconButton size="small" disabled={i === questions.length - 1} onClick={() => { setQuestions((p) => move(p, i, 1)); mark(); }}>
                  <ArrowDownwardRoundedIcon fontSize="small" />
                </IconButton>
                <IconButton size="small" color="error" onClick={() => { setQuestions((p) => p.filter((_x, idx) => idx !== i)); mark(); }}>
                  <DeleteOutlineRoundedIcon fontSize="small" />
                </IconButton>
              </Stack>
              <Stack spacing={2}>
                <TextField label="متن سؤال" multiline minRows={2} fullWidth value={q.prompt}
                  onChange={(e) => updateQ(i, { prompt: e.target.value })} />
                <OptionsEditor options={q.options} scales={scaleNames}
                  onChange={(rows) => updateQ(i, { options: rows })} />
                <TextField fullWidth size="small" label="نام زیرمقیاس (اختیاری — فقط برای نمره‌دهی؛ به کاربر نشان داده نمی‌شود)"
                  value={q.subscale} onChange={(e) => updateQ(i, { subscale: e.target.value })} />
                {/* تصویر پیوست سؤال (ماتریس ریون و …) */}
                <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
                  <Button component="label" variant="outlined" size="small" startIcon={<ImageIcon />}>
                    {q.image_url ? "تغییر تصویر" : "افزودن تصویر"}
                    <input type="file" hidden accept="image/png,image/jpeg,image/webp"
                      onChange={async (e) => {
                        const f = e.target.files?.[0];
                        e.target.value = "";
                        if (!f) return;
                        try {
                          const up = await uploadPsychQuestionImage(testId, f);
                          updateQ(i, { image_path: up.image_path, image_url: up.image_url });
                        } catch (err) {
                          setSnack({ msg: errDetail(err), ok: false });
                        }
                      }} />
                  </Button>
                  {q.image_url && (
                    <>
                      <Box component="img" src={q.image_url} alt="تصویر سؤال"
                        sx={{ maxHeight: 90, maxWidth: 160, borderRadius: 1.5, border: "1px solid #ece2e4" }} />
                      <Button size="small" color="error"
                        onClick={() => updateQ(i, { image_path: null, image_url: null })}>
                        حذف تصویر
                      </Button>
                    </>
                  )}
                </Stack>
              </Stack>
            </Paper>
          ))}
          <Button variant="outlined" startIcon={<AddCircleOutlineRoundedIcon />}
            onClick={() => {
              setQuestions((p) => [...p, {
                prompt: "", subscale: "", image_path: null, image_url: null,
                options: [
                  { label: "هرگز", score: 0 }, { label: "گاهی", score: 1 },
                  { label: "اغلب", score: 2 }, { label: "همیشه", score: 3 },
                ],
              }]);
              mark();
            }}>
            افزودن سؤال جدید
          </Button>
        </Stack>
      )}

      {/* ---------- تب ۳: بازه‌های تفسیر ---------- */}
      {tab === 2 && (
        <Stack spacing={2}>
          {interps.map((it, i) => (
            <Paper key={it.id ?? `new-i-${i}`} variant="outlined" sx={{ p: { xs: 1.75, md: 2.5 } }}>
              <Stack direction="row" spacing={1} alignItems="center" mb={1.5}>
                <Chip size="small" color="primary" variant="outlined"
                  label={`${it.score_min} تا ${it.score_max}`} />
                <Box flexGrow={1} />
                <IconButton size="small" disabled={i === 0} onClick={() => { setInterps((p) => move(p, i, -1)); mark(); }}>
                  <ArrowUpwardRoundedIcon fontSize="small" />
                </IconButton>
                <IconButton size="small" disabled={i === interps.length - 1} onClick={() => { setInterps((p) => move(p, i, 1)); mark(); }}>
                  <ArrowDownwardRoundedIcon fontSize="small" />
                </IconButton>
                <IconButton size="small" color="error" onClick={() => { setInterps((p) => p.filter((_x, idx) => idx !== i)); mark(); }}>
                  <DeleteOutlineRoundedIcon fontSize="small" />
                </IconButton>
              </Stack>
              <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                <TextField label="از نمره" type="number" value={String(it.score_min)}
                  onChange={(e) => { setInterps((p) => p.map((x, idx) => idx === i ? { ...x, score_min: Number(e.target.value) } : x)); mark(); }} />
                <TextField label="تا نمره" type="number" value={String(it.score_max)}
                  onChange={(e) => { setInterps((p) => p.map((x, idx) => idx === i ? { ...x, score_max: Number(e.target.value) } : x)); mark(); }} />
                <TextField fullWidth label="عنوان سطح" value={it.label}
                  onChange={(e) => { setInterps((p) => p.map((x, idx) => idx === i ? { ...x, label: e.target.value } : x)); mark(); }} />
              </Stack>
              <TextField fullWidth multiline minRows={2} sx={{ mt: 2 }}
                label="متن تفسیر (نمایش به کاربر پس از آزمون)" value={it.guidance}
                onChange={(e) => { setInterps((p) => p.map((x, idx) => idx === i ? { ...x, guidance: e.target.value } : x)); mark(); }} />
            </Paper>
          ))}
          <Button variant="outlined" startIcon={<AddCircleOutlineRoundedIcon />}
            onClick={() => { setInterps((p) => [...p, { score_min: 0, score_max: 0, label: "", guidance: "" }]); mark(); }}>
            افزودن بازهٔ تفسیر
          </Button>
        </Stack>
      )}

      {/* ---------- تب ۴: مقیاس‌ها (گزارش تحلیلی) ---------- */}
      {tab === 3 && (
        <Stack spacing={2}>
          <Alert severity="info" variant="outlined">
            مقیاس‌ها ساختار «گزارش تحلیلی» را می‌سازند: هر مقیاس با «نام‌های هم‌نام» به سؤال‌ها وصل
            می‌شود (نام زیرمقیاس در تب سؤال‌ها) و «سطح‌ها» بازه‌های تفسیر آن هستند. مقیاسِ دارای
            زیرمقیاس، نمره‌اش = جمع فرزندها.
          </Alert>
          {scales.map((s, i) => (
            <ScaleEditor key={`root-${i}`} node={s} depth={0} scaleNames={scaleNames}
              onChange={(n) => { setScales((p) => p.map((x, idx) => (idx === i ? n : x))); mark(); }}
              onDelete={() => { setScales((p) => p.filter((_x, idx) => idx !== i)); mark(); }} />
          ))}
          <Button variant="outlined" startIcon={<AddCircleOutlineRoundedIcon />}
            onClick={() => { setScales((p) => [...p, emptyScale()]); mark(); }}>
            افزودن مقیاس اصلی
          </Button>
        </Stack>
      )}

      {/* ---------- تب ۵: پیش‌نمایش زنده ---------- */}
      {tab === 4 && <PreviewRunner title={meta.title || test.title} description={meta.description}
        code={meta.code} accentColor={meta.accent_color || test.accent_color || "#8a3342"}
        questions={questions} />}

      <Snackbar open={!!snack} autoHideDuration={6000} onClose={() => setSnack(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}>
        <Alert severity={snack?.ok ? "success" : "error"} onClose={() => setSnack(null)}>
          {snack?.msg}
        </Alert>
      </Snackbar>
    </Stack>
  );
}

// ============================================================ مقیاس‌ها (بازگشتی)
function ScaleEditor({ node, onChange, onDelete, depth, scaleNames }: {
  node: DraftS; onChange: (n: DraftS) => void; onDelete: () => void;
  depth: number; scaleNames: string[];
}) {
  const patch = (p: Partial<DraftS>) => onChange({ ...node, ...p });
  return (
    <Paper variant="outlined" sx={{ p: { xs: 1.5, md: 2 }, bgcolor: depth ? "#fdf9fa" : "#fff",
      borderRight: depth ? "3px solid #d9b8c0" : "3px solid #8a3342" }}>
      <Stack direction="row" spacing={1} alignItems="center" mb={1.5}>
        <Chip size="small" sx={{ height: 22, fontSize: 11 }}
          label={depth ? "زیرمقیاس" : "مقیاس اصلی"} color={depth ? "secondary" : "primary"} variant="outlined" />
        <Box flexGrow={1} />
        <IconButton size="small" color="error" onClick={onDelete}>
          <DeleteOutlineRoundedIcon fontSize="small" />
        </IconButton>
      </Stack>
      <Stack spacing={2}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
          <TextField size="small" label="عنوان مقیاس" value={node.title}
            onChange={(e) => patch({ title: e.target.value })} />
          <TextField size="small" label="کلید (مثل n-anxiety)" value={node.key}
            onChange={(e) => patch({ key: e.target.value })} />
          <FormControl size="small" fullWidth>
            <InputLabel>جهت رنگ‌بندی گزارش</InputLabel>
            <Select size="small" label="جهت رنگ‌بندی گزارش" value={node.direction}
              onChange={(e) => patch({ direction: e.target.value as Direction })}>
              {(Object.keys(DIRECTION_TITLES) as Direction[]).map((d) => (
                <MenuItem key={d} value={d}>{DIRECTION_TITLES[d]}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
          <TextField size="small" fullWidth multiline minRows={1} label="توضیح مقیاس" value={node.description}
            onChange={(e) => patch({ description: e.target.value })} />
          <TextField size="small" fullWidth label="رنگ نمودار گزارش" type="color" value={node.color || "#b04a5a"}
            onChange={(e) => patch({ color: e.target.value })} InputProps={{ sx: { height: 48 } }} />
        </Stack>
        <TextField size="small" fullWidth
          label="اتصال به سؤال‌ها: نام‌های زیرمقیاس، جدا با کاما"
          placeholder="مثال: اضطراب، اضطراب و بی‌خوابی"
          value={node.match_names}
          onChange={(e) => patch({ match_names: e.target.value })}
          helperText={scaleNames.length
            ? `نام‌های موجود در سؤال‌ها: ${scaleNames.slice(0, 8).join(" • ")}${scaleNames.length > 8 ? " …" : ""}`
            : "هنوز هیچ زیرمقیاسی در سؤال‌ها ثبت نشده است"}
        />
        {/* سطح‌های تفسیر */}
        <Typography variant="caption" fontWeight={700} color="text.secondary">
          سطح‌های تفسیر (اولین بازهٔ شامل نمره انتخاب می‌شود)
        </Typography>
        {node.levels.map((lv, li) => (
          <Paper key={li} variant="outlined" sx={{ p: 1.5, bgcolor: "#fff" }}>
            <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
              <TextField size="small" type="number" label="از" sx={{ maxWidth: { md: 110 } }}
                value={String(lv.min)}
                onChange={(e) => patch({ levels: node.levels.map((x, idx) => idx === li ? { ...x, min: Number(e.target.value) } : x) })} />
              <TextField size="small" type="number" label="تا" sx={{ maxWidth: { md: 110 } }}
                value={String(lv.max)}
                onChange={(e) => patch({ levels: node.levels.map((x, idx) => idx === li ? { ...x, max: Number(e.target.value) } : x) })} />
              <TextField size="small" label="عنوان سطح" fullWidth value={lv.label}
                onChange={(e) => patch({ levels: node.levels.map((x, idx) => idx === li ? { ...x, label: e.target.value } : x) })} />
              <IconButton size="small" color="error"
                onClick={() => patch({ levels: node.levels.filter((_x, idx) => idx !== li) })}>
                <DeleteOutlineRoundedIcon fontSize="small" />
              </IconButton>
            </Stack>
            <TextField size="small" fullWidth multiline minRows={2} sx={{ mt: 1.5 }}
              label="متن تفسیر این سطح" value={lv.text ?? ""}
              onChange={(e) => patch({ levels: node.levels.map((x, idx) => idx === li ? { ...x, text: e.target.value } : x) })} />
            <TextField size="small" fullWidth sx={{ mt: 1.5 }}
              label="توصیه (اختیاری)" value={lv.guidance ?? ""}
              onChange={(e) => patch({ levels: node.levels.map((x, idx) => idx === li ? { ...x, guidance: e.target.value } : x) })} />
          </Paper>
        ))}
        <Button size="small" startIcon={<AddCircleOutlineRoundedIcon />}
          onClick={() => patch({ levels: [...node.levels, { min: 0, max: 0, label: "", text: "", guidance: "" }] })}>
          افزودن سطح
        </Button>
        {/* فرزندان */}
        {node.children.length > 0 && <Divider />}
        <Stack spacing={1.5}>
          {node.children.map((c, ci) => (
            <ScaleEditor key={`ch-${ci}`} node={c} depth={depth + 1} scaleNames={scaleNames}
              onChange={(n) => patch({ children: node.children.map((x, idx) => (idx === ci ? n : x)) })}
              onDelete={() => patch({ children: node.children.filter((_x, idx) => idx !== ci) })} />
          ))}
        </Stack>
        <Button size="small" startIcon={<AddCircleOutlineRoundedIcon />}
          onClick={() => patch({ children: [...node.children, emptyScale()] })}>
          افزودن زیرمقیاس
        </Button>
      </Stack>
    </Paper>
  );
}

// ============================================================ پیش‌نمایش زنده
/** دقیقاً همان تجربهٔ صفحهٔ اجرای آزمون — از روی وضعیت draft (قبل از ذخیره).
 *  بدون ثبت نتیجه و بدون نام زیرمقیاس (مطابق رفتار جدید کاربر نهایی). */
function PreviewRunner({ title, description, code, accentColor, questions }: {
  title: string; description: string; code: string; accentColor: string;
  questions: DraftQ[];
}) {
  const [started, setStarted] = useState(false);
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number>>({});

  if (!questions.length) {
    return <Alert severity="info">هنوز سؤالی در فرم نیست — در تب «سؤال‌ها» سؤال اضافه کنید تا پیش‌نمایش زنده فعال شود.</Alert>;
  }

  const answeredCount = Object.keys(answers).length;
  const progress = (answeredCount / questions.length) * 100;
  const finished = answeredCount === questions.length;

  if (!started) {
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="success" variant="outlined" sx={{ mb: 2 }}>
          پیش‌نمایش زندهٔ تجربهٔ کاربر — از وضعیت فعلی فرم (قبل از ذخیره). هیچ نتیجه‌ای ثبت نمی‌شود.
        </Alert>
        <Typography variant="h5" fontWeight={800} textAlign="center">{title}</Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap justifyContent="center" mt={2}>
          {code && (
            <Chip variant="filled" label={code}
              sx={{ bgcolor: accentColor, color: "#fff", fontWeight: 700 }} />
          )}
          <Chip variant="outlined" label={`${questions.length.toLocaleString("fa-IR")} سؤال`} />
          <Chip variant="outlined" label="بدون نمایش نام زیرمقیاس‌ها (فاز ۸۳)" />
        </Stack>
        {description && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2, lineHeight: 2, textAlign: "center" }}>
            {description}
          </Typography>
        )}
        <Button variant="contained" size="large" sx={{ mt: 3, px: 6, mx: "auto", display: "block" }}
          onClick={() => { setStarted(true); setCurrent(0); setAnswers({}); }}>
          شروع پیش‌نمایش
        </Button>
      </Paper>
    );
  }

  const q = questions[current];
  return (
    <Stack spacing={2}>
      <Alert severity="success" variant="outlined">
        پیش‌نمایش زنده — همین صفحه بعد از ذخیره برای کاربر نمایش داده می‌شود (نام زیرمقیاس‌ها پنهان است).
      </Alert>
      <Stack direction="row" alignItems="center" spacing={1.5} flexWrap="wrap" useFlexGap>
        <Typography variant="subtitle1" fontWeight={800} flexGrow={1}>{title}</Typography>
        <Typography variant="caption" color="text.secondary">
          سؤال {(current + 1).toLocaleString("fa-IR")} از {questions.length.toLocaleString("fa-IR")}
        </Typography>
      </Stack>
      <LinearProgress variant="determinate" value={progress} sx={{ height: 8, borderRadius: 99 }} />
      {finished && (
        <Alert severity="success">
          همهٔ سؤال‌ها پاسخ داده شد — در اجرای واقعی اینجا نتیجه/گزارش نمایش داده می‌شد.
        </Alert>
      )}
      {q && (
        <Paper sx={{ p: { xs: 2, md: 3.5 } }}>
          <Typography variant="h6" fontWeight={800} sx={{ lineHeight: 1.9, mb: 2.5 }}>
            {q.prompt || "(متن سؤال خالی است)"}
          </Typography>
          {q.image_url && (
            <Box component="img" src={q.image_url} alt={q.prompt || "تصویر سؤال"}
              sx={{ display: "block", mx: "auto", mb: 2.5, maxWidth: "100%", maxHeight: 420, borderRadius: 2, border: "1px solid #ece2e4" }} />
          )}
          <Stack spacing={1.25}>
            {q.options.map((opt, oi) => {
              const selected = answers[current] === oi;
              return (
                <Box key={oi} onClick={() => setAnswers((p) => ({ ...p, [current]: oi }))}
                  sx={{
                    px: 2, py: 1.5, borderRadius: 2.5, cursor: "pointer",
                    border: "1.5px solid", borderColor: selected ? "primary.main" : "#ece2e4",
                    bgcolor: selected ? "#faf3f4" : "#fff", transition: "all .15s",
                    "&:hover": { borderColor: "primary.main", bgcolor: "#fdf7f8" },
                    display: "flex", alignItems: "center", gap: 1.5,
                  }}>
                  {selected
                    ? <CheckCircleRoundedIcon color="primary" />
                    : <CircleRoundedIcon sx={{ fontSize: 20, color: "#d3bfc4" }} />}
                  <Typography variant="body1" fontWeight={selected ? 700 : 500}>
                    {opt.label || `(گزینه ${oi + 1} — برچسب خالی)`}
                  </Typography>
                  <Chip size="small" variant="outlined" sx={{ height: 20, fontSize: 10, mr: "auto" }}
                    label={`امتیاز: ${opt.score}`} />
                </Box>
              );
            })}
          </Stack>
        </Paper>
      )}
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Button startIcon={<ArrowForwardRoundedIcon />} disabled={current === 0}
          onClick={() => setCurrent((c) => c - 1)}>
          سؤال قبلی
        </Button>
        <Stack direction="row" spacing={1}>
          <Button color="inherit" onClick={() => { setStarted(false); setAnswers({}); }}>
            پایان پیش‌نمایش
          </Button>
          {current < questions.length - 1 ? (
            <Button variant="contained" endIcon={<ArrowBackRoundedIcon />}
              onClick={() => setCurrent((c) => c + 1)}>
              سؤال بعدی
            </Button>
          ) : (
            <Button variant="contained" color="success"
              onClick={() => setCurrent(0)}>
              بازگشت به سؤال اول
            </Button>
          )}
        </Stack>
      </Stack>
    </Stack>
  );
}
