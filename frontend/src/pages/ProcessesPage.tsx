import {
  Alert, Box, Card, CardActionArea, CardContent, Chip, CircularProgress, Stack, Typography,
} from "@mui/material";
import { useEffect, useMemo, useRef, useState } from "react";
import BpmnJS from "bpmn-js/lib/NavigatedViewer";
import type Canvas from "diagram-js/lib/core/Canvas";
import "bpmn-js/dist/assets/diagram-js.css";
import "bpmn-js/dist/assets/bpmn-js.css";

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

export default function ProcessesPage() {
  const [currentId, setCurrentId] = useState<string>(PROCESSES[0].id);
  const current = useMemo(() => PROCESSES.find((p) => p.id === currentId)!, [currentId]);

  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<BpmnJS | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ساخت viewer یک‌بار
  useEffect(() => {
    if (!containerRef.current) return;
    const viewer = new BpmnJS({ container: containerRef.current });
    viewerRef.current = viewer;
    return () => {
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  // بارگذاری نمودار جاری
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${import.meta.env.BASE_URL}processes/${current.file}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const xml = await res.text();
        await viewer.importXML(xml);
        if (cancelled) return;
        const canvas = viewer.get<Canvas>("canvas");
        canvas.zoom("fit-viewport");
      } catch {
        if (!cancelled) setError("بارگذاری نمودار فرایند ناموفق بود.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [current]);

  const zoom = (factor: number | "fit-viewport") => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const canvas = viewer.get<Canvas>("canvas");
    if (factor === "fit-viewport") canvas.zoom("fit-viewport");
    else canvas.zoom(canvas.zoom() * factor);
  };

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="h6" fontWeight={700}>فرایندهای سازمانی (BPMN)</Typography>
        <Typography variant="body2" color="text.secondary">
          نمایش فرایندهای خدمات مشاوره با استاندارد BPMN 2.0 — برای جابه‌جایی، نمودار را با ماوس بکشید؛
          برای بزرگ‌نمایی از دکمه‌ها یا اسکرول استفاده کنید.
        </Typography>
      </Box>

      {/* فهرست فرایندها */}
      <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "1fr 1fr" }} gap={1.5}>
        {PROCESSES.map((p) => {
          const active = p.id === currentId;
          return (
            <Card
              key={p.id}
              variant="outlined"
              sx={{
                borderColor: active ? "primary.main" : "divider",
                borderWidth: active ? 2 : 1,
              }}
            >
              <CardActionArea onClick={() => setCurrentId(p.id)}>
                <CardContent sx={{ py: 1.5 }}>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                    {p.code && <Chip size="small" color="primary" variant="outlined" label={p.code} />}
                    <Typography variant="subtitle2" fontWeight={700}>{p.title}</Typography>
                  </Stack>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
                    {p.description}
                  </Typography>
                </CardContent>
              </CardActionArea>
            </Card>
          );
        })}
      </Box>

      {/* نمایشگر */}
      <Box sx={{ position: "relative", border: 1, borderColor: "divider", borderRadius: 1, overflow: "hidden" }}>
        <Box
          sx={{
            position: "absolute", top: 8, left: 8, zIndex: 2,
            display: "flex", gap: 0.5, bgcolor: "background.paper", borderRadius: 1, p: 0.5,
            boxShadow: 1,
          }}
        >
          <Chip size="small" label="＋" onClick={() => zoom(1.2)} />
          <Chip size="small" label="－" onClick={() => zoom(1 / 1.2)} />
          <Chip size="small" label="اندازه صفحه" onClick={() => zoom("fit-viewport")} />
        </Box>
        {loading && (
          <Box sx={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", zIndex: 1 }}>
            <CircularProgress />
          </Box>
        )}
        {error && (
          <Alert severity="error" sx={{ position: "absolute", top: 8, right: 8, zIndex: 2 }}>{error}</Alert>
        )}
        <div
          ref={containerRef}
          style={{ width: "100%", height: 560, backgroundColor: "#fafafa" }}
          dir="ltr"
        />
      </Box>

      <Typography variant="caption" color="text.secondary">
        فایل‌های نمودار در مسیر frontend/public/processes نگهداری می‌شوند و با استاندارد BPMN 2.0 در
        ابزارهایی مانند Camunda Modeler نیز قابل ویرایش هستند.
      </Typography>
    </Stack>
  );
}
