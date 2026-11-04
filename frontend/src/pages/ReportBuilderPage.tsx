// فاز ۷۶ (v0.59.0) - گزارش‌ساز و داشبوردساز
//
// ساخت گزارش تجمیعی دلخواه از مجموعه‌داده‌های سامانه (نوبت، جلسه، پرونده،
// درخواست مشاوره، فروش، پرداخت، آزمون، ارزیابی، نظرات): انتخاب بازه،
// گروه‌بندی، سنجه و نوع نمودار + افزودن هر گزارش به «داشبورد من» (ذخیره در
// مرورگر کاربر) + خروجی CSV سازگار با Excel + چاپ.
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogContent, DialogTitle,
  FormControl, Grid, IconButton, InputLabel, MenuItem, Paper, Select, Stack,
  Table, TableBody, TableCell, TableHead, TableRow, TextField, Tooltip, Typography,
} from "@mui/material";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import AddCircleOutlineRoundedIcon from "@mui/icons-material/AddCircleOutlineRounded";
import PrintRoundedIcon from "@mui/icons-material/PrintRounded";
import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import HelpOutlineRoundedIcon from "@mui/icons-material/HelpOutlineRounded";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { errDetail } from "../api/client";
import {
  fetchReportDatasets, fetchReportQuery, reportCsvUrl,
} from "../api/reports";
import type { ReportDataset } from "../api/reports";
import { BarChart, ChartCard, DonutChart, TrendChart } from "../components/charts";

type ChartKind = "bar" | "pie" | "line";

interface SavedWidget {
  id: string;
  dataset: string;
  datasetTitle: string;
  group_by: string;
  groupTitle: string;
  metric: string;
  metricTitle: string;
  days: number;
  chart: ChartKind;
}

const WIDGETS_KEY = "rosepsy_report_widgets_v1";

function loadWidgets(): SavedWidget[] {
  try {
    const raw = localStorage.getItem(WIDGETS_KEY);
    return raw ? (JSON.parse(raw) as SavedWidget[]) : [];
  } catch {
    return [];
  }
}

/** برچسب خوانا برای کلیدهای روز/ماه (تقویم جلالی) و بقیه مقادیر */
function prettyKey(groupBy: string, key: string): string {
  if (groupBy === "day" && /^\d{4}-\d{2}-\d{2}$/.test(key)) {
    try {
      return new Intl.DateTimeFormat("fa-IR", { day: "numeric", month: "long" }).format(new Date(`${key}T00:00:00Z`));
    } catch { /* همان کلید */ }
  }
  if (groupBy === "month" && /^\d{4}-\d{2}$/.test(key)) {
    try {
      return new Intl.DateTimeFormat("fa-IR", { month: "long", year: "numeric" }).format(new Date(`${key}-01T00:00:00Z`));
    } catch { /* همان کلید */ }
  }
  return key;
}

function WidgetChart({ chart, rows, color }: { chart: ChartKind; rows: { label: string; value: number }[]; color: string }) {
  if (chart === "pie") {
    return (
      <DonutChart
        title="جمع"
        items={rows.slice(0, 10).map((r, i) => ({
          label: r.label,
          value: r.value,
          color: ["#b04a5a", "#7a5c8a", "#2e7d32", "#1565c0", "#ed8c37", "#c62828", "#00838f", "#6d4c41", "#5c6bc0", "#c99a5b"][i % 10],
        }))}
      />
    );
  }
  if (chart === "line") {
    return (
      <TrendChart
        color={color}
        data={[...rows].reverse().map((r) => ({ date: r.label, count: r.value }))}
      />
    );
  }
  return <BarChart items={rows.slice(0, 12)} color={color} />;
}

export default function ReportBuilderPage() {
  const [days, setDays] = useState(30);
  const [datasetKey, setDatasetKey] = useState("");
  const [groupBy, setGroupBy] = useState("status");
  const [metric, setMetric] = useState("count");
  const [chart, setChart] = useState<ChartKind>("bar");
  const [statusFilter, setStatusFilter] = useState("");
  const [widgets, setWidgets] = useState<SavedWidget[]>(() => loadWidgets());
  const [saveOpen, setSaveOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  const { data: datasetsData } = useQuery({
    queryKey: ["report-datasets"],
    queryFn: fetchReportDatasets,
  });
  const datasets: ReportDataset[] = datasetsData?.items ?? [];
  const ds = useMemo(
    () => datasets.find((d) => d.key === datasetKey) ?? null,
    [datasets, datasetKey],
  );

  // پیش‌فرض: اولین مجموعه‌داده پس از بارگذاری
  useEffect(() => {
    if (!datasetKey && datasets.length) {
      setDatasetKey(datasets[0].key);
      setGroupBy(datasets[0].dims[0]?.key ?? "status");
      setMetric(datasets[0].metrics[0]?.key ?? "count");
    }
  }, [datasets, datasetKey]);

  const params = useMemo(() => ({
    dataset: datasetKey,
    group_by: groupBy,
    metric,
    days,
    status: statusFilter.trim() || undefined,
  }), [datasetKey, groupBy, metric, days, statusFilter]);

  const { data: result, isLoading, error, isFetching } = useQuery({
    queryKey: ["report-query", params],
    queryFn: () => fetchReportQuery(params),
    enabled: !!datasetKey,
  });

  const rows = result?.rows ?? [];
  const csvHref = datasetKey ? reportCsvUrl(params) : undefined;

  const addWidget = () => {
    if (!ds || !result) return;
    const w: SavedWidget = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      dataset: ds.key,
      datasetTitle: ds.title,
      group_by: groupBy,
      groupTitle: result.group_by_title,
      metric,
      metricTitle: result.metric_title,
      days,
      chart,
    };
    const next = [w, ...widgets].slice(0, 12);
    setWidgets(next);
    localStorage.setItem(WIDGETS_KEY, JSON.stringify(next));
    setSaveOpen(false);
  };

  const removeWidget = (id: string) => {
    const next = widgets.filter((w) => w.id !== id);
    setWidgets(next);
    localStorage.setItem(WIDGETS_KEY, JSON.stringify(next));
  };

  const total = result?.total ?? 0;

  return (
    <Stack spacing={3}>
      {/* هدر */}
      <Paper sx={{ p: 3, borderRadius: 3, background: "linear-gradient(135deg,#5b4b8a 0%,#39457a 100%)", color: "#fff" }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
          <Box>
            <Typography variant="h5" fontWeight={800}>گزارش‌ساز و داشبورد</Typography>
            <Typography variant="body2" sx={{ opacity: 0.85, mt: 0.5 }}>
              هر ترکیب از داده‌ها را بسازید، نمودار بگیرید، خروجی Excel بگیرید و داشبورد شخصی خود را مونتاژ کنید
            </Typography>
          </Box>
          <Tooltip title="راهنمای گزارش‌ساز">
            <IconButton sx={{ color: "#fff" }} onClick={() => setHelpOpen(true)} aria-label="راهنما">
              <HelpOutlineRoundedIcon />
            </IconButton>
          </Tooltip>
        </Stack>
      </Paper>

      {error && <Alert severity="error">{errDetail(error)}</Alert>}

      {/* سازندهٔ گزارش */}
      <Paper sx={{ p: 2.5, borderRadius: 3 }}>
        <Stack direction="row" spacing={1} alignItems="center" mb={2}>
          <Box sx={{ width: 4, height: 18, borderRadius: 2, bgcolor: "primary.main" }} />
          <Typography variant="subtitle1" fontWeight={800}>ساخت گزارش جدید</Typography>
        </Stack>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}>
            <FormControl size="small" fullWidth>
              <InputLabel>مجموعه‌داده</InputLabel>
              <Select label="مجموعه‌داده" value={datasetKey}
                onChange={(e) => {
                  const d = datasets.find((x) => x.key === e.target.value);
                  setDatasetKey(e.target.value);
                  if (d) {
                    if (!d.dims.some((x) => x.key === groupBy)) setGroupBy(d.dims[0]?.key ?? "status");
                    if (!d.metrics.some((x) => x.key === metric)) setMetric(d.metrics[0]?.key ?? "count");
                  }
                }}>
                {datasets.map((d) => <MenuItem key={d.key} value={d.key}>{d.title}</MenuItem>)}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <FormControl size="small" fullWidth>
              <InputLabel>گروه‌بندی بر اساس</InputLabel>
              <Select label="گروه‌بندی بر اساس" value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
                {(ds?.dims ?? []).map((d) => <MenuItem key={d.key} value={d.key}>{d.title}</MenuItem>)}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <FormControl size="small" fullWidth>
              <InputLabel>سنجه</InputLabel>
              <Select label="سنجه" value={metric} onChange={(e) => setMetric(e.target.value)}>
                {(ds?.metrics ?? []).map((m) => <MenuItem key={m.key} value={m.key}>{m.title}</MenuItem>)}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <FormControl size="small" fullWidth>
              <InputLabel>نوع نمودار</InputLabel>
              <Select label="نوع نمودار" value={chart} onChange={(e) => setChart(e.target.value as ChartKind)}>
                <MenuItem value="bar">میله‌ای</MenuItem>
                <MenuItem value="pie">دایره‌ای (دونات)</MenuItem>
                <MenuItem value="line">روند خطی</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Stack direction="row" spacing={1} alignItems="center" justifyContent={{ xs: "flex-start", md: "flex-end" }}>
              <Tooltip title="خروجی CSV (Excel)">
                <span>
                  <IconButton component="a" href={csvHref} download aria-label="خروجی CSV" disabled={!csvHref}>
                    <DownloadRoundedIcon />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="چاپ / PDF">
                <IconButton onClick={() => window.print()} aria-label="چاپ">
                  <PrintRoundedIcon />
                </IconButton>
              </Tooltip>
              <Button variant="contained" size="small" startIcon={<AddCircleOutlineRoundedIcon />}
                onClick={() => setSaveOpen(true)} disabled={!result || rows.length === 0}>
                افزودن به داشبورد
              </Button>
            </Stack>
          </Grid>
        </Grid>

        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mt: 2 }}>
          <Typography variant="caption" color="text.secondary">بازه:</Typography>
          {[7, 30, 90, 365].map((d) => (
            <Chip key={d} size="small" clickable
              label={d === 365 ? "یک سال" : `${d.toLocaleString("fa-IR")} روز`}
              color={days === d ? "primary" : "default"}
              variant={days === d ? "filled" : "outlined"}
              onClick={() => setDays(d)} />
          ))}
          {(ds?.filters ?? []).includes("status") && (
            <TextField size="small" sx={{ width: 260 }}
              label="فیلتر وضعیت (اختیاری، با کاما)"
              placeholder="مثلاً: paid, pending"
              value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} />
          )}
          {isFetching && <CircularProgress size={18} />}
        </Stack>
      </Paper>

      {/* نتیجهٔ گزارش */}
      {ds && (
        <Grid container spacing={2}>
          <Grid item xs={12} md={8}>
            <ChartCard
              title={`${result?.title ?? ds.title} — گروه‌بندی: ${result?.group_by_title ?? ""}`}
              desc={`سنجه: ${result?.metric_title ?? ""}${statusFilter ? ` — فیلتر وضعیت: ${statusFilter}` : ""}`}
              accent="#5b4b8a"
            >
              {isLoading ? (
                <CircularProgress size={26} sx={{ mx: "auto", display: "block", my: 4 }} />
              ) : (
                <WidgetChart chart={chart} rows={rows} color="#5b4b8a" />
              )}
            </ChartCard>
          </Grid>
          <Grid item xs={12} md={4}>
            <ChartCard title="جدول نتایج" desc="ردیف‌های گزارش به ترتیب مقدار" accent="#c99a5b">
              {rows.length === 0 ? (
                <Typography variant="body2" color="text.secondary" py={3} textAlign="center">
                  داده‌ای در این بازه یافت نشد.
                </Typography>
              ) : (
                <Box sx={{ maxHeight: 260, overflow: "auto" }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>{result?.group_by_title}</TableCell>
                        <TableCell align="left">{result?.metric_title}</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {rows.map((r) => (
                        <TableRow key={r.key}>
                          <TableCell>{groupBy === "day" || groupBy === "month" ? prettyKey(groupBy, r.key) : r.label}</TableCell>
                          <TableCell align="left" sx={{ fontWeight: 700 }}>{r.value.toLocaleString("fa-IR")}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Box>
              )}
              <Stack direction="row" justifyContent="space-between" mt={1.5} px={1}>
                <Typography variant="body2" fontWeight={800}>جمع کل:</Typography>
                <Typography variant="body2" fontWeight={800} color="primary.main">{total.toLocaleString("fa-IR")}</Typography>
              </Stack>
            </ChartCard>
          </Grid>
        </Grid>
      )}

      {/* داشبورد من */}
      <Box>
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1.5} flexWrap="wrap" useFlexGap>
          <Stack direction="row" spacing={1} alignItems="center">
            <Box sx={{ width: 4, height: 18, borderRadius: 2, bgcolor: "#7a5c8a" }} />
            <Typography variant="subtitle1" fontWeight={800}>داشبورد من</Typography>
            <Chip size="small" label={`${widgets.length.toLocaleString("fa-IR")} ویجت`} variant="outlined" />
          </Stack>
          {widgets.length > 0 && (
            <Button size="small" color="inherit" onClick={() => { setWidgets([]); localStorage.removeItem(WIDGETS_KEY); }}>
              پاک‌کردن همه
            </Button>
          )}
        </Stack>
        {widgets.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 3, borderRadius: 3, textAlign: "center" }}>
            <Typography variant="body2" color="text.secondary">
              هنوز ویجتی ندارید — گزارشی بسازید و با «افزودن به داشبورد» اینجا ذخیره‌اش کنید. داشبورد شما در همین مرورگر نگه داشته می‌شود.
            </Typography>
          </Paper>
        ) : (
          <Grid container spacing={2}>
            {widgets.map((w) => (
              <WidgetCard key={w.id} widget={w} onRemove={() => removeWidget(w.id)} />
            ))}
          </Grid>
        )}
      </Box>

      {/* گفت‌وگوی ذخیره ویجت */}
      <Dialog open={saveOpen} onClose={() => setSaveOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>افزودن به داشبورد من</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" mb={2}>
            این ویجت با تنظیمات فعلی (مجموعه‌داده، گروه‌بندی، سنجه، بازه و نوع نمودار) به داشبورد شما اضافه می‌شود و هربار که این صفحه را باز کنید به‌روز نمایش داده می‌شود.
          </Typography>
          {result && (
            <Stack spacing={0.5} mb={2}>
              <Typography variant="caption">• مجموعه‌داده: {result.title}</Typography>
              <Typography variant="caption">• گروه‌بندی: {result.group_by_title}</Typography>
              <Typography variant="caption">• سنجه: {result.metric_title}</Typography>
              <Typography variant="caption">• بازه: {days.toLocaleString("fa-IR")} روز</Typography>
            </Stack>
          )}
          <Stack direction="row" spacing={1} justifyContent="flex-end">
            <Button onClick={() => setSaveOpen(false)}>انصراف</Button>
            <Button variant="contained" onClick={addWidget}>افزودن</Button>
          </Stack>
        </DialogContent>
      </Dialog>

      {/* راهنما */}
      <Dialog open={helpOpen} onClose={() => setHelpOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>راهنمای گزارش‌ساز</DialogTitle>
        <DialogContent>
          <Stack spacing={1.5} component="div">
            <Typography variant="body2"><b>۱. مجموعه‌داده:</b> موضوع گزارش — نوبت‌ها، جلسات، پرونده‌ها، درخواست‌های سایت، سفارش‌ها (فروش)، پرداخت‌ها، آزمون‌ها، ارزیابی‌ها و نظرات مشاوران.</Typography>
            <Typography variant="body2"><b>۲. گروه‌بندی:</b> تعیین می‌کند ردیف‌های گزارش بر چه اساسی دسته‌بندی شوند: وضعیت، مشاور، روز، ماه، درگاه پرداخت، نوع سفارش، امتیاز یا آزمون.</Typography>
            <Typography variant="body2"><b>۳. سنجه:</b> چیزی که اندازه می‌گیرید — تعداد، مبلغ (ریال) یا میانگین نمره.</Typography>
            <Typography variant="body2"><b>۴. بازه:</b> فقط داده‌های روزهای اخیر شمرده می‌شود.</Typography>
            <Typography variant="body2"><b>۵. داشبورد من:</b> با «افزودن به داشبورد» هر گزارش به‌صورت ویجت زنده ذخیره می‌شود و با بازکردن صفحه، با دادهٔ تازه نمایش داده می‌شود (ذخیره‌سازی در مرورگر شما).</Typography>
            <Typography variant="body2"><b>۶. خروجی:</b> دکمهٔ دانلود، همان گزارش را به CSV سازگار با Excel می‌دهد؛ دکمهٔ چاپ هم نسخهٔ کاغذی/PDF می‌سازد.</Typography>
            <Alert severity="info" sx={{ mt: 1 }}>گزارش‌ها تجمیعی و بی‌نام هستند؛ نام افراد یا محتوای بالینی در گزارش‌ها نمایش داده نمی‌شود (بند ۱۵ سند جامع).</Alert>
          </Stack>
        </DialogContent>
      </Dialog>
    </Stack>
  );
}

function WidgetCard({ widget, onRemove }: { widget: SavedWidget; onRemove: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["report-widget", widget.dataset, widget.group_by, widget.metric, widget.days],
    queryFn: () => fetchReportQuery({
      dataset: widget.dataset, group_by: widget.group_by, metric: widget.metric, days: widget.days,
    }),
    refetchInterval: 120_000, // تازه‌سازی هر ۲ دقیقه
  });

  const rows = (data?.rows ?? []).map((r) => ({
    label: widget.group_by === "day" || widget.group_by === "month" ? prettyKey(widget.group_by, r.key) : r.label,
    value: r.value,
  }));

  return (
    <Grid item xs={12} md={6}>
      <ChartCard
        title={`${widget.datasetTitle} — ${widget.groupTitle}`}
        desc={`سنجه: ${widget.metricTitle} — بازه: ${widget.days.toLocaleString("fa-IR")} روز`}
        accent="#7a5c8a"
      >
        {isLoading ? (
          <CircularProgress size={22} sx={{ mx: "auto", display: "block", my: 3 }} />
        ) : (
          <WidgetChart chart={widget.chart} rows={rows} color="#7a5c8a" />
        )}
        <Stack direction="row" justifyContent="space-between" alignItems="center" mt={1}>
          <Typography variant="caption" color="text.secondary">
            جمع: {(data?.total ?? 0).toLocaleString("fa-IR")}
          </Typography>
          <Tooltip title="حذف ویجت">
            <IconButton size="small" onClick={onRemove} aria-label="حذف ویجت">
              <CloseRoundedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      </ChartCard>
    </Grid>
  );
}
