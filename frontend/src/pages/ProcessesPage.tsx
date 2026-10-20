// فاز ۵۰ - BPMN حرفه‌ای: نمایشگر بزرگ با تمام‌صفحه، خروجی SVG/PNG، اطلاعات عنصر،
// رنگ‌بندی سفارشی نمودار و راهنمای نمادها — bpmn-js NavigatedViewer
import {
  Alert, Box, Button, Chip, CircularProgress, Divider, IconButton, Paper, Stack,
  Tooltip, Typography, GlobalStyles,
} from "@mui/material";
import { useEffect, useMemo, useRef, useState } from "react";
import BpmnJS from "bpmn-js/lib/NavigatedViewer";
import type Canvas from "diagram-js/lib/core/Canvas";
import AddRoundedIcon from "@mui/icons-material/AddRounded";
import RemoveRoundedIcon from "@mui/icons-material/RemoveRounded";
import CenterFocusStrongRoundedIcon from "@mui/icons-material/CenterFocusStrongRounded";
import FullscreenRoundedIcon from "@mui/icons-material/FullscreenRounded";
import FullscreenExitRoundedIcon from "@mui/icons-material/FullscreenExitRounded";
import FileDownloadRoundedIcon from "@mui/icons-material/FileDownloadRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import { ChartCard } from "../components/charts";

interface ProcessInfo {
  id: string;
  file: string;
  code: string | null;
  title: string;
  description: string;
}

/** کاتالوگ فرایندهای سازمانی — فایل‌های XML از public/processes بارگذاری می‌شوند */
const PROCESSES: ProcessInfo[] = [
  {
    id: "overall",
    file: "process-00-overall.bpmn",
    code: null,
    title: "گردش کلی خدمات مشاوره",
    description:
      "نقشه کلان: از تماس/درخواست تا پذیرش تلفنی، تشکیل پرونده، ارزیابی تخصصی، جلسات درمانی و بستن پرونده — و انشعاب فرایند مورد حاد در صورت شناسایی خطر.",
  },
  {
    id: "telephone",
    file: "process-01-telephone-intake.bpmn",
    code: "RS-PS-01-01",
    title: "پذیرش اولیه مراجعان تلفنی",
    description:
      "ثبت اطلاعات فردی مراجع تلفنی، ارزیابی اولیه موضوع مراجعه، تشخیص مورد حاد و تعیین مسیر (پذیرش حضوری، اطلاع‌رسانی یا تماس مجدد) با بازبینی نظارت حرفه‌ای.",
  },
  {
    id: "case-intake",
    file: "process-04-case-intake.bpmn",
    code: "RS-PS-04-01",
    title: "پذیرش و تشکیل پرونده",
    description:
      "تشکیل پرونده، رضایت‌نامه آگاهانه، تخصیص مشاور، ارزیابی تخصصی و MSE، چرخه نهایی‌سازی/تأیید مسئول فنی (با برگشت برای اصلاح)، طرح درمان و جلسات تا بستن پرونده.",
  },
  {
    id: "acute-case",
    file: "process-08-acute-case.bpmn",
    code: "RS-PS-08-01",
    title: "ارزیابی و مدیریت مورد حاد / پر خطر",
    description:
      "ثبت فرم مورد حاد و تعیین سطح فوریت؛ مسیر سطح ۱ (پایش دوره‌ای)، سطح ۲ (ارجاع برنامه‌ریزی‌شده) و سطح ۳ (اقدام فوری و ارجاع اورژانسی)؛ ثبت نتیجه پذیرش مقصد، پیگیری و مختومه‌سازی.",
  },
];

const LEGEND = [
  { label: "رویداد شروع/پایان", color: "#2e7d32" },
  { label: "فعالیت / وظیفه", color: "#b04a5a" },
  { label: "گیت‌وی تصمیم", color: "#ed8c37" },
  { label: "جریان توالی", color: "#7a5c8a" },
];

/** استایل سفارشی diagram-js — پالت رزی، فونت سامانه و پس‌زمینه شبکه‌ای */
const BPMN_STYLES = (
  <GlobalStyles
    styles={{
      ".bpmn-viewer .djs-container": {
        background: "radial-gradient(circle at 1px 1px, #e9dadd 1px, transparent 0) !important",
        backgroundSize: "22px 22px !important",
        backgroundColor: "#fdfbfc !important",
      },
      ".bpmn-viewer .djs-element .djs-visual > text, .bpmn-viewer .djs-label": {
        fontFamily: "Vazirmatn, Tahoma, sans-serif !important",
        fill: "#4a3238 !important",
      },
      ".bpmn-viewer .djs-shape .djs-visual > rect": {
        stroke: "#b04a5a !important",
        strokeWidth: "1.6px !important",
      },
      ".bpmn-viewer .djs-shape .djs-visual > circle": {
        stroke: "#2e7d32 !important",
        strokeWidth: "1.8px !important",
      },
      ".bpmn-viewer .djs-shape .djs-visual > polygon": {
        stroke: "#ed8c37 !important",
        strokeWidth: "1.8px !important",
        fill: "#fff8ef !important",
      },
      ".bpmn-viewer .djs-shape:hover .djs-visual > rect, .bpmn-viewer .selected .djs-visual > rect": {
        stroke: "#7a2b38 !important",
        strokeWidth: "2.2px !important",
      },
      ".bpmn-viewer .djs-connection .djs-visual > path": {
        stroke: "#9c6b74 !important",
        strokeWidth: "1.6px !important",
      },
      ".bpmn-viewer .djs-element.selected .djs-outline": { stroke: "#7a2b38 !important" },
    }}
  />
);

interface ElementInfo { name: string; type: string }

export default function ProcessesPage() {
  const [currentId, setCurrentId] = useState<string>(PROCESSES[0].id);
  const current = useMemo(() => PROCESSES.find((p) => p.id === currentId)!, [currentId]);

  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<BpmnJS | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zoomPct, setZoomPct] = useState(100);
  const [fullscreen, setFullscreen] = useState(false);
  const [selected, setSelected] = useState<ElementInfo | null>(null);

  const syncZoom = () => {
    const canvas = viewerRef.current?.get<Canvas>("canvas");
    if (canvas) setZoomPct(Math.round(canvas.zoom() * 100));
  };

  // ساخت viewer یک‌بار + کلیک عنصر
  useEffect(() => {
    if (!containerRef.current) return;
    const viewer = new BpmnJS({ container: containerRef.current });
    viewerRef.current = viewer;
    try {
      viewer.on("element.click", (ev: unknown) => {
        const el = (ev as { element?: { businessObject?: { name?: string; $type?: string }; type?: string } }).element;
        if (el) {
          const bo = el.businessObject ?? {};
          setSelected({
            name: bo.name || "—",
            type: (bo.$type || el.type || "").replace("bpmn:", ""),
          });
        }
      });
    } catch { /* رویداد حیاتی نیست */ }
    return () => {
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  // ESC برای خروج از تمام‌صفحه
  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setFullscreen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fullscreen]);

  // بارگذاری نمودار جاری
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      setSelected(null);
      try {
        const res = await fetch(`${import.meta.env.BASE_URL}processes/${current.file}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const xml = await res.text();
        await viewer.importXML(xml);
        if (cancelled) return;
        const canvas = viewer.get<Canvas>("canvas");
        canvas.zoom("fit-viewport");
        syncZoom();
      } catch {
        if (!cancelled) setError("بارگذاری نمودار فرایند ناموفق بود.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [current]);

  const zoom = (factor: number | "fit-viewport") => {
    const canvas = viewerRef.current?.get<Canvas>("canvas");
    if (!canvas) return;
    if (factor === "fit-viewport") canvas.zoom("fit-viewport");
    else canvas.zoom(canvas.zoom() * factor);
    syncZoom();
  };

  const download = async (kind: "svg" | "png") => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    try {
      if (kind === "svg") {
        const { svg } = await viewer.saveSVG();
        triggerDownload(new Blob([svg], { type: "image/svg+xml" }), `${current.id}.svg`);
      } else {
        const { svg } = await viewer.saveSVG();
        const img = new Image();
        const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        img.onload = () => {
          const canvas2 = document.createElement("canvas");
          canvas2.width = (img.width || 1600) * 2;
          canvas2.height = (img.height || 900) * 2;
          const ctx = canvas2.getContext("2d");
          if (ctx) {
            ctx.fillStyle = "#ffffff";
            ctx.fillRect(0, 0, canvas2.width, canvas2.height);
            ctx.drawImage(img, 0, 0, canvas2.width, canvas2.height);
            canvas2.toBlob((b) => { if (b) triggerDownload(b, `${current.id}.png`); }, "image/png");
          }
          URL.revokeObjectURL(url);
        };
        img.src = url;
      }
    } catch {
      setError("خروجی گرفتن از نمودار ناموفق بود.");
    }
  };

  const viewerBox = (
    <Box
      sx={{
        position: "relative",
        border: "1px solid #ece2e4",
        borderRadius: 2,
        overflow: "hidden",
        bgcolor: "#fff",
        ...(fullscreen
          ? { position: "fixed", inset: 0, zIndex: 1300, borderRadius: 0, border: 0 }
          : {}),
      }}
    >
      {/* نوار ابزار */}
      <Stack
        direction="row"
        alignItems="center"
        spacing={0.5}
        sx={{
          px: 1, py: 0.75, bgcolor: "background.paper",
          borderBottom: "1px solid #f0e4e6", flexWrap: "wrap", gap: 0.5,
        }}
      >
        <Tooltip title="کوچک‌نمایی">
          <IconButton size="small" onClick={() => zoom(1 / 1.2)}><RemoveRoundedIcon fontSize="small" /></IconButton>
        </Tooltip>
        <Chip size="small" label={`${zoomPct.toLocaleString("fa-IR")}٪`} sx={{ minWidth: 58, fontWeight: 700 }} />
        <Tooltip title="بزرگ‌نمایی">
          <IconButton size="small" onClick={() => zoom(1.2)}><AddRoundedIcon fontSize="small" /></IconButton>
        </Tooltip>
        <Tooltip title="اندازه صفحه">
          <IconButton size="small" onClick={() => zoom("fit-viewport")}><CenterFocusStrongRoundedIcon fontSize="small" /></IconButton>
        </Tooltip>
        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
        <Tooltip title="خروجی SVG">
          <IconButton size="small" onClick={() => download("svg")}><FileDownloadRoundedIcon fontSize="small" /></IconButton>
        </Tooltip>
        <Button size="small" onClick={() => download("png")}>خروجی PNG</Button>
        <Box flexGrow={1} />
        {selected && (
          <Chip
            size="small" color="primary" variant="outlined" deleteIcon={<CloseRoundedIcon />}
            onDelete={() => setSelected(null)}
            label={`${selected.name} — ${selected.type}`}
            sx={{ maxWidth: 340 }}
          />
        )}
        <Tooltip title={fullscreen ? "خروج از تمام‌صفحه (Esc)" : "نمایش تمام‌صفحه"}>
          <IconButton size="small" onClick={() => setFullscreen((s) => !s)}>
            {fullscreen ? <FullscreenExitRoundedIcon fontSize="small" /> : <FullscreenRoundedIcon fontSize="small" />}
          </IconButton>
        </Tooltip>
      </Stack>

      {loading && (
        <Box sx={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", zIndex: 2 }}>
          <CircularProgress />
        </Box>
      )}
      {error && <Alert severity="error" sx={{ position: "absolute", top: 8, left: 8, zIndex: 2 }}>{error}</Alert>}
      <div
        ref={containerRef}
        className="bpmn-viewer"
        style={{
          width: "100%",
          height: fullscreen ? "calc(100vh - 46px)" : 580,
          backgroundColor: "#fdfbfc",
        }}
        dir="ltr"
      />
    </Box>
  );

  return (
    <Stack spacing={2.5}>
      {BPMN_STYLES}
      <Box>
        <Typography variant="h5" fontWeight={800}>فرایندهای سازمانی (BPMN)</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          نمودارهای استاندارد BPMN 2.0 — جابه‌جایی با کشیدن ماوس، بزرگ‌نمایی با اسکرول یا دکمه‌ها،
          کلیک روی هر عنصر برای دیدن نام و نوع آن، و خروجی SVG/PNG برای گزارش‌ها.
        </Typography>
      </Box>

      {/* چیدمان دو ستونه: فهرست فرایندها + نمایشگر */}
      <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "300px 1fr" }} gap={2} alignItems="start">
        <Stack spacing={1.25}>
          {PROCESSES.map((p) => {
            const active = p.id === currentId;
            return (
              <Paper
                key={p.id}
                variant="outlined"
                onClick={() => setCurrentId(p.id)}
                sx={{
                  p: 1.5, cursor: "pointer", transition: "all .15s",
                  borderColor: active ? "primary.main" : "#ece2e4",
                  borderWidth: active ? 2 : 1,
                  bgcolor: active ? "#fdf3f4" : "#fff",
                  "&:hover": { boxShadow: 2 },
                }}
              >
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                  {p.code && <Chip size="small" color="primary" variant="outlined" sx={{ height: 20, fontSize: 10 }} label={p.code} />}
                  <Typography variant="subtitle2" fontWeight={800}>{p.title}</Typography>
                </Stack>
              </Paper>
            );
          })}
          <ChartCard title="راهنمای نمادها" accent="#7a5c8a">
            <Stack spacing={0.75}>
              {LEGEND.map((l) => (
                <Stack key={l.label} direction="row" spacing={1} alignItems="center">
                  <Box sx={{ width: 12, height: 12, borderRadius: "50%", bgcolor: l.color }} />
                  <Typography variant="caption">{l.label}</Typography>
                </Stack>
              ))}
            </Stack>
          </ChartCard>
        </Stack>

        <Stack spacing={1.5}>
          {viewerBox}
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap mb={0.5}>
              {current.code && <Chip size="small" color="primary" variant="outlined" label={current.code} />}
              <Typography variant="subtitle1" fontWeight={800}>{current.title}</Typography>
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 2 }}>
              {current.description}
            </Typography>
          </Paper>
          <Typography variant="caption" color="text.secondary">
            فایل‌های نمودار در مسیر frontend/public/processes نگهداری می‌شوند و با استاندارد BPMN 2.0 در
            ابزارهایی مانند Camunda Modeler نیز قابل ویرایش هستند.
          </Typography>
        </Stack>
      </Box>
    </Stack>
  );
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
