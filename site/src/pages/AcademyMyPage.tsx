// فاز ۸۶ - آکادمی رز: دوره‌های من — دسترسی به ویدیوها + پرداخت‌های معلق
import {
  Alert, Box, Button, Chip, Container, LinearProgress, Paper, Stack, Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import AcademyAuthDialog from "../components/AcademyAuthDialog";
import {
  academyPay, clearSession, fetchAcademyMe, getToken, type AcademyMyCourse,
} from "../academy";

const fa = (n: number) => n.toLocaleString("fa-IR");

const STATUS: Record<string, { label: string; color: "success" | "warning" | "info" | "error" | "default" }> = {
  active: { label: "فعال", color: "success" },
  completed: { label: "تکمیل‌شده", color: "info" },
  pending: { label: "در انتظار پرداخت", color: "warning" },
  cancelled: { label: "لغوشده", color: "error" },
};

export default function AcademyMyPage() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState<AcademyMyCourse[] | null>(null);
  const [user, setUser] = useState<{ display_name: string; mobile: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = () => {
    if (!getToken()) {
      setAuthOpen(true);
      setCourses([]);
      return;
    }
    fetchAcademyMe()
      .then((d) => {
        setUser(d.user);
        setCourses(d.courses);
      })
      .catch((e) => {
        if (e instanceof Error && e.message === "unauthorized") {
          clearSession();
          setAuthOpen(true);
          setCourses([]);
        } else {
          setError(e instanceof Error ? e.message : "خطا");
        }
      });
  };

  useEffect(() => {
    window.scrollTo(0, 0);
    document.title = "دوره‌های من | آکادمی رز";
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const resumePayment = async (c: AcademyMyCourse) => {
    if (!c.order) return;
    setBusyId(c.enrollment_id);
    try {
      const pay = await academyPay(c.order.id);
      window.location.href = pay.redirect_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "خطا در آغاز پرداخت");
      setBusyId(null);
    }
  };

  return (
    <Box>
      <Header />
      <Box sx={{ background: "linear-gradient(180deg,#fdf3f5 0%,#ffffff 100%)", pb: 6 }}>
        <Container maxWidth="md" sx={{ py: { xs: 4, md: 6 }, minHeight: "55vh" }}>
          <Stack direction="row" alignItems="center" spacing={1.5} flexWrap="wrap" useFlexGap>
            <Typography variant="h4" fontWeight={800} color="primary.main">دوره‌های من</Typography>
            <Box flexGrow={1} />
            {user && (
              <>
                <Typography variant="caption" color="text.secondary">
                  {user.display_name} • <span dir="ltr">{user.mobile}</span>
                </Typography>
                <Button size="small" onClick={() => { clearSession(); setUser(null); setCourses([]); setAuthOpen(true); }}>
                  خروج
                </Button>
              </>
            )}
          </Stack>

          {error && <Alert severity="error" sx={{ mt: 2 }} onClose={() => setError(null)}>{error}</Alert>}
          {!courses && <LinearProgress sx={{ mt: 3 }} />}

          {courses && courses.length === 0 && (
            <Paper sx={{ p: 4, mt: 3, textAlign: "center", border: "1px solid #f3dce2" }}>
              <Typography color="text.secondary" mb={2}>هنوز در دوره‌ای ثبت‌نام نکرده‌اید.</Typography>
              <Button component={RouterLink} to="/academy" variant="contained">مشاهده دوره‌های آکادمی</Button>
            </Paper>
          )}

          <Stack spacing={1.5} mt={3}>
            {(courses ?? []).map((c) => {
              const st = STATUS[c.status] ?? { label: c.status, color: "default" as const };
              return (
                <Paper key={c.enrollment_id} sx={{ p: 2.2, border: "1px solid #f3dce2", borderRadius: 3 }}>
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
                    {c.course.cover_image_url && (
                      <Box component="img" src={c.course.cover_image_url} alt={c.course.title}
                        sx={{ width: 110, height: 74, objectFit: "cover", borderRadius: 2 }} />
                    )}
                    <Box flexGrow={1} sx={{ minWidth: 0 }}>
                      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                        <Typography fontWeight={800}>{c.course.title}</Typography>
                        <Chip size="small" label={st.label} color={st.color} variant="outlined" />
                      </Stack>
                      <Typography variant="caption" color="text.secondary">
                        {c.status === "pending"
                          ? `پرداخت معلق — ${fa(c.order?.payable_amount ?? 0)} ریال (سفارش ${c.order?.order_number ?? ""})`
                          : c.course.episodes_count > 0
                            ? `پیشرفت: ${fa(c.watched_count)} از ${fa(c.course.episodes_count)} جلسه`
                            : "به‌زودی"}
                      </Typography>
                    </Box>
                    {c.status === "pending" && c.order ? (
                      <Button variant="contained" disabled={busyId === c.enrollment_id} onClick={() => void resumePayment(c)}>
                        {busyId === c.enrollment_id ? "..." : "تکمیل پرداخت"}
                      </Button>
                    ) : (
                      <Button variant="contained" onClick={() => navigate(`/academy/c/${c.course.slug}`)}>
                        تماشا
                      </Button>
                    )}
                  </Stack>
                </Paper>
              );
            })}
          </Stack>
        </Container>
      </Box>
      <AcademyAuthDialog open={authOpen} onClose={() => setAuthOpen(false)} onDone={load} />
      <Footer />
    </Box>
  );
}
