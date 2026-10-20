// فاز ۴۸ - نمودارهای سبک SVG بدون وابستگی جدید: روند (خط/ناحیه)، دونات و میله افقی
// هم‌راستا با پالت رزی؛ RTL-آگاه؛ با تولتیپ هاور
import { Box, Paper, Stack, Typography } from "@mui/material";
import { useMemo, useState } from "react";

export interface TrendPoint { date: string; count: number }

/** تبدیل تاریخ ISO به نمایش جلالی خوانا (ماه/روز) */
function faDay(iso: string): string {
  try {
    return new Intl.DateTimeFormat("fa-IR", { month: "short", day: "numeric" }).format(new Date(iso));
  } catch {
    return iso.slice(5);
  }
}

export function TrendChart({
  data, color = "#b04a5a", height = 190, secondary,
}: {
  data: TrendPoint[];
  color?: string;
  height?: number;
  secondary?: { data: TrendPoint[]; color: string; label: string };
}) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 640, H = height, PL = 34, PR = 10, PT = 12, PB = 22;
  const n = data.length;
  const maxVal = Math.max(
    1,
    ...data.map((d) => d.count),
    ...(secondary?.data ?? []).map((d) => d.count),
  );
  const step = n > 1 ? (W - PL - PR) / (n - 1) : 0;
  const x = (i: number) => PL + i * step;
  const y = (v: number) => PT + (1 - v / maxVal) * (H - PT - PB);

  const path = (pts: TrendPoint[]) =>
    pts.map((d, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(d.count).toFixed(1)}`).join(" ");
  const area = (pts: TrendPoint[]) =>
    `${path(pts)} L ${x(n - 1).toFixed(1)} ${H - PB} L ${PL} ${H - PB} Z`;

  const gid = useMemo(() => `g${Math.random().toString(36).slice(2, 8)}`, []);

  if (!n) {
    return (
      <Typography variant="caption" color="text.secondary" display="block" py={4} textAlign="center">
        داده‌ای برای نمایش روند نیست.
      </Typography>
    );
  }

  return (
    <Box sx={{ position: "relative" }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H}
        onMouseLeave={() => setHover(null)}>
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.28} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        {/* خطوط راهنما */}
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line key={f} x1={PL} x2={W - PR} y1={y(maxVal * f)} y2={y(maxVal * f)}
            stroke="#f0e4e6" strokeWidth={1} strokeDasharray="3 4" />
        ))}
        <text x={PL - 6} y={y(maxVal) + 4} fontSize={10} fill="#a08990" textAnchor="end">{maxVal.toLocaleString("fa-IR")}</text>
        <text x={PL - 6} y={y(0) + 4} fontSize={10} fill="#a08990" textAnchor="end">0</text>

        <path d={area(data)} fill={`url(#${gid})`} />
        <path d={path(data)} fill="none" stroke={color} strokeWidth={2.2} strokeLinejoin="round" strokeLinecap="round" />
        {secondary && secondary.data.length === n && (
          <path d={path(secondary.data)} fill="none" stroke={secondary.color} strokeWidth={1.8}
            strokeDasharray="5 4" strokeLinejoin="round" />
        )}

        {/* نقطه‌ها + هاور */}
        {data.map((d, i) => (
          <g key={i}>
            {i % Math.ceil(n / 8) === 0 && (
              <text x={x(i)} y={H - 6} fontSize={10} fill="#a08990" textAnchor="middle">{faDay(d.date)}</text>
            )}
            <circle cx={x(i)} cy={y(d.count)} r={hover === i ? 4.5 : 2.4}
              fill={hover === i ? color : "#fff"} stroke={color} strokeWidth={1.6}
              style={{ transition: "r .1s" }} />
            <rect x={x(i) - step / 2} y={PT} width={Math.max(step, 8)} height={H - PT - PB}
              fill="transparent" onMouseEnter={() => setHover(i)} />
          </g>
        ))}
        {hover !== null && (
          <line x1={x(hover)} x2={x(hover)} y1={PT} y2={H - PB} stroke={color} strokeWidth={1} strokeOpacity={0.4} />
        )}
      </svg>
      {hover !== null && (
        <Box sx={{
          position: "absolute", top: 4, right: 44,
          bgcolor: "rgba(60,40,45,.92)", color: "#fff", borderRadius: 1.5, px: 1.25, py: 0.75,
          pointerEvents: "none", minWidth: 110,
        }}>
          <Typography variant="caption" display="block">{faDay(data[hover].date)}</Typography>
          <Typography variant="body2" fontWeight={800}>
            {data[hover].count.toLocaleString("fa-IR")}
            {secondary && secondary.data[hover] && (
              <span style={{ opacity: 0.75, fontWeight: 600 }}> — {secondary.label}: {secondary.data[hover].count.toLocaleString("fa-IR")}</span>
            )}
          </Typography>
        </Box>
      )}
    </Box>
  );
}

/** دونات با لجند — برای توزیع وضعیت‌ها */
export function DonutChart({
  items, size = 168, title,
}: {
  items: { label: string; value: number; color: string }[];
  size?: number;
  title?: string;
}) {
  const total = items.reduce((a, b) => a + b.value, 0);
  const R = size / 2, r = R * 0.62, cx = R, cy = R;
  let angle = -Math.PI / 2;
  const segs = items.filter((i) => i.value > 0).map((it) => {
    const frac = total > 0 ? it.value / total : 0;
    const a0 = angle, a1 = angle + frac * Math.PI * 2;
    angle = a1;
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const p0 = { x: cx + r * Math.cos(a0), y: cy + r * Math.sin(a0) };
    const p1 = { x: cx + r * Math.cos(a1), y: cy + r * Math.sin(a1) };
    const p2 = { x: cx + R * Math.cos(a1), y: cy + R * Math.sin(a1) };
    const p3 = { x: cx + R * Math.cos(a0), y: cy + R * Math.sin(a0) };
    if (frac >= 0.999) {
      return { d: `M ${cx - R} ${cy} A ${R} ${R} 0 1 1 ${cx + R} ${cy} A ${R} ${R} 0 1 1 ${cx - R} ${cy} M ${cx - r} ${cy} A ${r} ${r} 0 1 0 ${cx + r} ${cy} A ${r} ${r} 0 1 0 ${cx - r} ${cy}`, color: it.color, label: it.label, value: it.value };
    }
    return { d: `M ${p0.x} ${p0.y} A ${r} ${r} 0 ${large} 1 ${p1.x} ${p1.y} L ${p2.x} ${p2.y} A ${R} ${R} 0 ${large} 0 ${p3.x} ${p3.y} Z`, color: it.color, label: it.label, value: it.value };
  });

  return (
    <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap>
      <Box sx={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
        <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
          {segs.length === 0 && <circle cx={cx} cy={cy} r={R} fill="#f3e8ea" />}
          {segs.map((s, i) => <path key={i} d={s.d} fill={s.color} stroke="#fff" strokeWidth={1.5} />)}
        </svg>
        <Box sx={{
          position: "absolute", inset: 0, display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", pointerEvents: "none",
        }}>
          <Typography variant="h5" fontWeight={800}>{total.toLocaleString("fa-IR")}</Typography>
          {title && <Typography variant="caption" color="text.secondary">{title}</Typography>}
        </Box>
      </Box>
      <Stack spacing={0.75} sx={{ minWidth: 150 }}>
        {items.map((it) => (
          <Stack key={it.label} direction="row" spacing={1} alignItems="center">
            <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: it.color, flexShrink: 0 }} />
            <Typography variant="caption" flexGrow={1}>{it.label}</Typography>
            <Typography variant="caption" fontWeight={800}>{it.value.toLocaleString("fa-IR")}</Typography>
          </Stack>
        ))}
      </Stack>
    </Stack>
  );
}

/** کارت نمودار یکپارچه برای داشبوردها */
export function ChartCard({ title, desc, children, accent }: {
  title: string; desc?: string; children: React.ReactNode; accent?: string;
}) {
  return (
    <Paper variant="outlined" sx={{ p: 2, height: "100%" }}>
      <Stack direction="row" alignItems="center" spacing={1} mb={1.5}>
        <Box sx={{ width: 4, height: 18, borderRadius: 2, bgcolor: accent ?? "primary.main" }} />
        <Typography variant="subtitle2" fontWeight={800}>{title}</Typography>
      </Stack>
      {desc && <Typography variant="caption" color="text.secondary" display="block" mb={1}>{desc}</Typography>}
      {children}
    </Paper>
  );
}
