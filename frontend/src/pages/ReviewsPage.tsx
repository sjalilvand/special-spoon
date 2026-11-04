// فاز ۷۶ (v0.59.0): صفحهٔ بررسی‌های فنی با راهنمای روان — پیش‌تر فقط جدول خام
// بود و معنی «کارتابل مسئول فنی»، وضعیت‌ها و تفاوت تأیید/برگشت برای کاربر روشن نبود.
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogContent, DialogTitle,
  Divider, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, Tooltip as MuiTooltip, Typography,
} from "@mui/material";
import HelpOutlineRoundedIcon from "@mui/icons-material/HelpOutlineRounded";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ASSESSMENT_STATUS_META, fetchSupervisorWorklist } from "../api/assessments";
import { formatJalaliDateTime } from "../utils/jalali";

/** راهنمای وضعیت‌های ارزیابی — همان برچسب‌های سراسری سامانه */
const STATUS_GUIDE: Record<string, string> = {
  draft: "پیش‌نویس: مشاور هنوز فرم را نهایی نکرده است؛ به صف بررسی نمی‌رسد.",
  finalized: "نهایی‌شده توسط مشاور و در حال ورود به صف بررسی فنی.",
  pending_review: "در انتظار بررسی شما: نوبتِ تصمیم‌گیری (تأیید یا برگشت) دست مسئول فنی است.",
  returned: "برگشت‌خورده: مسئول فنی ایراد گرفته است؛ نسخه نزد مشاور برای اصلاح برمی‌گردد.",
  approved: "تأییدشده: بررسی فنی تمام و سند در پرونده بایگانی شد؛ دیگر قابل ویرایش نیست.",
};

export default function ReviewsPage() {
  const navigate = useNavigate();
  const [helpOpen, setHelpOpen] = useState(false);
  const { data, isLoading, error } = useQuery({
    queryKey: ["worklist-supervisor"],
    queryFn: fetchSupervisorWorklist,
  });

  return (
    <Stack spacing={2}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" useFlexGap spacing={1}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h6" fontWeight={700}>بررسی‌های فنی (کارتابل مسئول فنی)</Typography>
          <Chip size="small" color="warning" variant="outlined"
            label={`${(data?.items.length ?? 0).toLocaleString("fa-IR")} در صف`} />
        </Stack>
        <Button size="small" variant="outlined" startIcon={<HelpOutlineRoundedIcon />}
          onClick={() => setHelpOpen(true)} sx={{ borderRadius: 99 }}>
          این صفحه چیست؟ (راهنما)
        </Button>
      </Stack>

      <Alert severity="info" sx={{ borderRadius: 2.5 }}>
        <Typography variant="body2" fontWeight={700} mb={0.5}>
          خلاصهٔ کار شما در این صفحه:
        </Typography>
        <Typography variant="body2" sx={{ lineHeight: 1.9 }}>
          هر ارزیابی‌ای که مشاور «نهایی» می‌کند به این صف می‌آید. شما ارزیابی را می‌خوانید و دو تصمیم دارید:
          <b> تأیید</b> (سند قطعی و بایگانی می‌شود) یا <b>برگشت</b> (با ذکر دلیل نزد مشاور برمی‌گردد تا اصلاح و دوباره نهایی کند).
          تا وقتی بررسی نشود، ارزیابی در وضعیت «در انتظار بررسی» می‌ماند.
        </Typography>
      </Alert>

      {/* راهنمای سریع وضعیت‌ها */}
      <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 3, display: "flex", gap: 0.75, flexWrap: "wrap", alignItems: "center" }}>
        <Typography variant="caption" color="text.secondary" fontWeight={700}>راهنمای وضعیت‌ها:</Typography>
        {Object.entries(ASSESSMENT_STATUS_META).map(([k, m]) => (
          <MuiTooltip key={k} title={STATUS_GUIDE[k] ?? ""} arrow>
            <Chip size="small" color={m.color} label={m.label} variant="outlined" sx={{ cursor: "help" }} />
          </MuiTooltip>
        ))}
      </Paper>

      {error && <Alert severity="error">دریافت صف بررسی ناموفق بود؛ دوباره تلاش کنید.</Alert>}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>پرونده</TableCell>
              <TableCell>متقاضی</TableCell>
              <TableCell>نسخه</TableCell>
              <TableCell>نویسنده</TableCell>
              <TableCell>زمان نهایی‌سازی</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={7} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7}>
                  <Typography variant="body2" color="text.secondary" py={1}>
                    صف بررسی خالی است — هیچ ارزیابی در انتظار تصمیم شما نیست. 🎉
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((row) => {
              const st = ASSESSMENT_STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
              return (
                <TableRow key={row.id} hover>
                  <TableCell sx={{ fontWeight: 700 }}>{row.case_number}</TableCell>
                  <TableCell>{row.applicant_name ?? "—"}</TableCell>
                  <TableCell>نسخه {row.version_no.toLocaleString("fa-IR")}</TableCell>
                  <TableCell>{row.author_name ?? "—"}</TableCell>
                  <TableCell>
                    {row.finalized_at ? formatJalaliDateTime(row.finalized_at) : "—"}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" color={st.color} label={st.label} />
                  </TableCell>
                  <TableCell>
                    <Button size="small" variant="outlined" onClick={() => navigate(`/assessments/${row.id}`)}>
                      بازکردن و بررسی
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      {/* راهنمای کامل */}
      <Dialog open={helpOpen} onClose={() => setHelpOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>کارتابل مسئول فنی چیست و چطور کار می‌کند؟</DialogTitle>
        <DialogContent>
          <Stack spacing={1.5} divider={<Divider flexItem />}>
            <Typography variant="body2" sx={{ lineHeight: 2 }}>
              <b>۱. تعریف:</b> «کارتابل مسئول فنی» یعنی صندوق کار شما؛ هر کاری که برای تصمیم‌گیری نظارتی نیاز دارید اینجا جمع می‌شود.
              در این سامانه، تمرکز اصلی کارتابل روی <b>ارزیابی‌های بالینی</b> است: فرم‌هایی که مشاوران برای پرونده‌ها ثبت می‌کنند.
            </Typography>
            <Typography variant="body2" sx={{ lineHeight: 2 }}>
              <b>۲. چرخهٔ یک ارزیابی:</b> مشاور فرم را پر می‌کند → «پیش‌نویس» → دکمهٔ نهایی‌سازی → «در انتظار بررسی»
              (به کارتابل شما می‌آید) → شما تأیید می‌کنید («تأییدشده») یا با دلیل برمی‌گردانید («برگشت‌خورده» → مشاور اصلاح می‌کند و دوباره نهایی می‌کند).
            </Typography>
            <Typography variant="body2" sx={{ lineHeight: 2 }}>
              <b>۳. «برگشتی» یعنی چه؟</b> یعنی نسخهٔ ارزیابی ایراد داشته و نزد مشاور رفته است؛ مثلاً دادهٔ ناقص، تفسیر ضعیف یا خطای روال.
              دلیل برگشت در همان ارزیابی ثبت می‌شود و مشاور می‌بیند. پرونده گیر نمی‌کند؛ فقط نسخهٔ جدید جایگزین می‌شود.
            </Typography>
            <Typography variant="body2" sx={{ lineHeight: 2 }}>
              <b>۴. چرا مهم است؟</b> این چرخه تضمین می‌کند هیچ سند بالینی بدون بازبینی فنی، نهایی و بایگانی نشود
              (الزام سند جامع — نظارت فنی مرحلهٔ ۷ از ۸ مرحلهٔ گردش‌کار سامانه).
            </Typography>
            <Box>
              <Typography variant="subtitle2" fontWeight={800} mb={0.5}>معنی هر وضعیت:</Typography>
              <Stack spacing={0.75}>
                {Object.entries(STATUS_GUIDE).map(([k, txt]) => (
                  <Stack key={k} direction="row" spacing={1} alignItems="center">
                    <Chip size="small" color={ASSESSMENT_STATUS_META[k]?.color ?? "default"} label={ASSESSMENT_STATUS_META[k]?.label ?? k} />
                    <Typography variant="caption" sx={{ lineHeight: 1.8 }}>{txt}</Typography>
                  </Stack>
                ))}
              </Stack>
            </Box>
          </Stack>
        </DialogContent>
      </Dialog>
    </Stack>
  );
}
