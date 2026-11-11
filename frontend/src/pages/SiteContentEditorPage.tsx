// فاز ۸۴ — ویرایشگر صفحات عمومی سایت (مثل وردپرس)
//
// گردش کار ادمین:
// ۱) انتخاب صفحه از فهرست (خانه / روان‌درمانی / قوانین پرداخت)؛
// ۲) ویرایش فرمیِ بخش‌ها (عنوان‌ها، متن‌ها، کارت‌ها، فهرست‌ها، تصاویر متنی) +
//    تب «پیش‌نمایش» برای دیدن ساختار نهایی؛
// ۳) «ذخیرهٔ پیش‌نویس» → هیچ بازدیدکننده‌ای چیزی نمی‌بیند؛
// ۴) «انتشار» → سایت از همان لحظه سند جدید را می‌خواند (پس از بارگذاری صفحه).
// امنیت: متن‌های پیش‌فرض از backend (تولیدشده از site/src/content) می‌آید؛
// «بازنشانی» ردیف را حذف می‌کند و سایت به متن‌های پیش‌فرض کد برمی‌گردد.
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent,
  DialogContentText, DialogTitle, Divider, IconButton, LinearProgress, MenuItem, Paper,
  Select, Snackbar, Stack, Tab, Tabs, TextField, Tooltip, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { errDetail } from "../api/client";
import {
  SiteContentPageDetail,
  fetchSiteContentAdmin,
  fetchSiteContentPage,
  publishSiteContent,
  resetSiteContent,
  revertSiteContentDraft,
  saveSiteContentDraft,
} from "../api/siteContent";
import AddCircleOutlineRoundedIcon from "@mui/icons-material/AddCircleOutlineRounded";
import ArrowDownwardRoundedIcon from "@mui/icons-material/ArrowDownwardRounded";
import ArrowUpwardRoundedIcon from "@mui/icons-material/ArrowUpwardRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import HistoryRoundedIcon from "@mui/icons-material/HistoryRounded";
import OpenInNewRoundedIcon from "@mui/icons-material/OpenInNewRounded";
import PublishRoundedIcon from "@mui/icons-material/PublishRounded";
import RestartAltRoundedIcon from "@mui/icons-material/RestartAltRounded";
import SaveRoundedIcon from "@mui/icons-material/SaveRounded";
import VisibilityRoundedIcon from "@mui/icons-material/VisibilityRounded";

type Doc = Record<string, unknown>;

// برچسب‌های فارسی بخش‌ها/فیلدها — کلید ناشناخته = خود کلید
const FIELD_LABELS: Record<string, string> = {
  // صفحهٔ خانه (texts.ts)
  brand: "نام برند", brandSub: "زیرعنوان برند", topbar: "نوار بالای سایت",
  nav: "منوی ناوبری", hero: "اسلایدر اصلی", heroChips: "برچسب‌های اعتماد",
  servicesTitle: "عنوان خدمات", servicesSub: "زیرعنوان خدمات", services: "کارت‌های خدمات",
  featuresTitle: "عنوان مزایا", featuresSub: "زیرعنوان مزایا", features: "چرا ما (مزایا)",
  stepsTitle: "عنوان مسیر رزرو", stepsSub: "زیرعنوان مسیر رزرو", steps: "گام‌های رزرو",
  counselorsTitle: "عنوان مشاوران", counselorsSub: "زیرعنوان مشاوران",
  academyTitle: "عنوان آکادمی", academySub: "زیرعنوان آکادمی", academy: "کارت‌های آکادمی",
  articlesTitle: "عنوان مقالات", articlesSub: "زیرعنوان مقالات", articles: "کارت‌های مقالات",
  aboutTitle: "عنوان درباره ما", about: "متن‌های درباره ما",
  stats: "آمار (اعداد بزرگ)", testimonialsTitle: "عنوان روایت مراجعان",
  testimonialsSub: "زیرعنوان روایت مراجعان", consultTitle: "عنوان درخواست مشاوره",
  consultSub: "زیرعنوان درخواست مشاوره", topics: "موضوع‌های فرم مشاوره",
  slots: "بازه‌های زمانی فرم", faqTitle: "عنوان سوالات پرتکرار",
  faqSub: "زیرعنوان سوالات پرتکرار", faq: "سوالات پرتکرار",
  ctaBand: "نوار دعوت به اقدام", appDownload: "معرفی اپلیکیشن", footer: "فوتر (تماس)",
  // صفحهٔ روان‌درمانی
  intro: "متن معرفی", treatments: "روش‌های درمان", whyTitle: "عنوان چرا ما", whyUs: "دلایل انتخاب ما",
  // قوانین پرداخت
  subtitle: "زیرعنوان صفحه", summaryTitle: "عنوان خلاصه", summary: "متن خلاصهٔ مهم",
  sections: "بندهای قوانین", contactTitle: "عنوان تماس مالی", contact: "متن تماس مالی",
  footnote: "پانوشت صفحه",
  // فیلدهای تکراری آیتم‌ها
  title: "عنوان", sub: "زیرعنوان", cta: "متن دکمه", icon: "آیکن/اموجی", desc: "توضیح",
  label: "برچسب", emoji: "اموجی", tag: "برچسب دسته", read: "زمان مطالعه", q: "سؤال", a: "پاسخ",
  id: "شناسه لنگر (پرونده)", text: "متن", img: "تصویر (مسیر)", phone: "تلفن", address: "نشانی",
  hours: "ساعات کاری", points: "نکات", download: "متن دکمهٔ دانلود", qrHint: "راهنمای QR",
  qrSub: "زیرنویس QR", installNote: "یادداشت نصب", button: "متن دکمه", items: "موارد بند",
  n: "شماره/عدد",
};

function labelFor(key: string): string {
  return FIELD_LABELS[key] ?? key;
}

function isPlainObj(v: unknown): v is Doc {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function cloneDoc<T>(v: T): T {
  return JSON.parse(JSON.stringify(v)) as T;
}

const IMG_RE = /^\/.+\.(png|jpe?g|webp|svg|gif)$/i;

function looksLikeImagePath(v: string): boolean {
  return IMG_RE.test(v.trim());
}

/** جابه‌جایی عنصر آرایه برای دکمه‌های بالا/پایین */
function moveItem<T>(arr: T[], from: number, to: number): T[] {
  if (to < 0 || to >= arr.length) return arr;
  const out = [...arr];
  const [it] = out.splice(from, 1);
  out.splice(to, 0, it);
  return out;
}

// ---------------------------------------------------------------------------
// ویرایشگرهای مقدار
// ---------------------------------------------------------------------------

function StringField({
  label, value, onChange,
}: { label: string; value: string; onChange: (v: string) => void }) {
  const multiline = value.length > 60 || value.includes("\n");
  return (
    <Box>
      <TextField
        fullWidth size="small" label={label} value={value}
        multiline={multiline} rows={multiline ? 4 : 1}
        onChange={(e) => onChange(e.target.value)}
      />
      {looksLikeImagePath(value) && (
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.5 }}>
          <Box
            component="img" src={value} alt={label}
            sx={{ height: 56, borderRadius: 1, border: "1px solid", borderColor: "divider" }}
          />
          <Typography variant="caption" color="text.secondary">
            تصویر — مسیر فایل روی سرور یا URL کامل
          </Typography>
        </Stack>
      )}
    </Box>
  );
}

function NumberField({
  label, value, onChange,
}: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <TextField
      fullWidth size="small" type="number" label={label} value={value}
      onChange={(e) => {
        const n = Number(e.target.value);
        if (!Number.isNaN(n)) onChange(n);
      }}
    />
  );
}

function StringArrayEditor({
  label, value, onChange,
}: { label: string; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
        <Typography variant="body2" fontWeight={700}>{label}</Typography>
        <Chip size="small" label={`${value.length} مورد`} />
        <Button
          size="small" startIcon={<AddCircleOutlineRoundedIcon />}
          onClick={() => onChange([...value, ""])}
        >
          افزودن
        </Button>
      </Stack>
      <Stack spacing={0.5}>
        {value.map((it, i) => (
          <Stack key={i} direction="row" spacing={0.5} alignItems="flex-start">
            <TextField
              fullWidth size="small" multiline={it.length > 60} rows={it.length > 60 ? 2 : 1}
              value={it} sx={{ bgcolor: "background.paper" }}
              onChange={(e) => onChange(value.map((x, j) => (j === i ? e.target.value : x)))}
            />
            <Tooltip title="بالا"><span>
              <IconButton size="small" disabled={i === 0} onClick={() => onChange(moveItem(value, i, i - 1))}>
                <ArrowUpwardRoundedIcon fontSize="small" />
              </IconButton>
            </span></Tooltip>
            <Tooltip title="پایین"><span>
              <IconButton size="small" disabled={i === value.length - 1} onClick={() => onChange(moveItem(value, i, i + 1))}>
                <ArrowDownwardRoundedIcon fontSize="small" />
              </IconButton>
            </span></Tooltip>
            <Tooltip title="حذف"><span>
              <IconButton size="small" onClick={() => onChange(value.filter((_, j) => j !== i))}>
                <DeleteOutlineRoundedIcon fontSize="small" />
              </IconButton>
            </span></Tooltip>
          </Stack>
        ))}
        {value.length === 0 && (
          <Typography variant="caption" color="text.secondary">فهرست خالی است</Typography>
        )}
      </Stack>
    </Box>
  );
}

function JsonFallback({
  label, value, onChange,
}: { label: string; value: unknown; onChange: (v: unknown) => void }) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2));
  const [bad, setBad] = useState(false);
  useEffect(() => {
    setText(JSON.stringify(value, null, 2));
    setBad(false);
  }, [value]);
  return (
    <TextField
      fullWidth size="small" label={`${label} (JSON)`} value={text}
      multiline rows={6} error={bad}
      helperText={bad ? "JSON نامعتبر است" : "ساختار پیشرفته — با احتیاط ویرایش کنید"}
      onChange={(e) => {
        setText(e.target.value);
        try {
          onChange(JSON.parse(e.target.value));
          setBad(false);
        } catch {
          setBad(true);
        }
      }}
    />
  );
}

/** ویرایشگر آیتم‌های شیء‌دار (کارت‌های خدمات، گام‌ها، سوالات، بندها و …) */
function ItemListEditor({
  label, value, onChange,
}: { label: string; value: Doc[]; onChange: (v: Doc[]) => void }) {
  const itemKeys = useMemo(() => {
    const keys: string[] = [];
    for (const it of value) for (const k of Object.keys(it)) if (!keys.includes(k)) keys.push(k);
    return keys;
  }, [value]);
  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
        <Typography variant="body2" fontWeight={700}>{label}</Typography>
        <Chip size="small" label={`${value.length} مورد`} />
        <Button
          size="small" startIcon={<AddCircleOutlineRoundedIcon />}
          onClick={() => onChange([...value, cloneDoc(value[0] ?? {})])}
        >
          افزودن مشابه مورد اول
        </Button>
      </Stack>
      <Stack spacing={1}>
        {value.map((item, i) => (
          <Paper key={i} variant="outlined" sx={{ p: 1.5 }}>
            <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mb: 1 }}>
              <Chip size="small" label={`مورد ${i + 1}`} color="primary" variant="outlined" />
              <Box sx={{ flex: 1 }} />
              <Tooltip title="بالا"><span>
                <IconButton size="small" disabled={i === 0} onClick={() => onChange(moveItem(value, i, i - 1))}>
                  <ArrowUpwardRoundedIcon fontSize="small" />
                </IconButton>
              </span></Tooltip>
              <Tooltip title="پایین"><span>
                <IconButton size="small" disabled={i === value.length - 1} onClick={() => onChange(moveItem(value, i, i + 1))}>
                  <ArrowDownwardRoundedIcon fontSize="small" />
                </IconButton>
              </span></Tooltip>
              <Tooltip title="حذف"><span>
                <IconButton size="small" onClick={() => onChange(value.filter((_, j) => j !== i))}>
                  <DeleteOutlineRoundedIcon fontSize="small" />
                </IconButton>
              </span></Tooltip>
            </Stack>
            <Stack spacing={1}>
              {itemKeys.map((k) => (
                <ValueEditor
                  key={k} depth={2}
                  label={labelFor(k)} value={item[k] ?? ""}
                  onChange={(nv) => onChange(value.map((x, j) => (j === i ? { ...x, [k]: nv } : x)))}
                />
              ))}
            </Stack>
          </Paper>
        ))}
      </Stack>
    </Box>
  );
}

/** تشخیص نوع مقدار و انتخاب ویرایشگر مناسب */
function ValueEditor({
  label, value, onChange, depth,
}: { label: string; value: unknown; onChange: (v: unknown) => void; depth: number }) {
  if (typeof value === "string") return <StringField label={label} value={value} onChange={onChange} />;
  if (typeof value === "number") return <NumberField label={label} value={value} onChange={onChange} />;
  if (Array.isArray(value) && value.every((x) => typeof x === "string")) {
    return <StringArrayEditor label={label} value={value as string[]} onChange={onChange as (v: string[]) => void} />;
  }
  if (Array.isArray(value) && value.length > 0 && value.every((x) => isPlainObj(x))) {
    return <ItemListEditor label={label} value={value as Doc[]} onChange={onChange as (v: Doc[]) => void} />;
  }
  if (Array.isArray(value) && value.length === 0) {
    return <Typography variant="caption" color="text.secondary">{label}: فهرست خالی</Typography>;
  }
  if (isPlainObj(value) && depth < 2) {
    return (
      <Box>
        <Typography variant="body2" fontWeight={700} sx={{ mb: 0.5 }}>{label}</Typography>
        <Stack spacing={1} sx={{ pr: 1, borderRight: "2px solid", borderColor: "divider" }}>
          {Object.keys(value).map((k) => (
            <ValueEditor
              key={k} depth={depth + 1}
              label={labelFor(k)} value={value[k]}
              onChange={(nv) => onChange({ ...value, [k]: nv })}
            />
          ))}
        </Stack>
      </Box>
    );
  }
  return <JsonFallback label={label} value={value} onChange={onChange} />;
}

// ---------------------------------------------------------------------------
// پیش‌نمایش
// ---------------------------------------------------------------------------

function PreviewValue({ value }: { value: unknown }) {
  if (typeof value === "string") {
    return (
      <Typography variant={value.length <= 60 ? "subtitle2" : "body2"} sx={{ lineHeight: 2 }}>
        {value}
      </Typography>
    );
  }
  if (typeof value === "number") return <Typography variant="subtitle2">{value}</Typography>;
  if (Array.isArray(value) && value.every((x) => typeof x === "string")) {
    return (
      <Stack component="ul" sx={{ m: 0, pr: 2, listStyle: "disc" }}>
        {(value as string[]).map((t, i) => (
          <Typography key={i} component="li" variant="body2">{t}</Typography>
        ))}
      </Stack>
    );
  }
  if (Array.isArray(value) && value.every((x) => isPlainObj(x))) {
    return (
      <Stack spacing={1}>
        {(value as Doc[]).map((it, i) => (
          <Paper key={i} variant="outlined" sx={{ p: 1, bgcolor: "action.hover" }}>
            {Object.keys(it).map((k) =>
              typeof it[k] === "string" || typeof it[k] === "number" ? (
                <Typography key={k} variant="body2">
                  <b>{labelFor(k)}: </b>
                  {k === "img" || k === "icon" ? (
                    looksLikeImagePath(String(it[k])) ? (
                      <Box
                        component="img" src={String(it[k])} alt={labelFor(k)}
                        sx={{ height: 40, verticalAlign: "middle", mx: 0.5 }}
                      />
                    ) : String(it[k])
                  ) : (
                    String(it[k])
                  )}
                </Typography>
              ) : null
            )}
          </Paper>
        ))}
      </Stack>
    );
  }
  if (isPlainObj(value)) {
    return (
      <Stack spacing={0.5}>
        {Object.keys(value).map((k) =>
          typeof value[k] === "string" || typeof value[k] === "number" ? (
            <Typography key={k} variant="body2"><b>{labelFor(k)}: </b>{String(value[k])}</Typography>
          ) : null
        )}
      </Stack>
    );
  }
  return <Typography variant="caption" color="text.secondary">—</Typography>;
}

function PreviewPanel({ doc, order }: { doc: Doc; order: string[] }) {
  return (
    <Stack spacing={2}>
      {order.map((k) => (
        <Paper key={k} variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={800} color="primary.main" gutterBottom>
            {labelFor(k)}
          </Typography>
          <PreviewValue value={doc[k]} />
        </Paper>
      ))}
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// صفحهٔ اصلی ویرایشگر
// ---------------------------------------------------------------------------

export default function SiteContentEditorPage() {
  const qc = useQueryClient();
  const [pageKey, setPageKey] = useState("");
  const [tab, setTab] = useState(0);
  const [doc, setDoc] = useState<Doc | null>(null);
  const [baseSnapshot, setBaseSnapshot] = useState("");
  const [snack, setSnack] = useState<{ msg: string; sev: "success" | "error" } | null>(null);
  const [confirm, setConfirm] = useState<null | "publish" | "reset">(null);

  const adminQ = useQuery({ queryKey: ["site-content-admin"], queryFn: fetchSiteContentAdmin });

  useEffect(() => {
    if (!pageKey && adminQ.data?.pages?.length) setPageKey(adminQ.data.pages[0].page_key);
  }, [adminQ.data, pageKey]);

  const detailQ = useQuery({
    queryKey: ["site-content-page", pageKey],
    queryFn: () => fetchSiteContentPage(pageKey),
    enabled: !!pageKey,
  });

  useEffect(() => {
    const d = detailQ.data;
    if (!d || d.page_key !== pageKey) return;
    const base = (d.draft ?? d.published ?? d.defaults ?? {}) as Doc;
    const cl = cloneDoc(base);
    setDoc(cl);
    setBaseSnapshot(JSON.stringify(cl));
  }, [detailQ.data, pageKey]);

  const meta = adminQ.data?.pages.find((p) => p.page_key === pageKey);
  const detail = detailQ.data;

  const sectionOrder = useMemo(() => {
    if (!doc) return [];
    const pref = detail?.defaults ? Object.keys(detail.defaults) : [];
    const keys = Object.keys(doc);
    return [...keys].sort((a, b) => {
      const ia = pref.indexOf(a);
      const ib = pref.indexOf(b);
      if (ia === -1 && ib === -1) return 0;
      if (ia === -1) return 1;
      if (ib === -1) return -1;
      return ia - ib;
    });
  }, [doc, detail]);

  const dirty = doc != null && JSON.stringify(doc) !== baseSnapshot;
  const draftDiffers =
    !!detail?.draft && !!detail?.published &&
    JSON.stringify(detail.draft) !== JSON.stringify(detail.published);

  const applyDetail = (d: SiteContentPageDetail) => {
    qc.setQueryData(["site-content-page", pageKey], d);
  };

  const onError = (e: unknown) => setSnack({ msg: errDetail(e) || "خطای نامشخص", sev: "error" });

  const saveMut = useMutation({
    mutationFn: (content: Doc) => saveSiteContentDraft(pageKey, content),
    onSuccess: (d) => {
      applyDetail(d);
      qc.invalidateQueries({ queryKey: ["site-content-admin"] });
      setBaseSnapshot(JSON.stringify(cloneDoc(d.draft ?? {})));
      setSnack({ msg: "پیش‌نویس ذخیره شد — تا «انتشار»، هیچ تغییری روی سایت دیده نمی‌شود", sev: "success" });
    },
    onError,
  });

  const publishMut = useMutation({
    mutationFn: () => publishSiteContent(pageKey),
    onSuccess: (d) => {
      applyDetail(d);
      qc.invalidateQueries({ queryKey: ["site-content-admin"] });
      setBaseSnapshot(JSON.stringify(cloneDoc(d.draft ?? {})));
      setSnack({ msg: "منتشر شد — بازدیدکنندگان با بارگذاری دوبارهٔ صفحه، متن جدید را می‌بینند", sev: "success" });
    },
    onError,
  });

  const revertMut = useMutation({
    mutationFn: () => revertSiteContentDraft(pageKey),
    onSuccess: (d) => {
      applyDetail(d);
      qc.invalidateQueries({ queryKey: ["site-content-admin"] });
      const base = (d.draft ?? d.published ?? d.defaults ?? {}) as Doc;
      setBaseSnapshot(JSON.stringify(cloneDoc(base)));
      setDoc(cloneDoc(base));
      setSnack({ msg: "پیش‌نویس به آخرین نسخهٔ منتشرشده بازگشت", sev: "success" });
    },
    onError,
  });

  const resetMut = useMutation({
    mutationFn: () => resetSiteContent(pageKey),
    onSuccess: (d) => {
      applyDetail(d);
      qc.invalidateQueries({ queryKey: ["site-content-admin"] });
      const base = (d.defaults ?? {}) as Doc;
      setBaseSnapshot(JSON.stringify(cloneDoc(base)));
      setDoc(cloneDoc(base));
      setSnack({ msg: "بازنشانی شد — سایت متن پیش‌فرض کد را نشان می‌دهد", sev: "success" });
    },
    onError,
  });

  const doPublish = async () => {
    setConfirm(null);
    try {
      if (dirty && doc) await saveMut.mutateAsync(doc);
      publishMut.mutate();
    } catch {
      /* خطای ذخیره در onError نمایش داده شده */
    }
  };

  if (adminQ.isLoading) {
    return (
      <Box sx={{ p: 4 }}>
        <LinearProgress />
      </Box>
    );
  }
  if (adminQ.isError) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{errDetail(adminQ.error)}</Alert>
      </Box>
    );
  }

  const pages = adminQ.data?.pages ?? [];

  return (
    <Box sx={{ maxWidth: 980, mx: "auto", p: { xs: 1.5, md: 3 } }}>
      <Typography variant="h5" fontWeight={800} mb={0.5}>
        ویرایشگر صفحات عمومی
      </Typography>
      <Typography variant="body2" color="text.secondary" mb={2}>
        مثل وردپرس: متن صفحات عمومی سایت را همین‌جا ویرایش کنید. تغییرات اول در
        «پیش‌نویس» ذخیره می‌شود و تا وقتی «انتشار» نزنید، هیچ بازدیدکننده‌ای چیزی نمی‌بیند.
      </Typography>

      <Paper elevation={0} sx={{ p: 2, mb: 2, border: "1px solid", borderColor: "divider" }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }}>
          <Select
            size="small" value={pageKey} sx={{ minWidth: 240, bgcolor: "background.paper" }}
            onChange={(e) => setPageKey(String(e.target.value))}
          >
            {pages.map((p) => (
              <MenuItem key={p.page_key} value={p.page_key}>
                {p.title}
                {p.has_draft ? " — پیش‌نویس دارد" : p.has_published ? " — منتشرشده" : ""}
              </MenuItem>
            ))}
          </Select>

          {meta?.has_published ? (
            <Chip size="small" color="success" label="نسخهٔ منتشرشده دارد" />
          ) : (
            <Chip size="small" label="متن پیش‌فرض کد" variant="outlined" />
          )}
          {meta?.has_draft && <Chip size="small" color="warning" label="پیش‌نویس ذخیره‌شده دارد" />}
          {dirty && <Chip size="small" color="info" label="تغییرات ذخیره‌نشده" />}

          <Box sx={{ flex: 1 }} />
          <Tooltip title="مشاهدهٔ سایت در تب جدید">
            <span>
              <Button size="small" href="/" target="_blank" rel="noopener" startIcon={<OpenInNewRoundedIcon />}>
                سایت
              </Button>
            </span>
          </Tooltip>
        </Stack>

        {(detail?.updated_at || detail?.published_at) && (
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
            {detail?.updated_at && `آخرین ویرایش پیش‌نویس: ${detail.updated_by_name ?? "—"} — ${detail.updated_at}`}
            {detail?.published_at && `  |  آخرین انتشار: ${detail.published_by_name ?? "—"} — ${detail.published_at}`}
          </Typography>
        )}

        <Divider sx={{ my: 1.5 }} />
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
          <Button
            variant="contained" startIcon={<PublishRoundedIcon />}
            disabled={!doc || publishMut.isPending || saveMut.isPending}
            onClick={() => setConfirm("publish")}
          >
            انتشار
          </Button>
          <Button
            variant="outlined" startIcon={<SaveRoundedIcon />}
            disabled={!doc || !dirty || saveMut.isPending}
            onClick={() => doc && saveMut.mutate(doc)}
          >
            ذخیرهٔ پیش‌نویس
          </Button>
          <Button
            variant="outlined" color="warning" startIcon={<HistoryRoundedIcon />}
            disabled={!draftDiffers || revertMut.isPending}
            onClick={() => revertMut.mutate()}
          >
            بازگردانی پیش‌نویس به منتشرشده
          </Button>
          <Button
            variant="text" color="error" startIcon={<RestartAltRoundedIcon />}
            disabled={resetMut.isPending}
            onClick={() => setConfirm("reset")}
          >
            بازنشانی به متن پیش‌فرض
          </Button>
        </Stack>
      </Paper>

      <Paper elevation={0} sx={{ mb: 2, border: "1px solid", borderColor: "divider" }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ px: 1, pt: 1 }}>
          <Tab label="ویرایش" />
          <Tab label="پیش‌نمایش" icon={<VisibilityRoundedIcon fontSize="small" />} iconPosition="start" />
        </Tabs>
      </Paper>

      {detailQ.isLoading || !doc ? (
        <Box sx={{ p: 4 }}>
          <LinearProgress />
        </Box>
      ) : tab === 0 ? (
        <Stack spacing={2}>
          {sectionOrder.map((k) => (
            <Paper key={k} elevation={0} sx={{ p: 2, border: "1px solid", borderColor: "divider" }}>
              <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
                <Typography variant="subtitle1" fontWeight={800}>{labelFor(k)}</Typography>
                <Chip size="small" variant="outlined" label={k} sx={{ fontSize: 11 }} />
              </Stack>
              <ValueEditor
                depth={0}
                label={labelFor(k)}
                value={doc[k]}
                onChange={(nv) => setDoc({ ...doc, [k]: nv })}
              />
            </Paper>
          ))}
        </Stack>
      ) : (
        <PreviewPanel doc={doc} order={sectionOrder} />
      )}

      <Dialog open={confirm === "publish"} onClose={() => setConfirm(null)}>
        <DialogTitle>انتشار محتوا</DialogTitle>
        <DialogContent>
          <DialogContentText>
            با انتشار، سند جدید بلافاصله برای همهٔ بازدیدکنندگان سایت اعمال می‌شود
            (تغییرات ذخیره‌نشده هم اول ذخیره و بعد منتشر می‌شوند). ادامه می‌دهید؟
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirm(null)}>انصراف</Button>
          <Button variant="contained" onClick={doPublish}>انتشار</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={confirm === "reset"} onClose={() => setConfirm(null)}>
        <DialogTitle>بازنشانی به متن پیش‌فرض</DialogTitle>
        <DialogContent>
          <DialogContentText>
            پیش‌نویس و نسخهٔ منتشرشدهٔ این صفحه حذف می‌شود و سایت به متن‌های
            پیش‌فرض برنامه برمی‌گردد. این عمل بازگشت‌پذیر نیست. ادامه می‌دهید؟
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirm(null)}>انصراف</Button>
          <Button color="error" variant="contained" onClick={() => { setConfirm(null); resetMut.mutate(); }}>
            بازنشانی
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={!!snack} autoHideDuration={5000} onClose={() => setSnack(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert severity={snack?.sev ?? "info"} onClose={() => setSnack(null)} variant="filled">
          {snack?.msg}
        </Alert>
      </Snackbar>
    </Box>
  );
}
