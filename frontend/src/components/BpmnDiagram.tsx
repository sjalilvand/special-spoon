// فاز ۵۹ - رندر زندهٔ دیاگرام BPMN با وضعیت واقعی هر عنصر:
// - شکل‌های استاندارد BPMN (رویداد شروع/پایان، فعالیت، گیت‌وی انحصاری/موازی/شمول)
// - رنگ وضعیت: انجام‌شده (سبز)، فعال (نارنجی + پالس)، ناموفق (قرمز)،
//   ردشده (خاکستری خط‌چین)، در انتظار (خاکستری روشن)
// - یال‌های طی‌شده پررنگ و گام فعال با پالس متحرک
// - کلیک روی هر عنصر: جزئیات رخداد (زمان، یادداشت)
// منبع مختصات: BPMNDI واقعی XML (اگر باشد)؛ در غیر این صورت چیدمان خودکار بک‌اند
import { useMemo, useState } from "react";
import { Box, Chip, IconButton, Paper, Stack, Tooltip, Typography } from "@mui/material";
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

const STATUS_COLORS: Record<string, { fill: string; stroke: string; label: string }> = {
  done: { fill: "#e3f4e4", stroke: "#2e7d32", label: "انجام‌شده" },
  active: { fill: "#ffeacc", stroke: "#ed8c37", label: "گام فعال" },
  pending: { fill: "#f4f4f4", stroke: "#9e9e9e", label: "در انتظار" },
  skipped: { fill: "#eeeeee", stroke: "#8a8a8a", label: "ردشده" },
  failed: { fill: "#fde2e1", stroke: "#c62828", label: "ناموفق" },
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

  const vb = {
    x: bounds.x + (bounds.width * (1 - 1 / zoom)) / 2,
    y: bounds.y + (bounds.height * (1 - 1 / zoom)) / 2,
    w: bounds.width / zoom,
    h: bounds.height / zoom,
  };

  return (
    <Box>
      {/* نوار ابزار: راهنمای وضعیت + بزرگ‌نمایی */}
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap mb={1}>
        {Object.entries(STATUS_COLORS).map(([k, v]) => (
          <Chip
            key={k} size="small" variant="outlined"
            label={`${v.label}${summary[k] ? ` (${summary[k].toLocaleString("fa-IR")})` : ""}`}
            sx={{ borderColor: v.stroke, color: v.stroke, bgcolor: v.fill }}
          />
        ))}
        <Box flexGrow={1} />
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
          "& .bpmn-active-node": { animation: "bpmnPulse 1.6s ease-in-out infinite" },
          "@keyframes bpmnPulse": {
            "0%, 100%": { filter: "drop-shadow(0 0 2px rgba(237,140,55,.55))" },
            "50%": { filter: "drop-shadow(0 0 9px rgba(237,140,55,.95))" },
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
              <path d="M0,0 L10,4 L0,8 Z" fill="#2e7d32" />
            </marker>
            <marker id="bpmn-arrow-active" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
              <path d="M0,0 L10,4 L0,8 Z" fill="#ed8c37" />
            </marker>
          </defs>

          {/* یال‌ها */}
          {edges.map((e) => {
            const pts = e.waypoints.length >= 2
              ? e.waypoints
              : orthogonalFallback(e, nodes);
            const color = e.active ? "#ed8c37" : e.passed ? "#2e7d32" : "#b9b9b9";
            const marker = e.active ? "url(#bpmn-arrow-active)" : e.passed ? "url(#bpmn-arrow-passed)" : "url(#bpmn-arrow)";
            return (
              <g key={`e-${e.id}`}>
                <polyline
                  points={pts.map((p) => p.join(",")).join(" ")}
                  fill="none" stroke={color} strokeWidth={e.active || e.passed ? 2.4 : 1.6}
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
            return (
              <g
                key={`n-${n.id}`}
                onClick={() => setSelected(isSel ? null : n.id)}
                style={{ cursor: "pointer" }}
                className={st.status === "active" ? "bpmn-active-node" : undefined}
              >
                <NodeShape node={n} fill={c.fill} stroke={c.stroke} selected={isSel} />
                {/* برچسب */}
                {n.name && n.kind !== "start" && n.kind !== "end" && (
                  <NodeLabel node={n} />
                )}
                {(n.kind === "start" || n.kind === "end") && n.name && (
                  <text
                    x={n.x + n.w / 2} y={n.y + n.h + 16}
                    fontSize={11} textAnchor="middle" fill="#555"
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
function NodeShape({ node, fill, stroke, selected }: {
  node: BpmnNode; fill: string; stroke: string; selected: boolean;
}) {
  const cx = node.x + node.w / 2;
  const cy = node.y + node.h / 2;
  const sw = selected ? 3 : 2;
  if (node.kind === "start" || node.kind === "end" || node.kind === "intermediate") {
    const r = Math.max(node.w, node.h) / 2 || 18;
    return (
      <>
        <circle cx={cx} cy={cy} r={r} fill={fill} stroke={stroke} strokeWidth={sw} />
        {node.kind === "end" && <circle cx={cx} cy={cy} r={r - 5} fill="none" stroke={stroke} strokeWidth={2.5} />}
        {node.kind === "intermediate" && <circle cx={cx} cy={cy} r={r - 4} fill="none" stroke={stroke} strokeWidth={1.5} />}
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
        {/* نماد داخل گیت‌وی */}
        {node.kind === "gateway_exclusive" && (
          <path
            d={`M${cx - s * 0.35},${cy - s * 0.35} L${cx + s * 0.35},${cy + s * 0.35} M${cx + s * 0.35},${cy - s * 0.35} L${cx - s * 0.35},${cy + s * 0.35}`}
            stroke={stroke} strokeWidth={2.4} fill="none"
          />
        )}
        {node.kind === "gateway_parallel" && (
          <path
            d={`M${cx},${cy - s * 0.42} L${cx},${cy + s * 0.42} M${cx - s * 0.42},${cy} L${cx + s * 0.42},${cy}`}
            stroke={stroke} strokeWidth={2.6} fill="none"
          />
        )}
        {node.kind === "gateway_inclusive" && <circle cx={cx} cy={cy} r={s * 0.35} fill="none" stroke={stroke} strokeWidth={2.2} />}
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

function NodeLabel({ node }: { node: BpmnNode }) {
  const lines = wrapText(node.name, Math.max(12, Math.floor(node.w / 9)));
  const startY = node.y + node.h / 2 - (lines.length - 1) * 7 + 4;
  return (
    <>
      {lines.map((ln, i) => (
        <text
          key={i} x={node.x + node.w / 2} y={startY + i * 14}
          fontSize={11.5} textAnchor="middle" fill="#333"
          style={{ fontWeight: 600, pointerEvents: "none" }}
        >
          {ln}
        </text>
      ))}
    </>
  );
}

function StatusBadge({ node, status }: { node: BpmnNode; status: string }) {
  const meta: Record<string, { ch: string; color: string }> = {
    done: { ch: "✓", color: "#2e7d32" },
    active: { ch: "●", color: "#ed8c37" },
    failed: { ch: "✕", color: "#c62828" },
    skipped: { ch: "»", color: "#8a8a8a" },
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
