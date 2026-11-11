// فاز ۸۶ - آکادمی رز: سبد خرید → پرداخت در درگاه (شبیه‌ساز/زرین‌پال)
import {
  Alert, Box, Button, Chip, Container, Divider, Paper, Stack, Typography,
} from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import AcademyAuthDialog from "../components/AcademyAuthDialog";
import {
  CART_EVENT, academyCheckout, academyPay, clearCart, fetchAcademyCourses,
  getStoredUser, getToken, removeFromCart,
  type AcademyCourseSummary,
} from "../academy";

const fa = (n: number) => n.toLocaleString("fa-IR");

export default function AcademyCartPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [courses, setCourses] = useState<AcademyCourseSummary[] | null>(null);
  const [items, setItems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [user, setUser] = useState(getStoredUser());

  const reload = useCallback(() => {
    try {
      const raw = localStorage.getItem("rosepsy_academy_cart");
      setItems(raw ? JSON.parse(raw) : []);
    } catch {
      setItems([]);
    }
  }, []);

  useEffect(() => {
    window.scrollTo(0, 0);
    document.title = "سبد خرید | آکادمی رز";
    reload();
    fetchAcademyCourses().then(setCourses).catch(() => setCourses([]));
    const onCart = () => reload();
    window.addEventListener(CART_EVENT, onCart);
    return () => window.removeEventListener(CART_EVENT, onCart);
  }, [reload]);

  const lines = (courses ?? []).filter((c) => items.includes(c.id));
  const total = lines.reduce((s, c) => s + c.price_amount, 0);
  const hasPaid = lines.some((c) => !c.is_free);
  const buyNow = params.get("buy") === "1" || params.get("order") !== null;

  const doCheckout = async () => {
    setError(null);
    if (!items.length) return;
    if (!getToken()) {
      setAuthOpen(true);
      return;
    }
    setBusy(true);
    try {
      const res = await academyCheckout(items);
      if (res.order) {
        // یک سبد = یک سفارش = یک پرداخت
        const pay = await academyPay(res.order.id);
        window.location.href = pay.redirect_url;
        return;
      }
      // فقط دورهٔ رایگان بود — بلافاصله ثبت‌نام شد
      clearCart();
      setOkMsg("ثبت‌نام شما در دوره‌های رایگان انجام شد ✓");
      setTimeout(() => navigate("/academy/my"), 1200);
    } catch (e) {
      setError(e instanceof Error ? e.message : "خطا در پرداخت");
      setBusy(false);
    }
  };

  useEffect(() => {
    // ?buy=1 یا ?order=... → شروع خودکار checkout پس از ورود
    if (buyNow && items.length && getToken() && !busy && user) {
      void doCheckout();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buyNow, items.length, user]);

  return (
    <Box>
      <Header />
      <Box sx={{ background: "linear-gradient(180deg,#fdf3f5 0%,#ffffff 100%)", pb: 6 }}>
        <Container maxWidth="md" sx={{ py: { xs: 4, md: 6 }, minHeight: "55vh" }}>
          <Typography variant="h4" fontWeight={800} color="primary.main">سبد خرید</Typography>
          <Typography variant="body2" color="text.secondary" mt={1}>
            همهٔ دوره‌های سبد با «یک» پرداخت فعال می‌شوند.
          </Typography>

          {error && <Alert severity="error" sx={{ mt: 2 }} onClose={() => setError(null)}>{error}</Alert>}
          {okMsg && <Alert severity="success" sx={{ mt: 2 }}>{okMsg}</Alert>}

          <Stack spacing={1.5} mt={3}>
            {!courses && <Typography color="text.secondary">در حال بارگذاری...</Typography>}
            {courses && lines.length === 0 && (
              <Paper sx={{ p: 4, textAlign: "center", border: "1px solid #f3dce2" }}>
                <Typography color="text.secondary" mb={2}>سبد خرید شما خالی است.</Typography>
                <Button component={RouterLink} to="/academy" variant="contained">مشاهده دوره‌ها</Button>
              </Paper>
            )}
            {lines.map((c) => (
              <Paper key={c.id} sx={{ p: 2, border: "1px solid #f3dce2", borderRadius: 3 }}>
                <Stack direction="row" alignItems="center" spacing={2}>
                  {c.cover_image_url && (
                    <Box component="img" src={c.cover_image_url} alt={c.title}
                      sx={{ width: 84, height: 60, objectFit: "cover", borderRadius: 2 }} />
                  )}
                  <Box flexGrow={1} sx={{ minWidth: 0 }}>
                    <Typography fontWeight={700} noWrap>{c.title}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {c.episodes_count > 0 ? `${fa(c.episodes_count)} جلسه` : "به‌زودی"}
                    </Typography>
                  </Box>
                  {c.is_free
                    ? <Chip size="small" color="success" label="رایگان" />
                    : <Typography fontWeight={800} color="primary.main">{fa(c.price_amount)} ریال</Typography>}
                  <Button size="small" color="error" onClick={() => { removeFromCart(c.id); reload(); }}>
                    حذف
                  </Button>
                </Stack>
              </Paper>
            ))}
          </Stack>

          {lines.length > 0 && (
            <Paper sx={{ p: 3, mt: 3, border: "1px solid #f3dce2", borderRadius: 3 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="body1">جمع قابل پرداخت</Typography>
                <Typography variant="h6" fontWeight={800} color="primary.main">
                  {hasPaid ? `${fa(total)} ریال` : "رایگان"}
                </Typography>
              </Stack>
              <Divider sx={{ my: 2 }} />
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
                <Button variant="contained" size="large" disabled={busy} onClick={doCheckout} fullWidth>
                  {busy ? "در حال اتصال به درگاه..." : hasPaid ? "پرداخت و ثبت‌نام" : "ثبت‌نام رایگان"}
                </Button>
                <Button component={RouterLink} to="/academy" variant="outlined" fullWidth>
                  ادامه خرید
                </Button>
              </Stack>
              {user && (
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                  خریدار: {user.display_name} ({user.mobile})
                </Typography>
              )}
            </Paper>
          )}
        </Container>
      </Box>
      <AcademyAuthDialog
        open={authOpen}
        onClose={() => setAuthOpen(false)}
        onDone={() => {
          setUser(getStoredUser());
          void doCheckout();
        }}
      />
      <Footer />
    </Box>
  );
}
