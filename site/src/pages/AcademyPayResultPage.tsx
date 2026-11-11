// فاز ۸۶ - آکادمی رز: نتیجهٔ بازگشت از درگاه پرداخت
// callback درگاه پس از verify سمت سرور به /academy/pay/result?state=...&order=<uuid> برمی‌گردد
import {
  Alert, Box, Button, Container, Paper, Stack, Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { Link as RouterLink, useSearchParams } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { academyOrderStatus, getStoredUser, getToken, type AcademyOrderStatus } from "../academy";

const fa = (n: number) => n.toLocaleString("fa-IR");

export default function AcademyPayResultPage() {
  const [params] = useSearchParams();
  const state = params.get("state") ?? "";
  const orderId = params.get("order") ?? "";
  const [order, setOrder] = useState<AcademyOrderStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    window.scrollTo(0, 0);
    document.title = "نتیجهٔ پرداخت | آکادمی رز";
    if (orderId && getToken()) {
      academyOrderStatus(orderId)
        .then(setOrder)
        .catch((e) => setError(e instanceof Error ? e.message : "خطا"));
    }
  }, [orderId]);

  const success = state === "success" || order?.status === "paid";
  const notLoggedIn = !getToken();

  return (
    <Box>
      <Header />
      <Box sx={{ background: "linear-gradient(180deg,#fdf3f5 0%,#ffffff 100%)", pb: 6 }}>
        <Container maxWidth="sm" sx={{ py: { xs: 5, md: 8 }, minHeight: "55vh" }}>
          <Paper
            elevation={0}
            sx={{
              p: { xs: 3, md: 4.5 }, borderRadius: 4, textAlign: "center",
              border: `1.5px solid ${success ? "#bfe3c8" : "#f0d9df"}`,
              background: success ? "linear-gradient(160deg,#f1faf3,#ffffff)" : "linear-gradient(160deg,#fdf3f5,#ffffff)",
            }}
          >
            <Box sx={{ fontSize: 58, mb: 1 }}>{success ? "✅" : "⚠️"}</Box>
            <Typography variant="h5" fontWeight={800} color={success ? "success.main" : "primary.main"} mb={1}>
              {success ? "پرداخت با موفقیت انجام شد" : "پرداخت تکمیل نشد"}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 2.1 }}>
              {success
                ? "ثبت‌نام شما در دوره(های) سبد فعال شد. ویدیوها از صفحهٔ «دوره‌های من» قابل تماشا هستند."
                : order?.payment?.fail_reason
                  ? `دلیل: ${order.payment.fail_reason}`
                  : "در صورت کسر وجه، مبلغ حداکثر تا ۷۲ ساعت آینده به‌صورت خودکار بازگشت داده می‌شود."}
            </Typography>

            {order && (
              <Stack spacing={0.8} mt={3} textAlign="right">
                <Typography variant="body2">شماره سفارش: <strong dir="ltr">{order.order_number}</strong></Typography>
                <Typography variant="body2">مبلغ: <strong>{fa(order.payable_amount)} ریال</strong></Typography>
                <Typography variant="body2">
                  دوره‌ها: <strong>{order.items.map((i) => i.title).join("، ") || "—"}</strong>
                </Typography>
                {order.payment && (
                  <Typography variant="body2">
                    درگاه: <strong>{order.payment.gateway === "sandbox" ? "شبیه‌ساز (توسعه)" : order.payment.gateway}</strong>
                  </Typography>
                )}
              </Stack>
            )}

            {notLoggedIn && (
              <Alert severity="info" sx={{ mt: 3, textAlign: "right", fontSize: 13 }}>
                برای دیدن دوره‌های خریداری‌شده، با همان شماره موبایل خرید وارد شوید.
              </Alert>
            )}

            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} mt={4}>
              <Button component={RouterLink} to="/academy/my" variant="contained" fullWidth>
                دوره‌های من
              </Button>
              <Button component={RouterLink} to="/academy" variant="outlined" fullWidth>
                بازگشت به آکادمی
              </Button>
            </Stack>
            {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
            {!orderId && (
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 2 }}>
                شناسه سفارش در آدرس صفحه یافت نشد؛ وضعیت خرید را از «دوره‌های من» بررسی کنید.
              </Typography>
            )}
          </Paper>
        </Container>
      </Box>
      <Footer />
      {getStoredUser() ? null : null}
    </Box>
  );
}
