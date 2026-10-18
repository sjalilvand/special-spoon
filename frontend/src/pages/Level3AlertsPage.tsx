import {
  Alert, Chip, CircularProgress, Divider, Paper, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Button } from "@mui/material";
import { fetchLevel3Cartable } from "../api/assessments";

/**
 * کارتابل هشدار سطح ۳ مسئول فنی (فاز ۲۳) — چرخه فرم مورد حاد RS-PS-08-01
 *
 * فقط فرم‌های نهایی‌شده با سطح فوریت ۳ که در انتظار بررسی هستند نمایش داده می‌شوند؛
 * قدیمی‌ترین هشدار اول. داده‌ها هر ۳۰ ثانیه بازخوانی می‌شوند.
 */
export default function Level3AlertsPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["worklist-level3"],
    queryFn: fetchLevel3Cartable,
    refetchInterval: 30_000,
  });

  const items = data?.items ?? [];

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
        <Typography variant="h6" fontWeight={700}>کارتابل هشدار سطح ۳ (مورد حاد)</Typography>
        <Chip color="error" size="small" label={`در انتظار بررسی: ${items.length}`} />
        {typeof data?.total_level3 === "number" && (
          <Chip variant="outlined" size="small" label={`مجموع هشدارهای سطح ۳ ثبت‌شده: ${data.total_level3}`} />
        )}
      </Stack>

      <Alert severity="warning" variant="outlined">
        موارد سطح ۳ (فوریت بالا) نیازمند اقدام فوری و ارجاع اورژانسی هستند. تکمیل اطلاعات ارجاع
        برای نهایی‌سازی الزامی است و این کارتابل فقط مسئول فنی را هدف می‌گیرد.
      </Alert>

      {isError && <Alert severity="error">بارگذاری کارتابل هشدار سطح ۳ ناموفق بود.</Alert>}

      <TableContainer component={Paper} sx={{ border: items.length ? 1 : 0, borderColor: "error.light" }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ bgcolor: "#fdecea" }}>
              <TableCell>پرونده</TableCell>
              <TableCell>فرد در فرم (تماس)</TableCell>
              <TableCell>متقاضی پرونده</TableCell>
              <TableCell>نوع خطر</TableCell>
              <TableCell>اقدام فوری</TableCell>
              <TableCell>مقصد و نتیجه ارجاع</TableCell>
              <TableCell>نویسنده / زمان</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={8} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {!isLoading && items.length === 0 && (
              <TableRow>
                <TableCell colSpan={8}>
                  <Stack spacing={1} alignItems="center" sx={{ py: 3 }}>
                    <Typography variant="subtitle1" color="success.main" fontWeight={700}>
                      هشدار سطح ۳ در انتظار بررسی وجود ندارد.
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      اگر فرم مورد حاد جدیدی با فوریت بالا نهایی شود، به‌صورت خودکار در همین صفحه ظاهر می‌شود (بازخوانی هر ۳۰ ثانیه).
                    </Typography>
                  </Stack>
                </TableCell>
              </TableRow>
            )}
            {items.map((row) => (
              <TableRow key={row.id} hover>
                <TableCell>
                  <Stack spacing={0.5}>
                    <Typography variant="body2" fontWeight={700}>{row.case_number}</Typography>
                    <Chip color="error" size="small" label={row.severity_label ?? "سطح ۳"} sx={{ alignSelf: "flex-start" }} />
                  </Stack>
                </TableCell>
                <TableCell>
                  <Stack spacing={0.5}>
                    <Typography variant="body2" fontWeight={700}>{row.person_name ?? "—"}</Typography>
                    <Typography variant="caption" color="text.secondary">{row.person_phone ?? "—"}</Typography>
                  </Stack>
                </TableCell>
                <TableCell>{row.applicant_name}</TableCell>
                <TableCell>
                  <Stack spacing={0.5} useFlexGap flexWrap="wrap" maxWidth={220}>
                    {row.risk_types.length
                      ? row.risk_types.map((rt) => (
                        <Chip key={rt} size="small" variant="outlined" color="error" label={rt} />
                      ))
                      : <Typography variant="caption">—</Typography>}
                  </Stack>
                </TableCell>
                <TableCell sx={{ maxWidth: 220 }}>{row.immediate_action ?? "—"}</TableCell>
                <TableCell sx={{ maxWidth: 220 }}>
                  <Stack spacing={0.5}>
                    <Typography variant="body2">{row.referral_destination ?? "—"}</Typography>
                    {row.referral_result && (
                      <>
                        <Divider />
                        <Typography variant="caption" color="text.secondary">{row.referral_result}</Typography>
                      </>
                    )}
                  </Stack>
                </TableCell>
                <TableCell>
                  <Stack spacing={0.5}>
                    <Typography variant="caption">{row.author_name ?? "—"}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {row.finalized_at ? new Date(row.finalized_at).toLocaleString("fa-IR") : "—"}
                    </Typography>
                  </Stack>
                </TableCell>
                <TableCell>
                  <Button size="small" variant="contained" color="error" onClick={() => navigate(`/assessments/${row.id}`)}>
                    بررسی فوری
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}
