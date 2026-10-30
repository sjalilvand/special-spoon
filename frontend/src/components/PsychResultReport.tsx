// فاز ۶۳ - گزارش تحلیلی چندلایهٔ نتیجهٔ آزمون (مدل مرجع ای‌سنج):
// گیج نمره کل + مقیاس غالب + نمودار راداری پروفایل + منحنی جایگاه نمره هر بعد
// + نوار نقطه‌ای وجه‌ها + کارت تفسیر سطح‌بندی‌شدهٔ هر مقیاس — همه SVG بدون وابستگی جدید
import {
  Alert, Box, Chip, Divider, Paper, Stack, Typography,
} from "@mui/material";
import StarRoundedIcon from "@mui/icons-material/StarRounded";
import type { PsychAttempt, ReportPayload, ReportScale } from "../api/psych";
import { formatJalaliDateTime } from "../utils/jalali";

const fa = (n: number | string) => Number(n).toLocaleString("fa-IR");

/** رنگ سطح بر پایهٔ جهت مقیاس: بالینی (بالا=قرمز)، توانمندی (بالا=سبز)، صفت (خنثی) */
export function levelColor(direction: string, percent: number, scaleColor?: string | null): string {
  if (direction === "higher_worse") return percent < 34 ? "#2e7d32" : percent < 67 ? "#ed8c37" : "#c62828";
  if (direction === "higher_better") return percent < 34 ? "#c62828" : percent < 67 ? "#ed8c37" : "#2e7d32";
  return scaleColor || "#7a5c8a";
}

/** گیج نمره نیم‌دایره — از صفحهٔ اجرا منتقل شد (فاز ۶۳) */
export function ScoreGauge({ score, max, label }: { score: number; max: number; label: string }) {
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
          {fa(score)}
        </text>
        <text x={CX} y={CY + 12} textAnchor="middle" fontSize={12} fill="#8a757c">
          از {fa(max)}
        </text>
      </svg>
      {label && (
        <Chip size="small" label={label} sx={{ position: "absolute", bottom: -6, left: "50%", transform: "translateX(-50%)", bgcolor: color, color: "#fff", fontWeight: 700 }} />
      )}
    </Box>
  );
}

/** نمودار راداری پروفایل (سه‌گوش/پنج‌گوش/…) — مثل نمودار پنج‌گوش مرجع */
function RadarChart({ scales }: { scales: ReportScale[] }) {
  const W = 340, H = 320, CX = W / 2, CY = H / 2 + 6, R = 108;
  const n = scales.length;
  if (n < 3) return null;
  const pt = (i: number, r: number) => {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    return { x: CX + r * Math.cos(a), y: CY + r * Math.sin(a) };
  };
  const ring = (r: number) => scales.map((_, i) => { const p = pt(i, (R * r) / 100); return `${p.x.toFixed(1)},${p.y.toFixed(1)}`; }).join(" ");
  const dataPoly = scales
    .map((s, i) => { const p = pt(i, (R * Math.max(4, s.percent)) / 100); return `${p.x.toFixed(1)},${p.y.toFixed(1)}`; })
    .join(" ");
  return (
    <Box component="svg" viewBox={`0 0 ${W} ${H}`} sx={{ width: "100%", maxWidth: 380, mx: "auto", display: "block" }}>
      {[25, 50, 75, 100].map((r) => (
        <polygon key={r} points={ring(r)} fill="none" stroke={r === 100 ? "#d8c7cb" : "#ece2e4"} strokeWidth={1} />
      ))}
      {scales.map((s, i) => {
        const v = pt(i, R);
        const label = pt(i, R + 22);
        const anchor = Math.abs(label.x - CX) < 12 ? "middle" : label.x > CX ? "start" : "end";
        const c = levelColor(s.direction, s.percent, s.color);
        return (
          <g key={s.key}>
            <line x1={CX} y1={CY} x2={v.x} y2={v.y} stroke="#ece2e4" strokeWidth={1} />
            <circle cx={v.x} cy={v.y} r={3.5} fill={c} />
            <text x={label.x} y={label.y - 2} textAnchor={anchor} fontSize={11.5} fontWeight={700} fill="#5d4a50">
              {s.title}
            </text>
            <text x={label.x} y={label.y + 12} textAnchor={anchor} fontSize={10.5} fill={c} fontWeight={700}>
              {fa(s.percent)}٪
            </text>
          </g>
        );
      })}
      <polygon points={dataPoly} fill="#b04a5a" fillOpacity={0.18} stroke="#b04a5a" strokeWidth={2} />
      {scales.map((s, i) => {
        const p = pt(i, (R * Math.max(4, s.percent)) / 100);
        return <circle key={s.key} cx={p.x} cy={p.y} r={3.5} fill={levelColor(s.direction, s.percent, s.color)} stroke="#fff" strokeWidth={1} />;
      })}
    </Box>
  );
}

/** منحنی جایگاه نمره (نرمال‌نما) — ناحیهٔ تا نمرهٔ شما سایه‌خورده است */
function CurveChart({ percent, color, uid }: { percent: number; color: string; uid: string }) {
  const W = 300, H = 108, BL = 88;
  const cut = 10 + ((W - 20) * Math.min(100, Math.max(0, percent))) / 100;
  return (
    <Box component="svg" viewBox={`0 0 ${W} ${H}`} sx={{ width: "100%", maxWidth: 320, display: "block" }}>
      <defs>
        <clipPath id={`clip-${uid}`}>
          <rect x={10} y={0} width={cut - 10} height={H} />
        </clipPath>
      </defs>
      <path
        d={`M 10 ${BL} C 80 ${BL}, 92 10, 150 10 C 208 10, 220 ${BL}, 290 ${BL} Z`}
        fill="#f5ecef" stroke="#d8c7cb" strokeWidth={1.4}
      />
      <path
        d={`M 10 ${BL} C 80 ${BL}, 92 10, 150 10 C 208 10, 220 ${BL}, 290 ${BL} Z`}
        fill={color} fillOpacity={0.3} stroke="none" clipPath={`url(#clip-${uid})`}
      />
      <line x1={cut} y1={14} x2={cut} y2={BL} stroke={color} strokeWidth={1.6} strokeDasharray="4 3" />
      <circle cx={cut} cy={16} r={3.4} fill={color} />
      <text x={10} y={H - 4} fontSize={9.5} fill="#8a757c">۰ (حداقل)</text>
      <text x={W - 10} y={H - 4} fontSize={9.5} fill="#8a757c" textAnchor="end">۱۰۰ (حداکثر)</text>
    </Box>
  );
}

/** نوار نقطه‌ای وجه‌های یک بعد — ۰ سمت راست (RTL) مانند نمودار مرجع */
function FacetStrip({ facets }: { facets: ReportScale[] }) {
  const W = 700, H = 66, PAD = 30, AX = 44;
  const xAt = (percent: number) => W - PAD - ((W - 2 * PAD) * percent) / 100; // RTL
  const ticks = [0, 25, 50, 75, 100];
  return (
    <Box>
      <Box component="svg" viewBox={`0 0 ${W} ${H}`} sx={{ width: "100%", display: "block" }}>
        <line x1={W - PAD} y1={AX} x2={PAD} y2={AX} stroke="#c9b6bb" strokeWidth={1.4} />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={xAt(t)} y1={AX - 4} x2={xAt(t)} y2={AX + 4} stroke="#c9b6bb" strokeWidth={1} />
            <text x={xAt(t)} y={AX + 16} fontSize={10} fill="#8a757c" textAnchor="middle">{fa(t)}</text>
          </g>
        ))}
        {facets.map((c, i) => {
          const cx = xAt(c.percent);
          const above = i % 2 === 0;
          const color = levelColor(c.direction, c.percent, c.color);
          return (
            <g key={c.key}>
              <line x1={cx} y1={AX} x2={cx} y2={above ? 18 : AX} stroke="#ece2e4" strokeWidth={1} />
              <circle cx={cx} cy={above ? 14 : AX + 0} r={5} fill={color} stroke="#fff" strokeWidth={1.2} />
            </g>
          );
        })}
      </Box>
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mt: 0.75 }}>
        {facets.map((c) => (
          <Stack key={c.key} direction="row" spacing={0.5} alignItems="center">
            <Box sx={{ width: 9, height: 9, borderRadius: "50%", bgcolor: levelColor(c.direction, c.percent, c.color) }} />
            <Typography variant="caption" color="text.secondary">{c.title} — {fa(c.percent)}٪</Typography>
          </Stack>
        ))}
      </Box>
    </Box>
  );
}

/** کارت تفسیر یک مقیاس/وجه */
function ScaleCard({ s, small }: { s: ReportScale; small?: boolean }) {
  const color = levelColor(s.direction, s.percent, s.color);
  return (
    <Paper
      variant={small ? "outlined" : "elevation"}
      elevation={small ? 0 : 1}
      sx={{ p: small ? 1.5 : 2, borderRadius: 2.5, borderColor: "#ece2e4", minWidth: 0 }}
    >
      <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap" useFlexGap>
        <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: color, flexShrink: 0 }} />
        <Typography variant={small ? "body2" : "subtitle2"} fontWeight={800}>{s.title}</Typography>
        {s.level?.label && (
          <Chip size="small" label={s.level.label} sx={{
            height: 20, fontSize: 11, fontWeight: 700, bgcolor: `${color}22`, color,
          }} />
        )}
        <Box flexGrow={1} />
        <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
          {fa(s.score)} از {fa(s.max)} ({fa(s.percent)}٪)
        </Typography>
      </Stack>
      {s.level?.text && (
        <Typography variant="body2" sx={{ mt: 1, lineHeight: 2, textAlign: "justify" }}>
          {s.level.text}
        </Typography>
      )}
      {s.level?.guidance && (
        <Alert severity="info" sx={{ mt: 1, py: 0.5, "& .MuiAlert-message": { py: 0.3, fontSize: 13 } }}>
          {s.level.guidance}
        </Alert>
      )}
    </Paper>
  );
}

/** بخش یک بُعد اصلی: تفسیر + منحنی جایگاه + وجه‌ها */
function DomainSection({ s, index }: { s: ReportScale; index: number }) {
  const color = levelColor(s.direction, s.percent, s.color);
  const facets = s.children ?? [];
  return (
    <Paper sx={{ p: { xs: 2, md: 2.5 }, borderRadius: 3 }}>
      <Stack direction="row" alignItems="center" spacing={1.25} flexWrap="wrap" useFlexGap>
        <Box sx={{
          width: 30, height: 30, borderRadius: "50%", bgcolor: `${color}1e`, color,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 14, fontWeight: 800, flexShrink: 0,
        }}>
          {fa(index + 1)}
        </Box>
        <Typography variant="subtitle1" fontWeight={800}>{s.title}</Typography>
        {s.level?.label && (
          <Chip size="small" label={s.level.label} sx={{ bgcolor: `${color}22`, color, fontWeight: 700 }} />
        )}
        <Box flexGrow={1} />
        <Typography variant="body2" color="text.secondary">
          نمره: {fa(s.score)} از {fa(s.max)} — {fa(s.percent)}٪
        </Typography>
      </Stack>
      {s.description && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5, px: 4.25 }}>
          {s.description}
        </Typography>
      )}
      <Box sx={{ mt: 1.5, display: "grid", gridTemplateColumns: { xs: "1fr", sm: "auto 1fr" }, gap: 2, alignItems: "center" }}>
        <CurveChart percent={s.percent} color={color} uid={s.key} />
        <Box sx={{ minWidth: 0 }}>
          {s.level?.text ? (
            <Typography variant="body2" sx={{ lineHeight: 2.05, textAlign: "justify" }}>
              {s.level.text}
            </Typography>
          ) : (
            <Typography variant="body2" color="text.secondary">تفسیر متنی برای این مقیاس ثبت نشده است.</Typography>
          )}
          {s.level?.guidance && (
            <Alert severity="info" sx={{ mt: 1, py: 0.5, "& .MuiAlert-message": { py: 0.3, fontSize: 13 } }}>
              {s.level.guidance}
            </Alert>
          )}
        </Box>
      </Box>
      {facets.length > 0 && (
        <Box sx={{ mt: 1.5 }}>
          <Divider sx={{ mb: 1.25 }} />
          <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1 }}>
            ریزنمرهٔ وجه‌های {s.title}
          </Typography>
          <FacetStrip facets={facets} />
          <Box display="grid" gridTemplateColumns={{ xs: "1fr", sm: "1fr 1fr" }} gap={1.25} sx={{ mt: 1.25 }}>
            {facets.map((c) => <ScaleCard key={c.key} s={c} small />)}
          </Box>
        </Box>
      )}
    </Paper>
  );
}

/** گزارش کامل — در صفحهٔ نتیجهٔ اجرا و دیالوگ «نتایج من» استفاده می‌شود */
export default function PsychResultReport({
  payload, attempt, testTitle,
}: { payload: ReportPayload; attempt?: PsychAttempt | null; testTitle?: string }) {
  const scales = payload.scales ?? [];
  const topCount = scales.length;
  const demographics = attempt?.demographics ?? null;
  const demoLine = demographics
    ? [
        demographics.gender,
        demographics.age ? `${fa(demographics.age)} ساله` : null,
        demographics.education,
        demographics.marital,
      ].filter(Boolean).join(" · ")
    : null;

  return (
    <Stack spacing={2}>
      {/* سربرگ: مشخصات و نمرهٔ کل */}
      <Paper sx={{ p: { xs: 2, md: 3 }, borderRadius: 3 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2.5} alignItems="center">
          <Box sx={{ flexGrow: 1, minWidth: 0, textAlign: { xs: "center", sm: "right" } }}>
            <Typography variant="h6" fontWeight={800}>
              گزارش تحلیلی {testTitle ? `«${testTitle}»` : "آزمون"}
            </Typography>
            {demoLine && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{demoLine}</Typography>
            )}
            {attempt?.created_at && (
              <Typography variant="caption" color="text.secondary">
                تاریخ اجرا: {formatJalaliDateTime(attempt.created_at)}
              </Typography>
            )}
            {payload.dominant && topCount >= 3 && (
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1.25 }} flexWrap="wrap" useFlexGap>
                <Chip
                  size="small" icon={<StarRoundedIcon />} color="primary" variant="outlined"
                  label={`مقیاس غالب: ${payload.dominant.title} (${fa(payload.dominant.percent)}٪)`}
                />
              </Stack>
            )}
          </Box>
          <ScoreGauge score={payload.total.score} max={payload.total.max} label={payload.total.label ?? ""} />
        </Stack>
        {payload.total.guidance && (
          <Typography variant="body2" sx={{ mt: 1.5, lineHeight: 2, textAlign: "justify" }}>
            {payload.total.guidance}
          </Typography>
        )}
      </Paper>

      {/* نمای کلی پروفایل: رادار + نوار درصد */}
      {topCount >= 3 ? (
        <Paper sx={{ p: { xs: 2, md: 2.5 }, borderRadius: 3 }}>
          <Typography variant="subtitle1" fontWeight={800} sx={{ mb: 1.5 }}>
            نمای کلی پروفایل
          </Typography>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1.2fr" }, gap: 2.5, alignItems: "center" }}>
            <RadarChart scales={scales} />
            <Stack spacing={1.25} sx={{ minWidth: 0 }}>
              {scales.map((s) => {
                const color = levelColor(s.direction, s.percent, s.color);
                return (
                  <Box key={s.key}>
                    <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.4 }}>
                      <Typography variant="body2" fontWeight={700}>{s.title}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {fa(s.score)} از {fa(s.max)} · {fa(s.percent)}٪
                      </Typography>
                    </Stack>
                    <Box sx={{ bgcolor: "#f3e8ea", borderRadius: 99, height: 9 }}>
                      <Box sx={{
                        width: `${s.percent}%`, height: 9, borderRadius: 99, bgcolor: color,
                        transition: "width .6s",
                      }} />
                    </Box>
                    {s.children && s.children.length > 0 && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.3 }}>
                        {fa(s.children.length)} زیرمقیاس
                      </Typography>
                    )}
                  </Box>
                );
              })}
            </Stack>
          </Box>
        </Paper>
      ) : topCount > 0 ? (
        <Paper sx={{ p: 2, borderRadius: 3 }}>
          <Typography variant="subtitle1" fontWeight={800} sx={{ mb: 1.25 }}>مقیاس‌های آزمون</Typography>
          <Stack spacing={1.25}>
            {scales.map((s) => {
              const color = levelColor(s.direction, s.percent, s.color);
              return (
                <Box key={s.key}>
                  <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.4 }}>
                    <Typography variant="body2" fontWeight={700}>{s.title}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {fa(s.score)} از {fa(s.max)} · {fa(s.percent)}٪
                    </Typography>
                  </Stack>
                  <Box sx={{ bgcolor: "#f3e8ea", borderRadius: 99, height: 9 }}>
                    <Box sx={{ width: `${s.percent}%`, height: 9, borderRadius: 99, bgcolor: color, transition: "width .6s" }} />
                  </Box>
                </Box>
              );
            })}
          </Stack>
        </Paper>
      ) : null}

      {/* بخش‌های تفصیلی هر بعد */}
      {scales.map((s, i) => (
        <DomainSection key={s.key} s={s} index={i} />
      ))}
    </Stack>
  );
}
