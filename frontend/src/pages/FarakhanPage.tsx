// فاز ۸۸ - پنل «فراخوان همکاری»: فهرست ثبت‌نام‌های فرم عمومی + جزئیات + فایل‌ها
// + تغییر وضعیت بررسی + خروجی اکسل. دادهٔ فرم عمومی /farakhan اینجا مدیریت می‌شود.
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogContent,
  DialogTitle, FormControl, Grid, IconButton, InputLabel, MenuItem, Paper, Select,
  Stack, Table, TableBody, TableCell, TableContainer, TableHead, TablePagination,
  TableRow, TextField, Tooltip, Typography,
} from "@mui/material";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import ExcelRoundedIcon from "@mui/icons-material/TableChart";
import OpenInNewRoundedIcon from "@mui/icons-material/OpenInNew";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { errDetail } from "../api/client";
import {
  downloadFarakhanFile, exportFarakhanSubmissions, fetchFarakhanSubmission, fetchFarakhanSubmissions,
  setFarakhanSubmissionStatus,
} from "../api/farakhan";
import type { FarakhanSubmissionRow } from "../api/farakhan";
import { formatJalaliDateTime } from "../utils/jalali";

const STATUS_CHIPS: Record<string, { label: string; color: "default" | "primary" | "info" | "success" | "warning" | "error" }> = {
  new: { label: "جدید", color: "primary" },
  reviewed: { label: "بررسی‌شده", color: "info" },
  accepted: { label: "پذیرفته‌شده", color: "success" },
  rejected: { label: "ردشده", color: "error" },
};

function faBytes(n: number): string {
  if (n >= 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} مگابایت`;
  return `${Math.ceil(n / 1024)} کیلوبایت`;
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Grid item xs={12} sm={6} md={4}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography variant="body2" fontWeight={600}>{value ?? "—"}</Typography>
    </Grid>
  );
}

function YesNo({ value }: { value: boolean }) {
  return <Chip size="small" label={value ? "بله" : "خیر"} color={value ? "success" : "default"} variant="outlined" />;
}

function DetailDialog({ id, onClose }: { id: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["farakhan-submission", id],
    queryFn: () => fetchFarakhanSubmission(id),
  });

  const apply = async (nextStatus: string) => {
    setSaving(true);
    setError("");
    try {
      await setFarakhanSubmissionStatus(id, nextStatus, note);
      setStatus(nextStatus);
      qc.invalidateQueries({ queryKey: ["farakhan-submissions"] });
      qc.invalidateQueries({ queryKey: ["farakhan-submission", id] });
    } catch (e) {
      setError(errDetail(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1, pb: 1 }}>
        {data && <Chip size="small" label={data.tracking_code} sx={{ fontFamily: "monospace", direction: "ltr" }} />}
        {data ? `${data.first_name} ${data.last_name}` : "جزئیات ثبت‌نام"}
        <Box flexGrow={1} />
        {data && <Chip size="small" label={STATUS_CHIPS[status || data.status]?.label ?? data.status} color={STATUS_CHIPS[status || data.status]?.color ?? "default"} />}
        <IconButton onClick={onClose} aria-label="بستن"><CloseRoundedIcon /></IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {isLoading || !data ? (
          <Stack alignItems="center" py={6}><CircularProgress sx={{ color: "primary.main" }} /></Stack>
        ) : (
          <>
            <Grid container spacing={2} sx={{ mb: 2 }}>
              <DetailRow label="کد ملی" value={<span dir="ltr">{data.national_code}</span>} />
              <DetailRow label="جنسیت" value={data.gender_label} />
              <DetailRow label="تاریخ تولد (شمسی)" value={<span dir="ltr">{data.birth_date_jalali}</span>} />
              <DetailRow label="وضعیت سربازی" value={data.military_status_label} />
              <DetailRow label="مدرک تحصیلی" value={data.education_degree_label} />
              <DetailRow label="رشته تحصیلی" value={data.education_field} />
              <DetailRow label="وضعیت پروانه" value={data.license_status_label} />
              <DetailRow label="شماره پروانه" value={data.license_number ? <span dir="ltr">{data.license_number}</span> : null} />
              <DetailRow label="توضیحات پروانه" value={data.license_description} />
              <DetailRow label="مالکیت مرکز" value={data.center_ownership_label} />
              <DetailRow label="استان / شهرستان" value={`${data.province_name} / ${data.county_name}`} />
              <DetailRow label="تلفن ثابت" value={<span dir="ltr">{data.phone}</span>} />
              <DetailRow label="همراه" value={data.mobile_number ? <span dir="ltr">{data.mobile_number}</span> : null} />
              <DetailRow label="کدپستی" value={data.postal_code ? <span dir="ltr">{data.postal_code}</span> : null} />
              <DetailRow label="نشانی" value={data.address} />
              <DetailRow label="اتاق انفرادی / گروهی / کودک" value={`${data.individual_rooms} / ${data.group_rooms} / ${data.child_rooms}`} />
              <DetailRow label="تعداد مشاوران" value={data.counselors_count} />
              <DetailRow label="فضای انتظار" value={<YesNo value={data.has_waiting_space} />} />
              <DetailRow label="الگوی شرکت‌ها" value={<YesNo value={data.accepts_company_pattern} />} />
              <DetailRow label="دسترسی‌پذیری" value={<YesNo value={data.has_accessibility} />} />
              <DetailRow label="تاریخ ثبت" value={data.created_at ? formatJalaliDateTime(data.created_at) : null} />
              <DetailRow label="IP ثبت" value={data.submit_ip ? <span dir="ltr">{data.submit_ip}</span> : null} />
            </Grid>

            <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1 }}>مدارک بارگذاری‌شده ({data.files.length})</Typography>
            {data.files.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>فایلی ثبت نشده است.</Typography>
            ) : (
              <Stack spacing={1} sx={{ mb: 2 }}>
                {data.files.map((f) => (
                  <Stack key={f.id} direction="row" spacing={1} alignItems="center"
                    sx={{ border: "1px solid #f3dce2", borderRadius: 2, px: 1.5, py: 1 }}>
                    <Typography variant="body2" fontWeight={700}>{f.field_label}</Typography>
                    <Typography variant="caption" color="text.secondary" noWrap sx={{ flexGrow: 1 }}>
                      {f.original_name} ({faBytes(f.size_bytes)})
                    </Typography>
                    <Tooltip title="دانلود امن (بلیت کوتاه‌مدت)">
                      <IconButton size="small" onClick={() => downloadFarakhanFile(f.file_id)} aria-label={`دانلود ${f.field_label}`}>
                        <DownloadRoundedIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                ))}
              </Stack>
            )}

            <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1 }}>بررسی</Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }}>
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel>وضعیت بررسی</InputLabel>
                <Select value={status || data.status} label="وضعیت بررسی" onChange={(e) => setStatus(e.target.value)}>
                  {Object.entries(STATUS_CHIPS).map(([key, v]) => (
                    <MenuItem key={key} value={key}>{v.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField size="small" label="یادداشت بررسی" value={note}
                onChange={(e) => setNote(e.target.value)} sx={{ flexGrow: 1 }}
                helperText={data.review_note && !note ? `یادداشت فعلی: ${data.review_note}` : undefined} />
              <Button variant="contained" disabled={saving} onClick={() => apply(status || data.status)}>
                {saving ? "…" : "ذخیرهٔ بررسی"}
              </Button>
            </Stack>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function FarakhanPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["farakhan-submissions", page + 1, pageSize, q, status],
    queryFn: () => fetchFarakhanSubmissions({ q, status, page: page + 1, page_size: pageSize }),
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const doExport = async () => {
    setExporting(true);
    setError("");
    try {
      await exportFarakhanSubmissions(status);
    } catch (e) {
      setError(errDetail(e));
    } finally {
      setExporting(false);
    }
  };

  return (
    <Box p={{ xs: 2, md: 3 }}>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
        <Typography variant="h6" fontWeight={800}>فراخوان همکاری</Typography>
        <Typography variant="caption" color="text.secondary">
          ثبت‌نام‌های فرم عمومی /farakhan
        </Typography>
        <Box flexGrow={1} />
        <Tooltip title="خروجی اکسل">
          <span>
            <Button variant="outlined" startIcon={<ExcelRoundedIcon />} disabled={exporting} onClick={doExport}>
              {exporting ? "…" : "اکسل"}
            </Button>
          </span>
        </Tooltip>
        <Tooltip title="بازخوانی">
          <IconButton onClick={() => qc.invalidateQueries({ queryKey: ["farakhan-submissions"] })} aria-label="بازخوانی">
            <RefreshRoundedIcon />
          </IconButton>
        </Tooltip>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>{error}</Alert>}

      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mb: 2 }}>
        <TextField size="small" label="جست‌وجو (نام، کد ملی، کد پیگیری، تلفن)" value={q}
          onChange={(e) => { setQ(e.target.value); setPage(0); }} sx={{ minWidth: 320 }} />
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>وضعیت</InputLabel>
          <Select value={status} label="وضعیت" onChange={(e) => { setStatus(e.target.value); setPage(0); }}>
            <MenuItem value="">همه</MenuItem>
            {Object.entries(STATUS_CHIPS).map(([key, v]) => (
              <MenuItem key={key} value={key}>{v.label}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <Typography variant="body2" color="text.secondary" alignSelf="center">
          {isFetching || isLoading ? "…" : `${total.toLocaleString("fa-IR")} ثبت‌نام`}
        </Typography>
      </Stack>

      <TableContainer component={Paper} elevation={0} sx={{ border: "1px solid #eee3e8", borderRadius: 3 }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ bgcolor: "#fdf3f5" }}>
              <TableCell>کد پیگیری</TableCell>
              <TableCell>نام و نام خانوادگی</TableCell>
              <TableCell>کد ملی</TableCell>
              <TableCell>استان / شهرستان</TableCell>
              <TableCell>مدرک</TableCell>
              <TableCell>تلفن</TableCell>
              <TableCell>فایل‌ها</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>تاریخ ثبت</TableCell>
              <TableCell align="center">جزئیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <TableRow><TableCell colSpan={10} align="center" sx={{ py: 6 }}><CircularProgress sx={{ color: "primary.main" }} /></TableCell></TableRow>
            ) : items.length === 0 ? (
              <TableRow><TableCell colSpan={10} align="center" sx={{ py: 6 }}>
                <Typography variant="body2" color="text.secondary">ثبت‌نامی یافت نشد.</Typography>
              </TableCell></TableRow>
            ) : items.map((row: FarakhanSubmissionRow) => (
              <TableRow key={row.id} hover>
                <TableCell><Typography variant="caption" sx={{ fontFamily: "monospace", direction: "ltr" }}>{row.tracking_code}</Typography></TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{row.first_name} {row.last_name}</TableCell>
                <TableCell><span dir="ltr">{row.national_code}</span></TableCell>
                <TableCell>{row.province_name} / {row.county_name}</TableCell>
                <TableCell>{row.education_degree_label}</TableCell>
                <TableCell><span dir="ltr">{row.phone}</span></TableCell>
                <TableCell align="center">{row.file_count.toLocaleString("fa-IR")}</TableCell>
                <TableCell><Chip size="small" label={row.status_label} color={STATUS_CHIPS[row.status]?.color ?? "default"} /></TableCell>
                <TableCell>{row.created_at ? formatJalaliDateTime(row.created_at) : "—"}</TableCell>
                <TableCell align="center">
                  <Tooltip title="جزئیات و بررسی">
                    <IconButton size="small" onClick={() => setOpenId(row.id)} aria-label={`جزئیات ${row.tracking_code}`}>
                      <OpenInNewRoundedIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <TablePagination
          component="div"
          count={total}
          page={page}
          onPageChange={(_e, p) => setPage(p)}
          rowsPerPage={pageSize}
          onRowsPerPageChange={(e) => { setPageSize(Number(e.target.value)); setPage(0); }}
          rowsPerPageOptions={[10, 20, 50, 100]}
          labelRowsPerPage="ردیف در صفحه:"
          labelDisplayedRows={({ from, to, count }) => `${from.toLocaleString("fa-IR")}–${to.toLocaleString("fa-IR")} از ${count.toLocaleString("fa-IR")}`}
        />
      </TableContainer>

      {openId && <DetailDialog id={openId} onClose={() => setOpenId(null)} />}
    </Box>
  );
}
