// فاز ۴۷ - اجرای آزمون روان‌شناسی: سؤال‌به‌سؤال با نوار پیشرفت، پالت سؤال‌ها،
// صفحه نتیجه با گیج نمره و نمودار ریزنمره زیرمقیاس‌ها
import {
  Alert, Box, Button, Chip, CircularProgress, LinearProgress, Paper, Stack,
  Typography,
} from "@mui/material";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { errDetail } from "../api/client";
import {
  AttemptResult, fetchPublicPaper, submitPsychAttempt,
} from "../api/psych";
import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import CircleRoundedIcon from "@mui/icons-material/CircleRounded";
import PrintRoundedIcon from "@mui/icons-material/PrintRounded";
import ListAltRoundedIcon from "@mui/icons-material/ListAltRounded";

/** گیج نمره نیم‌دایره SVG — بدون وابستگی جدید */
function ScoreGauge({ score, max, label }: { score: number; max: number; label: string }) {
  const pct = max > 0 ? Math.min(1, score / max) : 0;
  const R = 78;
  const CX = 100, CY = 96;
  const arc = (p: number) => {
    const a = Math.PI * (1 - p);
    return { x: CX + R * Math.cos(a), y: CY - R * Math.sin(a) };
  };
  const end = arc(pct);
  const color = pct < 0.34 ? "#2e7d32" : pct < 0.67 ? "#ed8c37" : "#c62828";
  return (
    <Box sx={{ position: "relative", width: 200, height: 118 }}>
      <svg viewBox="0 0 200 118" width={200} height={118}>
        <path d={`M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${CX + R} ${CY}`} fill="none" stroke="#f0e4e6" strokeWidth={16} strokeLinecap="round" />
        <path d={`M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${end.x} ${end.y}`} fill="none" stroke={color} strokeWidth={16} strokeLinecap="round" />
        <text x={CX} y={CY - 12} textAnchor="middle" fontSize={34} fontWeight={800} fill={color}>
          {score.toLocaleString("fa-IR")}
        </text>
        <text x={CX} y={CY + 12} textAnchor="middle" fontSize={12} fill="#8a757c">
          از {max.toLocaleString("fa-IR")}
        </text>
      </svg>
      <Chip size="small" label={label} sx={{ position: "absolute", bottom: -6, left: "50%", transform: "translateX(-50%)", bgcolor: color, color: "#fff", fontWeight: 700 }} />
    </Box>
  );
}

export default function PsychTestRunPage() {
  const { slug = "" } = useParams<{ slug: string }>();
  const navigate = useNavigate();

  const paper = useQuery({ queryKey: ["psych-paper", slug], queryFn: () => fetchPublicPaper(slug) });

  const [started, setStarted] = useState(false);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [current, setCurrent] = useState(0);
  const [showPalette, setShowPalette] = useState(false);
  const [result, setResult] = useState<AttemptResult | null>(null);

  const questions = paper.data?.questions ?? [];
  // بیشینه نمره هر سؤال = اندیس آخرین گزینه (گزینه‌ها در همه ابزارهای درج‌شده صعودی‌اند)
  const questionMax = (qi: number) => (questions[qi]?.options.length ? questions[qi].options.length - 1 : 0);
  const totalMax = useMemo(
    () => questions.reduce((acc, _q, qi) => acc + questionMax(qi), 0),
    [questions],
  );

  const submitMut = useMutation({
    mutationFn: () => submitPsychAttempt(slug, questions.map((_, i) => answers[i])),
    onSuccess: (res) => setResult(res),
  });

  const answeredCount = Object.keys(answers).length;
  const progress = questions.length ? (answeredCount / questions.length) * 100 : 0;

  const pick = (optIdx: number) => {
    setAnswers((p) => ({ ...p, [current]: optIdx }));
    // پرش خودکار به سؤال بعد (با تأخیر کوتاه برای حس پاسخ‌گویی)
    setTimeout(() => {
      if (current < questions.length - 1) setCurrent((c) => c + 1);
    }, 220);
  };

  // -------------------------------------------------- نتیجه
  if (result) {
    const a = result.attempt;
    const subs = Object.entries(a.subscale_scores ?? {});
    return (
      <Stack sx={{ maxWidth: 760, mx: "auto", py: 2 }}>
        <Stack spacing={2.5}>
          <Paper sx={{ p: 3, textAlign: "center" }}>
            <CheckCircleRoundedIcon color="success" sx={{ fontSize: 46 }} />
            <Typography variant="h6" fontWeight={800} mt={1}>نتیجه آزمون شما ثبت شد</Typography>
            <Typography variant="body2" color="text.secondary">{paper.data?.test.title}</Typography>
            <Stack alignItems="center" mt={2}>
              <ScoreGauge score={a.score} max={totalMax} label={a.interpretation_label} />
            </Stack>
            {a.interpretation_guidance && (
              <Alert severity="info" sx={{ mt: 2, textAlign: "right" }}>
                {a.interpretation_guidance}
              </Alert>
            )}
          </Paper>

          {subs.length > 0 && (
            <Paper sx={{ p: 2.5 }}>
              <Typography variant="subtitle1" fontWeight={800} mb={2}>ریزنمره ابعاد</Typography>
              <Stack spacing={1.5}>
                {subs.map(([name, val]) => {
                  const subMax = questions
                    .filter((q) => q.subscale === name)
                    .reduce((acc, q) => acc + questionMax(questions.indexOf(q)), 0);
                  const pct = subMax > 0 ? (val / subMax) * 100 : 0;
                  return (
                    <Box key={name}>
                      <Stack direction="row" justifyContent="space-between" mb={0.5}>
                        <Typography variant="body2" fontWeight={700}>{name}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {val.toLocaleString("fa-IR")} از {subMax.toLocaleString("fa-IR")}
                        </Typography>
                      </Stack>
                      <Box sx={{ bgcolor: "#f3e8ea", borderRadius: 99, height: 10 }}>
                        <Box sx={{
                          width: `${pct}%`, height: 10, borderRadius: 99,
                          background: "linear-gradient(90deg,#b04a5a,#7a5c8a)",
                          transition: "width .6s",
                        }} />
                      </Box>
                    </Box>
                  );
                })}
              </Stack>
            </Paper>
          )}

          <Alert severity="warning">{result.disclaimer}</Alert>

          <Stack direction="row" spacing={1.5} justifyContent="center" flexWrap="wrap" useFlexGap>
            <Button variant="outlined" startIcon={<ListAltRoundedIcon />} onClick={() => navigate("/psych-tests")}>
              آزمون‌های دیگر
            </Button>
            <Button variant="outlined" startIcon={<PrintRoundedIcon />} onClick={() => window.print()}>
              چاپ نتیجه
            </Button>
          </Stack>
        </Stack>
      </Stack>
    );
  }

  // -------------------------------------------------- صفحه معرفی
  if (!started) {
    return (
      <Stack sx={{ maxWidth: 760, mx: "auto", py: 2 }}>
        {paper.isLoading && <CircularProgress sx={{ display: "block", mx: "auto", mt: 6 }} />}
        {paper.error && (
          <Alert severity="error">{errDetail(paper.error)}</Alert>
        )}
        {paper.data && (
          <Stack spacing={2.5}>
            <Button startIcon={<ArrowForwardRoundedIcon />} onClick={() => navigate("/psych-tests")}
              sx={{ alignSelf: "flex-start" }}>
              بازگشت به مرکز آزمون
            </Button>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h5" fontWeight={800}>{paper.data.test.title}</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5, lineHeight: 2 }}>
                {paper.data.test.description}
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap mt={2}>
                <Chip variant="outlined" label={`${questions.length.toLocaleString("fa-IR")} سؤال`} />
                <Chip variant="outlined" label="نتیجه فوری پس از پاسخ به همه سؤال‌ها" />
                <Chip variant="outlined" label="پاسخ‌ها محرمانه است" />
              </Stack>
            </Paper>
            <Alert severity="info">
              نکته: پاسخ «صادقانه به حالت فعلی خود» بدهید؛ پاسخ درست/غلطی وجود ندارد. می‌توانید قبل از
              ثبت نهایی، بین سؤال‌ها جابه‌جا شوید و پاسخ‌ها را تغییر دهید.
            </Alert>
            <Button variant="contained" size="large" sx={{ alignSelf: "center", px: 6, py: 1.5 }}
              onClick={() => setStarted(true)}>
              شروع آزمون
            </Button>
          </Stack>
        )}
      </Stack>
    );
  }

  // -------------------------------------------------- اجرا
  const q = questions[current];
  return (
    <Stack sx={{ maxWidth: 860, mx: "auto", py: 2 }}>
      <Stack spacing={2}>
        <Stack direction="row" alignItems="center" spacing={1.5} flexWrap="wrap" useFlexGap>
          <Typography variant="subtitle1" fontWeight={800} flexGrow={1}>
            {paper.data?.test.title}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            سؤال {(current + 1).toLocaleString("fa-IR")} از {questions.length.toLocaleString("fa-IR")}
          </Typography>
          <Button size="small" variant="outlined" onClick={() => setShowPalette((s) => !s)}>
            {showPalette ? "بستن فهرست" : "فهرست سؤال‌ها"}
          </Button>
        </Stack>

        <LinearProgress variant="determinate" value={progress} sx={{ height: 8, borderRadius: 99 }} />

        {showPalette && (
          <Paper variant="outlined" sx={{ p: 1.5 }}>
            <Box display="grid" gridTemplateColumns={{ xs: "repeat(8, 1fr)", md: "repeat(12, 1fr)" }} gap={0.75}>
              {questions.map((_, i) => {
                const done = answers[i] !== undefined;
                return (
                  <Box key={i} onClick={() => setCurrent(i)}
                    sx={{
                      height: 32, borderRadius: 1.5, cursor: "pointer",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 12, fontWeight: 700,
                      bgcolor: i === current ? "primary.main" : done ? "primary.main" : "#f7eef0",
                      opacity: i === current ? 1 : done ? 0.75 : 1,
                      color: i === current || done ? "#fff" : "#8a757c",
                      outline: i === current ? "2px solid #8a3342" : "none",
                      transition: "all .15s",
                    }}>
                    {(i + 1).toLocaleString("fa-IR")}
                  </Box>
                );
              })}
            </Box>
          </Paper>
        )}

        {q && (
          <Paper sx={{ p: { xs: 2, md: 3.5 } }}>
            {q.subscale && (
              <Chip size="small" color="secondary" variant="outlined" label={q.subscale} sx={{ mb: 1.5 }} />
            )}
            <Typography variant="h6" fontWeight={800} sx={{ lineHeight: 1.9, mb: 2.5 }}>
              {q.prompt}
            </Typography>
            <Stack spacing={1.25}>
              {q.options.map((label, oi) => {
                const selected = answers[current] === oi;
                return (
                  <Box key={oi}
                    onClick={() => pick(oi)}
                    sx={{
                      px: 2, py: 1.5, borderRadius: 2.5, cursor: "pointer",
                      border: "1.5px solid",
                      borderColor: selected ? "primary.main" : "#ece2e4",
                      bgcolor: selected ? "#faf3f4" : "#fff",
                      transition: "all .15s",
                      "&:hover": { borderColor: "primary.main", bgcolor: "#fdf7f8" },
                      display: "flex", alignItems: "center", gap: 1.5,
                    }}>
                    {selected
                      ? <CheckCircleRoundedIcon color="primary" />
                      : <CircleRoundedIcon sx={{ fontSize: 20, color: "#d3bfc4" }} />}
                    <Typography variant="body1" fontWeight={selected ? 700 : 500}>{label}</Typography>
                  </Box>
                );
              })}
            </Stack>
          </Paper>
        )}

        <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1} useFlexGap>
          <Button startIcon={<ArrowForwardRoundedIcon />} disabled={current === 0}
            onClick={() => setCurrent((c) => c - 1)}>
            سؤال قبلی
          </Button>
          <Box>
            {current < questions.length - 1 ? (
              <Button variant="contained" endIcon={<ArrowBackRoundedIcon />}
                onClick={() => setCurrent((c) => c + 1)}>
                سؤال بعدی
              </Button>
            ) : (
              <Button variant="contained" color="success"
                disabled={answeredCount < questions.length || submitMut.isPending}
                onClick={() => submitMut.mutate()}>
                {answeredCount < questions.length
                  ? `پاسخ‌دهی: ${answeredCount.toLocaleString("fa-IR")}/${questions.length.toLocaleString("fa-IR")}`
                  : submitMut.isPending ? "در حال ثبت…" : "ثبت و مشاهده نتیجه"}
              </Button>
            )}
          </Box>
        </Stack>

        {submitMut.error && <Alert severity="error">{errDetail(submitMut.error)}</Alert>}
      </Stack>
    </Stack>
  );
}
