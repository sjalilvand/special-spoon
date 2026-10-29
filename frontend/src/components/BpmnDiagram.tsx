// فاز ۵۹ - رندر زندهٔ دیاگرام BPMN با وضعیت واقعی هر عنصر:
// - شکل‌های استاندارد BPMN (رویداد شروع/پایان، فعالیت، گیت‌وی انحصاری/موازی/شمول)
// - رنگ وضعیت: انجام‌شده (سبز)، فعال (نارنجی + پالس)، ناموفق (قرمز)،
//   ردشده (خاکستری خط‌چین)، در انتظار (خاکستری روشن)
// - یال‌های طی‌شده پررنگ و گام فعال با پالس متحرک
// - کلیک روی هر عنصر: جزئیات رخداد (زمان، یادداشت)
// منبع مختصات: BPMNDI واقعی XML (اگر باشد)؛ در غیر این صورت چیدمان خودکار بک‌اند
import { useMemo, useState } from "react";
import { Box, Chip, IconButton, LinearProgress, Paper, Stack, Tooltip, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import RemoveIcon from "@mui/icons-material/Remove";
import CenterFocusStrongIcon from "@mui/icons-material/CenterFocusStrong";
import { formatJalaliDateTime } from "../utils/jalali";

export interface BpmnNode {
  id: string;
  name: string;
  kind: string;
  raw_type?: string;
  x: number; y: number; w: number; h: number;
}
export interface BpmnEdge {
  id: string; source: string; target: string;
  name?: string | null;
  waypoints: [number, number][];
  passed?: boolean;
  active?: boolean;
}
export interface BpmnState {
  status: string;
  occurred_at?: string | null;
  note?: string | null;
}

// فاز ۶۰: رنگ‌های پررنگ و اشباع — وضعیت هر عنصر یک‌نگاه از روی رنگ خود شکل
// خوانده می‌شود (سبز پررنگ = انجام‌شده، نارنجی پررنگ + پالس = گام فعال،
// قرمز پررنگ = ناموفق، طوسی روشن = در انتظار، طوسی تیره = ردشده)
const STATUS_COLORS: Record<string, { fill: string; stroke: string; label: string; text: string }> = {
  done: { fill: "#2e9e44", stroke: "#1b5e20", label: "انجام‌شده", text: "#ffffff" },
  active: { fill: "#ff9800", stroke: "#e65100", label: "گام فعال", text: "#ffffff" },
  pending: { fill: "#f1f3f5", stroke: "#90a4ae", label: "در انتظار", text: "#455a64" },
  skipped: { fill: "#cfd8dc", stroke: "#607d8b", label: "ردشده", text: "#37474f" },
  failed: { fill: "#e53935", stroke: "#b71c1c", label: "ناموفق", text: "#ffffff" },
};

const KIND_TITLES: Record<string, string> = {
  start: "رویداد شروع", end: "رویداد پایان", task: "فعالیت",
  subprocess: "زیرفرایند", gateway_exclusive: "گیت‌وی انحصاری",
  gateway_parallel: "گیت‌وی موازی", gateway_inclusive: "گیت‌وی شمول",
  gateway_event: "گیت‌وی رویدادمحور", intermediate: "رخداد میانی",
};

/** متن چندخطی فارسی — شکست خط ساده بر اساس طول تقریبی */
function wrapText(text: string, maxChars = 20): string[] {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > maxChars && cur) {
      lines.push(cur);
      cur = w;
    } else {
      cur = (cur + " " + w).trim();
    }
  }
  if (cur) lines.push(cur);
  return lines.slice(0, 4);
}

export default function BpmnDiagram({
  nodes, edges, states, height = 460,
}: {
  nodes: BpmnNode[];
  edges: BpmnEdge[];
  states: Record<string, BpmnState>;
  height?: number;
}) {
  const [zoom, setZoom] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);

  const bounds = useMemo(() => {
    if (nodes.length === 0) return { x: 0, y: 0, width: 800, height: 400 };
    const minX = Math.min(...nodes.map((n) => n.x)) - 50;
    const minY = Math.min(...nodes.map((n) => n.y)) - 50;
    const maxX = Math.max(...nodes.map((n) => n.x + n.w)) + 50;
    const maxY = Math.max(...nodes.map((n) => n.y + n.h)) + 50;
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
  }, [nodes]);

  const summary = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const n of nodes) {
      const st = states[n.id]?.status ?? "pending";
      counts[st] = (counts[st] ?? 0) + 1;
    }
    return counts;
  }, [nodes, states]);

  const selectedNode = selected ? nodes.find((n) => n.id === selected) ?? null : null;
  const selectedEvents = selected
    ? edges.filter((e) => e.source === selected || e.target === selected)
    : [];

  // فاز ۶۰: نوار پیشرفت — چند گام انجام شده، گام فعال کدام است
  const total = nodes.length;
  const doneCount = (summary["done"] ?? 0) + (summary["skipped"] ?? 0);
  const activeCount = summary["active"] ?? 0;
  const failedCount = summary["failed"] ?? 0;
  const activeNode = activeCount > 0
    ? nodes.find((n) => states[n.id]?.status === "active") ?? null
    : null;

  const vb = {
    x: bounds.x + (bounds.width * (1 - 1 / zoom)) / 2,
    y: bounds.y + (bounds.height * (1 - 1 / zoom)) / 2,
    w: bounds.width / zoom,
    h: bounds.height / zoom,
  };

  return (
    <Box>
      {/* نوار ابزار: راهنمای وضعیت + پیشرفت + بزرگ‌نمایی */}
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap mb={1}>
        {Object.entries(STATUS_COLORS).map(([k, v]) => (
          <Chip
            key={k} size="small"
            label={`${v.label}${summary[k] ? ` (${summary[k].toLocaleString("fa-IR")})` : ""}`}
            sx={{
              bgcolor: v.fill, color: v.text, borderColor: v.stroke,
              fontWeight: 800, border: "1.5px solid",
              boxShadow: k === "active" ? "0 0 8px rgba(255,152,0,.65)" : undefined,
            }}
          />
        ))}
        <Box flexGrow={1} />
        {total > 0 && (
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="caption" fontWeight={800} color="text.secondary">
              پیشرفت: {doneCount.toLocaleString("fa-IR")} از {total.toLocaleString("fa-IR")} گام
              {activeNode?.name ? ` — اکنون: ${activeNode.name}` : ""}
              {failedCount > 0 ? ` — ${failedCount.toLocaleString("fa-IR")} ناموفق` : ""}
            </Typography>
            <LinearProgress
              variant="determinate"
              value={total ? Math.round((doneCount / total) * 100) : 0}
              sx={{ width: 130, height: 9, borderRadius: 5, bgcolor: "#e8eef1" }}
            />
          </Stack>
        )}
        <Tooltip title="بزرگ‌نمایی">
          <IconButton size="small" onClick={() => setZoom((z) => Math.min(3, +(z + 0.25).toFixed(2)))}>
            <AddIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="کوچک‌نمایی">
          <IconButton size="small" onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))}>
            <RemoveIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="اندازهٔ اصلی">
          <IconButton size="small" onClick={() => setZoom(1)}>
            <CenterFocusStrongIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Typography variant="caption" color="text.secondary" sx={{ minWidth: 38, textAlign: "center" }} dir="ltr">
          {Math.round(zoom * 100)}٪
        </Typography>
      </Stack>

      <Box
        sx={{
          border: "1px solid #e5c9cf", borderRadius: 2, overflow: "auto",
          bgcolor: "#fffdfb", direction: "ltr",
          // فاز ۶۰: پالس قوی‌تر گام فعال + جریان متحرک روی یال فعال
          "& .bpmn-active-node": {
            animation: "bpmnPulse 1.3s ease-in-out infinite",
            "& rect, & circle, & polygon": { strokeWidth: 3.5 },
          },
          "@keyframes bpmnPulse": {
            "0%, 100%": { filter: "drop-shadow(0 0 3px rgba(230,81,0,.55))" },
            "50%": { filter: "drop-shadow(0 0 14px rgba(230,81,0,1))" },
          },
          "& .bpmn-edge-active": {
            strokeDasharray: "9 5",
            animation: "bpmnDash 0.8s linear infinite",
          },
          "@keyframes bpmnDash": {
            to: { strokeDashoffset: -14 },
          },
        }}
      >
        <svg
          width="100%"
          height={height}
          viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
          preserveAspectRatio="xMidYMid meet"
          style={{ minWidth: Math.max(640, bounds.width * 0.9), display: "block" }}
        >
          <defs>
            <marker id="bpmn-arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
              <path d="M0,0 L10,4 L0,8 Z" fill="#8a8a8a" />
            </marker>
            <marker id="bpmn-arrow-passed" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
              <path d="M0,0 L10,4 L0,8 Z" fill="#2e9e44" />
            </marker>
            <marker id="bpmn-arrow-active" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
              <path d="M0,0 L10,4 L0,8 Z" fill="#e65100" />
            </marker>
          </defs>

          {/* یال‌ها */}
          {edges.map((e) => {
            const pts = e.waypoints.length >= 2
              ? e.waypoints
              : orthogonalFallback(e, nodes);
            const color = e.active ? "#e65100" : e.passed ? "#2e9e44" : "#b9b9b9";
            const marker = e.active ? "url(#bpmn-arrow-active)" : e.passed ? "url(#bpmn-arrow-passed)" : "url(#bpmn-arrow)";
            return (
              <g key={`e-${e.id}`}>
                <polyline
                  className={e.active ? "bpmn-edge-active" : undefined}
                  points={pts.map((p) => p.join(",")).join(" ")}
                  fill="none" stroke={color} strokeWidth={e.active ? 3 : e.passed ? 2.6 : 1.6}
                  strokeLinecap="round"
                  markerEnd={marker}
                />
                {e.name && pts.length >= 2 && (
                  <text
                    x={(pts[0][0] + pts[pts.length - 1][0]) / 2}
                    y={(pts[0][1] + pts[pts.length - 1][1]) / 2 - 6}
                    fontSize={11} textAnchor="middle"
                    fill={e.passed || e.active ? "#444" : "#999"}
                    style={{ fontWeight: e.active || e.passed ? 700 : 400 }}
                  >
                    {e.name}
                  </text>
                )}
              </g>
            );
          })}

          {/* گره‌ها */}
          {nodes.map((n) => {
            const st = states[n.id] ?? { status: "pending" };
            const c = STATUS_COLORS[st.status] ?? STATUS_COLORS.pending;
            const isSel = selected === n.id;
            const isActive = st.status === "active";
            return (
              <g
                key={`n-${n.id}`}
                onClick={() => setSelected(isSel ? null : n.id)}
                style={{ cursor: "pointer" }}
                className={isActive ? "bpmn-active-node" : undefined}
              >
                <NodeShape node={n} fill={c.fill} stroke={c.stroke} symbolColor={c.text} selected={isSel} />
                {/* برچسب */}
                {n.name && n.kind !== "start" && n.kind !== "end" && (
                  <NodeLabel node={n} color={c.text} />
                )}
                {(n.kind === "start" || n.kind === "end") && n.name && (
                  <text
                    x={n.x + n.w / 2} y={n.y + n.h + 16}
                    fontSize={11} textAnchor="middle" fill="#555"
                    style={{ fontWeight: isActive ? 800 : 400 }}
                  >
                    {n.name.length > 22 ? n.name.slice(0, 21) + "…" : n.name}
                  </text>
                )}
                {/* نشان وضعیت روی فعالیت‌ها */}
                {(n.kind === "task" || n.kind === "subprocess") && (
                  <StatusBadge node={n} status={st.status} />
                )}
              </g>
            );
          })}
        </svg>
      </Box>

      {/* جزئیات عنصر انتخاب‌شده */}
      {selectedNode && (
        <Paper
          variant="outlined"
          sx={{ mt: 1, p: 1.5, bgcolor: "#fffdfb" }}
        >
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Typography variant="body2" fontWeight={800}>{selectedNode.name}</Typography>
            <Chip size="small" variant="outlined" label={KIND_TITLES[selectedNode.kind] ?? selectedNode.kind} />
            <Chip
              size="small"
              sx={{ bgcolor: STATUS_COLORS[states[selectedNode.id]?.status ?? "pending"].fill }}
              label={STATUS_COLORS[states[selectedNode.id]?.status ?? "pending"].label}
            />
            {states[selectedNode.id]?.occurred_at && (
              <Typography variant="caption" color="text.secondary">
                زمان ثبت: {formatJalaliDateTime(states[selectedNode.id].occurred_at)}
              </Typography>
            )}
            {states[selectedNode.id]?.note && (
              <Typography variant="caption" color="text.secondary">
                یادداشت: {states[selectedNode.id].note}
              </Typography>
            )}
            <Box flexGrow={1} />
            <Typography variant="caption" color="text.secondary" dir="ltr">
              {selectedNode.id}
            </Typography>
          </Stack>
          {selectedEvents.length > 0 && (
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
              اتصال‌ها: {selectedEvents.map((e) => `${e.source} → ${e.target}`).join(" | ")}
            </Typography>
          )}
        </Paper>
      )}
    </Box>
  );
}

/* ------------------------------ شکل‌های BPMN ------------------------------ */
function NodeShape({ node, fill, stroke, symbolColor, selected }: {
  node: BpmnNode; fill: string; stroke: string; symbolColor: string; selected: boolean;
}) {
  const cx = node.x + node.w / 2;
  const cy = node.y + node.h / 2;
  const sw = selected ? 3.5 : 2.2;
  if (node.kind === "start" || node.kind === "end" || node.kind === "intermediate") {
    const r = Math.max(node.w, node.h) / 2 || 18;
    return (
      <>
        <circle cx={cx} cy={cy} r={r} fill={fill} stroke={stroke} strokeWidth={sw} />
        {node.kind === "end" && <circle cx={cx} cy={cy} r={r - 5} fill="none" stroke={symbolColor} strokeWidth={2.5} />}
        {node.kind === "intermediate" && <circle cx={cx} cy={cy} r={r - 4} fill="none" stroke={symbolColor} strokeWidth={1.5} />}
      </>
    );
  }
  if (node.kind.startsWith("gateway")) {
    const s = Math.max(node.w, node.h) / 2 || 25;
    return (
      <>
        <polygon
          points={`${cx},${cy - s} ${cx + s},${cy} ${cx},${cy + s} ${cx - s},${cy}`}
          fill={fill} stroke={stroke} strokeWidth={sw}
        />
        {/* نماد داخل گیت‌وی — فاز ۶۰: با رنگ متن (سفید روی رنگ پررنگ) برای کنتراست */}
        {node.kind === "gateway_exclusive" && (
          <path
            d={`M${cx - s * 0.35},${cy - s * 0.35} L${cx + s * 0.35},${cy + s * 0.35} M${cx + s * 0.35},${cy - s * 0.35} L${cx - s * 0.35},${cy + s * 0.35}`}
            stroke={symbolColor} strokeWidth={2.8} fill="none"
          />
        )}
        {node.kind === "gateway_parallel" && (
          <path
            d={`M${cx},${cy - s * 0.42} L${cx},${cy + s * 0.42} M${cx - s * 0.42},${cy} L${cx + s * 0.42},${cy}`}
            stroke={symbolColor} strokeWidth={3} fill="none"
          />
        )}
        {node.kind === "gateway_inclusive" && <circle cx={cx} cy={cy} r={s * 0.35} fill="none" stroke={symbolColor} strokeWidth={2.4} />}
      </>
    );
  }
  // فعالیت / زیرفرایند — مستطیل گردگوشه
  return (
    <rect
      x={node.x} y={node.y} width={node.w} height={node.h} rx={10}
      fill={fill} stroke={stroke} strokeWidth={sw}
      strokeDasharray={node.kind === "subprocess" ? "6 3" : undefined}
    />
  );
}

function NodeLabel({ node, color }: { node: BpmnNode; color: string }) {
  const lines = wrapText(node.name, Math.max(12, Math.floor(node.w / 9)));
  const startY = node.y + node.h / 2 - (lines.length - 1) * 7 + 4;
  return (
    <>
      {lines.map((ln, i) => (
        <text
          key={i} x={node.x + node.w / 2} y={startY + i * 14}
          fontSize={11.5} textAnchor="middle" fill={color}
          style={{ fontWeight: 700, pointerEvents: "none" }}
        >
          {ln}
        </text>
      ))}
    </>
  );
}

function StatusBadge({ node, status }: { node: BpmnNode; status: string }) {
  const meta: Record<string, { ch: string; color: string }> = {
    done: { ch: "✓", color: "#1b5e20" },
    active: { ch: "●", color: "#e65100" },
    failed: { ch: "✕", color: "#b71c1c" },
    skipped: { ch: "»", color: "#455a64" },
    pending: { ch: "", color: "transparent" },
  };
  const m = meta[status] ?? meta.pending;
  if (!m.ch) return null;
  return (
    <g>
      <circle cx={node.x + node.w - 8} cy={node.y + 8} r={8} fill="#fff" stroke={m.color} strokeWidth={1.5} />
      <text x={node.x + node.w - 8} y={node.y + 12.5} fontSize={11} textAnchor="middle" fill={m.color} style={{ fontWeight: 800 }}>
        {m.ch}
      </text>
    </g>
  );
}

/** یال بدون waypoint کافی: مسیر عمودی/افقی ساده بین مرکز دو گره */
function orthogonalFallback(e: BpmnEdge, nodes: BpmnNode[]): [number, number][] {
  const s = nodes.find((n) => n.id === e.source);
  const t = nodes.find((n) => n.id === e.target);
  if (!s || !t) return [[0, 0], [0, 0]];
  const sc = [s.x + s.w / 2, s.y + s.h / 2];
  const tc = [t.x + t.w / 2, t.y + t.h / 2];
  if (Math.abs(sc[0] - tc[0]) > Math.abs(sc[1] - tc[1])) {
    return [[sc[0], sc[1]], [tc[0], sc[1]], [tc[0], tc[1]]];
  }
  return [[sc[0], sc[1]], [sc[0], tc[1]], [tc[0], tc[1]]];
}
