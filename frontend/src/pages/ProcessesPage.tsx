// فاز ۴۹ - B41: فرایندهای سازمانی نسخه‌دار — تعریف فرایند جدید، افزودن نسخه
// با «ثبت نسخه قبلی» (هر نسخه ردیف مستقل دارد)، انتشار/بایگانی نسخه و نمایشگر
// BPMN حرفه‌ای (فاز ۵۰). فهرست از بک‌اند می‌آید؛ بدون seed، کاتالوگ داخلی نمایش داده می‌شود.
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, Divider, FormControlLabel, GlobalStyles, IconButton, Paper,
  Stack, Switch, TextField, Tooltip, Typography,
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
import HistoryIcon from "@mui/icons-material/History";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import {
  ProcessDefinitionInfo, ProcessVersionInfo, archiveProcessVersion, createProcess,
  createProcessVersion, fetchProcesses, fetchProcessVersionsXML, publishProcessVersion,
} from "../api/processes";
import { formatJalaliDateTime } from "../utils/jalali";

/** کاتالوگ داخلی — فقط وقتی بک‌اند خالی است نمایش داده می‌شود */
const BUILTIN = [
  { id: "builtin-overall", code: "RS-PR-00", title: "گردش کلی خدمات مشاوره", file: "process-00-overall.bpmn",
    description: "نقشه کلان: از تماس/درخواست تا پذیرش، تشکیل پرونده، ارزیابی، جلسات و بستن پرونده (کاتالوگ داخلی — برای نسخه‌داری از seed استفاده کنید)." },
  { id: "builtin-telephone", code: "RS-PS-01-01", title: "پذیرش اولیه مراجعان تلفنی", file: "process-01-telephone-intake.bpmn",
    description: "ثبت اطلاعات فردی، ارزیابی اولیه، تشخیص مورد حاد و تعیین مسیر (کاتالوگ داخلی)." },
  { id: "builtin-case-intake", code: "RS-PS-04-01", title: "پذیرش و تشکیل پرونده", file: "process-04-case-intake.bpmn",
    description: "تشکیل پرونده، رضایت‌نامه، تخصیص مشاور، ارزیابی، چرخه تأیید مسئول فنی (کاتالوگ داخلی)." },
  { id: "builtin-acute-case", code: "RS-PS-08-01", title: "ارزیابی و مدیریت مورد حاد / پر خطر", file: "process-08-acute-case.bpmn",
    description: "تعیین سطح فوریت و مسیرهای سطح ۱/۲/۳ تا مختومه‌سازی (کاتالوگ داخلی)." },
];

const LEGEND = [
  { label: "رویداد شروع/پایان", color: "#2e7d32" },
  { label: "فعالیت / وظیفه", color: "#b04a5a" },
  { label: "گیت‌وی تصمیم", color: "#ed8c37" },
  { label: "جریان توالی", color: "#7a5c8a" },
];

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

const VERSION_STATUS: Record<string, { label: string; color: "success" | "warning" | "default" }> = {
  published: { label: "منتشرشده", color: "success" },
  draft: { label: "پیش‌نویس", color: "warning" },
  archived: { label: "بایگانی", color: "default" },
};

export default function ProcessesPage() {
  const { user } = useAuth();
  const roles = user?.roles ?? [];
  const canManage = roles.includes("SYSTEM_ADMIN") || roles.includes("ORG_MANAGER");

  const [defs, setDefs] = useState<ProcessDefinitionInfo[] | null>(null);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [newOpen, setNewOpen] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  const loadDefs = async () => {
    try {
      const items = await fetchProcesses();
      setDefs(items);
      setCurrentId((prev) => prev ?? items[0]?.id ?? BUILTIN[0].id);
    } catch (e) {
      setError(errDetail(e));
      setDefs([]);
      setCurrentId((prev) => prev ?? BUILTIN[0].id);
    }
  };
  useEffect(() => { loadDefs(); }, []);

  const isBuiltin = (currentId ?? "").startsWith("builtin-");
  const currentDef = useMemo(
    () => defs?.find((d) => d.id === currentId) ?? null,
    [defs, currentId],
  );
  const currentBuiltin = isBuiltin ? BUILTIN.find((b) => b.id === currentId) ?? null : null;
  const currentVersion: ProcessVersionInfo | null = currentDef?.current_version ?? null;

  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<BpmnJS | null>(null);
  const [loading, setLoading] = useState(false);
  const [zoomPct, setZoomPct] = useState(100);
  const [fullscreen, setFullscreen] = useState(false);
  const [selected, setSelected] = useState<ElementInfo | null>(null);

  const syncZoom = () => {
    const canvas = viewerRef.current?.get<Canvas>("canvas");
    if (canvas) setZoomPct(Math.round(canvas.zoom() * 100));
  };

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

  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setFullscreen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fullscreen]);

  // بارگذاری XML نسخه جاری (بک‌اند یا کاتالوگ داخلی)
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !currentId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setSelected(null);
      try {
        let xml: string | undefined;
        if (currentDef?.current_version) {
          xml = (await fetchProcessVersionsXML(currentDef.current_version.id)).bpmn_xml;
        } else if (currentBuiltin) {
          const res = await fetch(`${import.meta.env.BASE_URL}processes/${currentBuiltin.file}`);
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          xml = await res.text();
        }
        if (!xml) throw new Error("no xml");
        await viewer.importXML(xml);
        if (cancelled) return;
        viewer.get<Canvas>("canvas").zoom("fit-viewport");
        syncZoom();
      } catch {
        if (!cancelled) setError("بارگذاری نمودار فرایند ناموفق بود.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentId, currentDef?.current_version?.id]);

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
        triggerDownload(new Blob([svg], { type: "image/svg+xml" }), `${currentId}.svg`);
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
            canvas2.toBlob((b) => { if (b) triggerDownload(b, `${currentId}.png`); }, "image/png");
          }
          URL.revokeObjectURL(url);
        };
        img.src = url;
      }
    } catch {
      setError("خروجی گرفتن از نمودار ناموفق بود.");
    }
  };

  const sidebarItem = (p: { id: string; code: string | null; title: string; versionLabel?: string }) => {
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
          {p.versionLabel && <Chip size="small" sx={{ height: 20, fontSize: 10 }} label={p.versionLabel} />}
          <Typography variant="subtitle2" fontWeight={800}>{p.title}</Typography>
        </Stack>
      </Paper>
    );
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
        <Typography variant="h5" fontWeight={800}>فرایندهای سازمانی (BPMN نسخه‌دار)</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          تعریف فرایند جدید، ثبت نسخه‌های جدید با حفظ نسخه‌های قبلی و انتشار نسخه فعال —
          نمودارها استاندارد BPMN 2.0 هستند و با ابزارهایی مانند Camunda Modeler قابل ویرایش‌اند.
        </Typography>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {okMsg && <Alert severity="success" onClose={() => setOkMsg(null)}>{okMsg}</Alert>}

      <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "300px 1fr" }} gap={2} alignItems="start">
        <Stack spacing={1.25}>
          {canManage && (
            <Button variant="contained" onClick={() => setNewOpen(true)}>+ فرایند جدید</Button>
          )}
          {defs === null && <CircularProgress size={26} sx={{ mx: "auto" }} />}
          {defs !== null && defs.length === 0 && (
            <Alert severity="info">فرایندی در سامانه ثبت نشده؛ کاتالوگ داخلی پایین نمایش داده می‌شود.</Alert>
          )}
          {(defs ?? []).map((d) => sidebarItem({
            id: d.id, code: d.code, title: d.title,
            versionLabel: d.current_version ? `نسخه ${d.current_version.version_number.toLocaleString("fa-IR")}` : "بدون نسخه منتشرشده",
          }))}
          {(defs === null || defs.length === 0) && BUILTIN.map((b) => sidebarItem({
            id: b.id, code: b.code, title: b.title,
          }))}

          {currentDef && canManage && (
            <Stack direction="row" spacing={1}>
              <Button variant="outlined" startIcon={<HistoryIcon />} onClick={() => setVersionsOpen(true)}>
                نسخه‌ها ({currentDef.versions.length.toLocaleString("fa-IR")})
              </Button>
            </Stack>
          )}

          <Paper variant="outlined" sx={{ p: 1.5 }}>
            <Typography variant="subtitle2" fontWeight={800} mb={1}>راهنمای نمادها</Typography>
            <Stack spacing={0.75}>
              {LEGEND.map((l) => (
                <Stack key={l.label} direction="row" spacing={1} alignItems="center">
                  <Box sx={{ width: 12, height: 12, borderRadius: "50%", bgcolor: l.color }} />
                  <Typography variant="caption">{l.label}</Typography>
                </Stack>
              ))}
            </Stack>
          </Paper>
        </Stack>

        <Stack spacing={1.5}>
          {viewerBox}
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap mb={0.5}>
              {(currentDef?.code ?? currentBuiltin?.code) && (
                <Chip size="small" color="primary" variant="outlined" label={currentDef?.code ?? currentBuiltin?.code} />
              )}
              {currentVersion && (
                <Chip size="small" color="success" label={`نسخه فعال: ${currentVersion.version_number.toLocaleString("fa-IR")}`} />
              )}
              <Typography variant="subtitle1" fontWeight={800}>
                {currentDef?.title ?? currentBuiltin?.title ?? "—"}
              </Typography>
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 2 }}>
              {currentDef?.description ?? currentBuiltin?.description ?? ""}
            </Typography>
          </Paper>
        </Stack>
      </Box>

      <NewProcessDialog
        open={newOpen}
        onClose={() => setNewOpen(false)}
        onSaved={(id) => {
          setNewOpen(false);
          setOkMsg("فرایند جدید ثبت شد");
          setError(null);
          loadDefs().then(() => setCurrentId(id));
        }}
        onError={(m) => setError(m)}
      />

      {currentDef && (
        <VersionsDialog
          def={currentDef}
          canManage={canManage}
          open={versionsOpen}
          onClose={() => setVersionsOpen(false)}
          onChanged={() => { loadDefs(); setOkMsg("نسخه‌ها به‌روز شد"); setError(null); }}
          onError={(m) => setError(m)}
          onPreview={(xml) => viewerRef.current?.importXML(xml).then(() => {
            viewerRef.current?.get<Canvas>("canvas").zoom("fit-viewport");
            syncZoom();
          }).catch(() => setError("پیش‌نمایش این XML ناموفق بود"))}
        />
      )}
    </Stack>
  );
}

/* ------------------------------ فرایند جدید ------------------------------ */

function NewProcessDialog({ open, onClose, onSaved, onError }: {
  open: boolean;
  onClose: () => void;
  onSaved: (id: string) => void;
  onError: (m: string) => void;
}) {
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [xml, setXml] = useState("");
  const [changelog, setChangelog] = useState("");
  const [publish, setPublish] = useState(true);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const pickFile = async (f: File | null) => {
    if (!f) return;
    setXml(await f.text());
  };

  const submit = async () => {
    setFormError(null);
    setBusy(true);
    try {
      const res = await createProcess({
        code: code.trim().toUpperCase(),
        title: title.trim(),
        description: description || undefined,
        bpmn_xml: xml,
        changelog: changelog || "نسخه اولیه",
        publish,
      });
      onSaved(res.id);
    } catch (e) {
      setFormError(errDetail(e));
      onError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>فرایند جدید (B41)</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {formError && <Alert severity="error">{formError}</Alert>}
          <Box display="grid" gap={2} gridTemplateColumns={{ xs: "1fr", sm: "1fr 1fr" }}>
            <TextField
              required label="کد فرایند *" value={code} onChange={(e) => setCode(e.target.value)}
              helperText="مثل RS-PR-02 — یکتا و حروف بزرگ"
              slotProps={{ htmlInput: { dir: "ltr" } }}
            />
            <TextField required label="عنوان فرایند *" value={title} onChange={(e) => setTitle(e.target.value)} />
          </Box>
          <TextField label="شرح" multiline minRows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Button variant="outlined" component="label">
              بارگذاری فایل .bpmn (XML استاندارد BPMN 2.0)
              <input type="file" accept=".bpmn,.xml,text/xml,application/xml" hidden
                onChange={(e) => pickFile(e.target.files?.[0] ?? null)} />
            </Button>
            {xml && <Chip size="small" color="success" label={`XML بارگذاری شد (${xml.length.toLocaleString("fa-IR")} کاراکتر)`} />}
          </Stack>
          <TextField
            label="یا XML را اینجا بچسبانید" multiline minRows={5} fullWidth
            value={xml} onChange={(e) => setXml(e.target.value)}
            slotProps={{ htmlInput: { dir: "ltr", style: { fontSize: 12 } } }}
          />
          <TextField label="توضیح تغییرات (چانج‌لاگ)" value={changelog} onChange={(e) => setChangelog(e.target.value)} />
          <FormControlLabel
            control={<Switch checked={publish} onChange={(e) => setPublish(e.target.checked)} />}
            label="انتشار فوری نسخه ۱ (در غیر این صورت پیش‌نویس می‌ماند)"
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" disabled={busy || !code.trim() || !title.trim() || xml.trim().length < 40} onClick={submit}>
          {busy ? "در حال ثبت…" : "ثبت فرایند"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/* ------------------------------ نسخه‌ها ------------------------------ */

function VersionsDialog({ def, canManage, open, onClose, onChanged, onError, onPreview }: {
  def: ProcessDefinitionInfo;
  canManage: boolean;
  open: boolean;
  onClose: () => void;
  onChanged: () => void;
  onError: (m: string) => void;
  onPreview: (xml: string) => void;
}) {
  const [newOpen, setNewOpen] = useState(false);
  const [xml, setXml] = useState("");
  const [changelog, setChangelog] = useState("");
  const [publish, setPublish] = useState(true);
  const [busy, setBusy] = useState(false);

  const nextVersionNo = (def.versions[0]?.version_number ?? 0) + 1;

  const submitVersion = async () => {
    setBusy(true);
    try {
      await createProcessVersion(def.id, {
        bpmn_xml: xml, changelog: changelog || `نسخه ${nextVersionNo}`, publish,
      });
      setNewOpen(false);
      setXml("");
      setChangelog("");
      onChanged();
    } catch (e) {
      onError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const act = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      onChanged();
    } catch (e) {
      onError(errDetail(e));
    }
  };

  const previewVersion = async (v: ProcessVersionInfo) => {
    try {
      const full = await fetchProcessVersionsXML(v.id);
      onPreview(full.bpmn_xml ?? "");
      onClose();
    } catch (e) {
      onError(errDetail(e));
    }
  };

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogTitle>نسخه‌های فرایند «{def.title}» — ثبت نسخه قبلی</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" mb={1.5}>
            هر نسخه ردیف مستقل دارد؛ انتشار نسخه جدید، نسخه منتشرشده قبلی را «بایگانی» می‌کند و
            نمونه‌های در جریان به نسخه خودشان ارجاع می‌مانند.
          </Typography>
          {canManage && (
            <Button variant="contained" size="small" onClick={() => setNewOpen(true)} sx={{ mb: 1.5 }}>
              + نسخه جدید (نسخه {nextVersionNo.toLocaleString("fa-IR")})
            </Button>
          )}
          <Stack spacing={1}>
            {def.versions.map((v) => {
              const st = VERSION_STATUS[v.status] ?? { label: v.status, color: "default" as const };
              return (
                <Paper key={v.id} variant="outlined" sx={{ p: 1.5 }}>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                    <Chip size="small" label={`نسخه ${v.version_number.toLocaleString("fa-IR")}`} sx={{ fontWeight: 800 }} />
                    <Chip size="small" color={st.color} label={st.label} />
                    {v.changelog && <Typography variant="body2">{v.changelog}</Typography>}
                    <Box flexGrow={1} />
                    {v.published_at && (
                      <Typography variant="caption" color="text.secondary">
                        انتشار: {formatJalaliDateTime(v.published_at)}
                      </Typography>
                    )}
                    <Button size="small" onClick={() => previewVersion(v)}>پیش‌نمایش</Button>
                    {canManage && v.status !== "published" && (
                      <Button size="small" color="success" onClick={() => act(() => publishProcessVersion(v.id))}>
                        انتشار
                      </Button>
                    )}
                    {canManage && v.status === "published" && (
                      <Button size="small" color="warning" onClick={() => act(() => archiveProcessVersion(v.id))}>
                        بایگانی
                      </Button>
                    )}
                  </Stack>
                </Paper>
              );
            })}
            {def.versions.length === 0 && (
              <Typography color="text.secondary">نسخه‌ای ثبت نشده است.</Typography>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>بستن</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={newOpen} onClose={() => setNewOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>نسخه جدید برای «{def.title}» (نسخه {nextVersionNo.toLocaleString("fa-IR")})</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Button variant="outlined" component="label">
                بارگذاری فایل .bpmn
                <input type="file" accept=".bpmn,.xml,text/xml,application/xml" hidden
                  onChange={async (e) => { const f = e.target.files?.[0]; if (f) setXml(await f.text()); }} />
              </Button>
              {xml && <Chip size="small" color="success" label={`XML بارگذاری شد (${xml.length.toLocaleString("fa-IR")} کاراکتر)`} />}
            </Stack>
            <TextField
              label="یا XML را اینجا بچسبانید" multiline minRows={6} fullWidth
              value={xml} onChange={(e) => setXml(e.target.value)}
              slotProps={{ htmlInput: { dir: "ltr", style: { fontSize: 12 } } }}
            />
            <TextField label="توضیح تغییرات" value={changelog} onChange={(e) => setChangelog(e.target.value)} />
            <FormControlLabel
              control={<Switch checked={publish} onChange={(e) => setPublish(e.target.checked)} />}
              label="انتشار فوری پس از ثبت (نسخه منتشرشده قبلی بایگانی می‌شود)"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNewOpen(false)}>انصراف</Button>
          <Button variant="contained" disabled={busy || xml.trim().length < 40} onClick={submitVersion}>
            {busy ? "در حال ثبت…" : "ثبت نسخه"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
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
