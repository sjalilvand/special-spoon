import {
  Alert, Box, Button, Chip, Divider, Paper, Skeleton, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography,
} from "@mui/material";
import PrintIcon from "@mui/icons-material/Print";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { fetchInvoice } from "../api/payments";
import { formatJalaliDateTime } from "../utils/jalali";

// فاز ۲۹ - B11 سند جامع: جزئیات فاکتور + خروجی PDF (چاپ مرورگر)؛
// مبلغ فاکتور با snapshot سفارش منطبق است و شماره آن یکتاست

const fa = (n: number | string | null | undefined) =>
  n === null || n === undefined ? "—" : Number(n).toLocaleString("fa-IR");

export default function InvoicePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const q = useQuery({
    queryKey: ["invoice", id],
    queryFn: () => fetchInvoice(id!),
    enabled: !!id,
  });

  if (q.isLoading) {
    return <Stack spacing={2}><Skeleton height={40} /><Skeleton height={200} /></Stack>;
  }
  if (q.isError || !q.data) {
    return <Alert severity="error">فاکتور یافت نشد</Alert>;
  }
  const inv = q.data;
  const total = inv.items.reduce((acc, i) => acc + Number(i.line_total), 0);

  return (
    <Stack spacing={2} maxWidth={820} mx="auto">
      <Box display="flex" gap={1} sx={{ "@media print": { display: "none" } }}>
        <Button variant="contained" startIcon={<PrintIcon />} onClick={() => window.print()}>
          چاپ / ذخیره PDF
        </Button>
        <Button onClick={() => navigate("/orders")}>بازگشت به سفارش‌ها</Button>
      </Box>

      <Paper sx={{ p: { xs: 2, md: 4 }, border: "1px solid #e5dcd3" }}>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" flexWrap="wrap" gap={2}>
          <Box>
            <Typography variant="h5" fontWeight={800} color="#8d2f3c">فاکتور خدمات مشاوره</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              کلینیک رز — سامانه Rosepsy
            </Typography>
          </Box>
          <Box sx={{ textAlign: "left" }}>
            <Typography variant="body1" sx={{ direction: "ltr", fontWeight: 700 }}>{inv.invoice_number}</Typography>
            <Typography variant="body2" color="text.secondary">
              تاریخ صدور: {formatJalaliDateTime(inv.issued_at)}
            </Typography>
            <Box sx={{ mt: 1 }}>
              <Chip size="small" color={inv.status === "issued" ? "success" : "default"}
                    label={inv.status === "issued" ? "صادرشده" : "ابطال‌شده"} />
            </Box>
          </Box>
        </Box>

        <Divider sx={{ my: 2.5 }} />

        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} justifyContent="space-between">
          <Box>
            <Typography variant="body2" color="text.secondary">خریدار</Typography>
            <Typography>{inv.buyer_name ?? "—"}</Typography>
            {inv.buyer_national_id && (
              <Typography variant="body2" color="text.secondary">کد ملی: {inv.buyer_national_id}</Typography>
            )}
            {inv.buyer_email && (
              <Typography variant="body2" color="text.secondary" sx={{ direction: "ltr" }}>{inv.buyer_email}</Typography>
            )}
          </Box>
          <Box sx={{ textAlign: { sm: "left" } }}>
            <Typography variant="body2" color="text.secondary">سفارش مرتبط</Typography>
            <Typography sx={{ direction: "ltr" }}>{inv.order_number ?? "—"}</Typography>
          </Box>
        </Stack>

        <TableContainer sx={{ mt: 3, border: "1px solid #eee" }}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: "#faf5f2" }}>
                <TableCell>#</TableCell>
                <TableCell>شرح</TableCell>
                <TableCell align="center">تعداد</TableCell>
                <TableCell align="center">مبلغ واحد (ریال)</TableCell>
                <TableCell align="center">جمع ردیف (ریال)</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {inv.items.map((item, idx) => (
                <TableRow key={item.id}>
                  <TableCell>{fa(idx + 1)}</TableCell>
                  <TableCell>{item.description}</TableCell>
                  <TableCell align="center">{fa(item.quantity)}</TableCell>
                  <TableCell align="center">{fa(item.unit_amount)}</TableCell>
                  <TableCell align="center">{fa(item.line_total)}</TableCell>
                </TableRow>
              ))}
              <TableRow sx={{ bgcolor: "#fdfaf8" }}>
                <TableCell colSpan={4} align="left" sx={{ fontWeight: 700 }}>
                  جمع کل (ریال)
                </TableCell>
                <TableCell align="center" sx={{ fontWeight: 800, fontSize: 15 }}>
                  {fa(total)}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </TableContainer>

        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" sx={{ mt: 4 }} spacing={2}>
          <Typography variant="body2" color="text.secondary">
            این فاکتور به‌صورت الکترونیکی توسط سامانه Rosepsy صادر شده است.
          </Typography>
          <Box sx={{ textAlign: "center" }}>
            <Typography variant="body2" sx={{ mb: 4 }}>مهر و امضا</Typography>
            <Box borderTop="1px solid #999" width={160} mx="auto" />
          </Box>
        </Stack>
      </Paper>
    </Stack>
  );
}
