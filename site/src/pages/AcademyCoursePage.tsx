// فاز ۸۶ - آکادمی رز: صفحهٔ دوره — ویترین، جلسات (رایگان/قفل/انتشار پلکانی)،
// پخش ویدیو با کنترل دسترسی سمت سرور، افزودن به سبد و خرید مستقیم
import {
  Alert, Box, Button, Chip, Container, Divider, LinearProgress, Paper, Snackbar,
  Stack, Typography,
} from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import { Link as RouterLink, useNavigate, useParams } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import AcademyAuthDialog from "../components/AcademyAuthDialog";
import {
  addToCart, cartCount, fetchAcademyCourse, fetchAcademyMe, fetchAcademyMyCourse,
  fetchVideoAccess, getStoredUser, getToken, markWatched,
  CART_EVENT,
  type AcademyCourseDetail, type AcademyMyCourse, type MyCourseDetail,
} from "../academy";

const fa = (n: number) => n.toLocaleString("fa-IR");

type Episode = AcademyCourseDetail["episodes"][number] & { watched?: boolean; access?: string };

function EpisodePlayer({ sessionId, onClose }: { sessionId: string; onClose: () => void }) {
  const [video, setVideo] = useState<{ kind: "mp4" | "embed"; url: string; title: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [watched, setWatched] = useState(false);

  useEffect(() => {
    setVideo(null); setError(null); setWatched(false);
    fetchVideoAccess(sessionId)
      .then((v) => setVideo(v))
      .catch((e) => setError(e instanceof Error ? e.message : "خطا"));
  }, [sessionId]);

  return (
    <Paper sx={{ position: "fixed", inset: 0, zIndex: 1300, bgcolor: "rgba(20,10,14,.94)", p: { xs: 1.5, md: 4 }, overflow: "auto" }}>
      <Container maxWidth="md">
        <Stack direction="row" alignItems="center" spacing={1} mb={2}>
          <Typography variant="h6" fontWeight={800} color="#fff" flexGrow={1}>
            {video?.title ?? "در حال بارگذاری ویدیو..."}
          </Typography>
          <Button variant="contained" size="small" onClick={onClose}>بستن ✕</Button>
        </Stack>
        {error && <Alert severity="error">{error}</Alert>}
        {video && video.kind === "mp4" && (
          <Box component="video" controls autoPlay src={video.url}
            sx={{ width: "100%", borderRadius: 3, bgcolor: "#000", maxHeight: "72vh" }} />
        )}
        {video && video.kind === "embed" && (
          <Box sx={{ position: "relative", paddingTop: "56.25%", borderRadius: 3, overflow: "hidden" }}>
            <Box component="iframe" src={video.url} title={video.title} allowFullScreen
              sx={{ position: "absolute", inset: 0, width: "100%", height: "100%", border: 0, borderRadius: 3 }} />
          </Box>
        )}
        {video && (
          <Stack direction="row" spacing={1} mt={2} justifyContent="center">
            <Button variant={watched ? "contained" : "outlined"} size="small"
              onClick={() => { setWatched(!watched); void markWatched(sessionId, !watched); }}>
              {watched ? "دیده شد ✓" : "علامت‌گذاری «دیده شد»"}
            </Button>
          </Stack>
        )}
      </Container>
    </Paper>
  );
}

function EpisodeRow({ ep, onPlay }: { ep: Episode; onPlay: (id: string) => void }) {
  const access = ep.access ?? (ep.is_free ? "free" : "locked");
  const playable = ep.has_video && (access === "free" || access === "ready");
  const lockedByDrip = access === "coming_soon";
  return (
    <Stack direction="row" alignItems="center" spacing={1.5}
      sx={{
        p: 1.6, borderRadius: 2.5, border: "1px solid #f3dce2", mb: 1,
        bgcolor: playable ? "#fff" : "#faf6f7",
      }}>
      <Box sx={{
        width: 38, height: 38, borderRadius: "50%", flexShrink: 0, display: "flex",
        alignItems: "center", justifyContent: "center", fontSize: 17,
        bgcolor: playable ? "rgba(168,58,84,.1)" : "#f1e7ea", color: playable ? "primary.main" : "#b9a7ae",
      }}>
        {playable ? "▶" : lockedByDrip ? "⏳" : "🔒"}
      </Box>
      <Box flexGrow={1} sx={{ minWidth: 0 }}>
        <Typography variant="body2" fontWeight={700} noWrap>{ep.title}</Typography>
        <Typography variant="caption" color="text.secondary">
          {fa(ep.duration_minutes)} دقیقه
          {ep.is_free ? " • پیش‌نمایش رایگان" : ""}
          {lockedByDrip ? ` • در دسترس از ${fa(ep.release_after_days)} روز پس از خرید` : ""}
          {!ep.has_video ? " • ویدیو به‌زودی" : ""}
        </Typography>
        {ep.description && (
          <Typography variant="caption" color="text.secondary" display="block" sx={{ lineHeight: 1.8 }}>
            {ep.description}
          </Typography>
        )}
      </Box>
      {playable && (
        <Button size="small" variant="outlined" onClick={() => onPlay(ep.id)}>
          پخش
        </Button>
      )}
      {ep.watched && <Chip size="small" color="success" label="دیده شد" variant="outlined" />}
    </Stack>
  );
}

export default function AcademyCoursePage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [course, setCourse] = useState<AcademyCourseDetail | null>(null);
  const [mine, setMine] = useState<MyCourseDetail | null>(null);
  const [myEntry, setMyEntry] = useState<AcademyMyCourse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [playSession, setPlaySession] = useState<string | null>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [trailerOpen, setTrailerOpen] = useState(false);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [cart, setCart] = useState(0);
  const [user, setUser] = useState(getStoredUser());
  const [afterAuth, setAfterAuth] = useState<"cart" | "checkout" | null>(null);

  const load = useCallback(async () => {
    if (!slug) return;
    try {
      const c = await fetchAcademyCourse(slug);
      setCourse(c);
      document.title = `${c.title} | آکادمی رز`;
      if (getToken()) {
        try {
          const m = await fetchAcademyMyCourse(c.id);
          setMine(m);
        } catch {
          setMine(null);
        }
        try {
          const me = await fetchAcademyMe();
          setMyEntry(me.courses.find((x) => x.course.id === c.id) ?? null);
        } catch {
          setMyEntry(null);
        }
      } else {
        setMine(null);
        setMyEntry(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "خطا");
    }
  }, [slug]);

  useEffect(() => {
    window.scrollTo(0, 0);
    void load();
    setCart(cartCount());
    const onCart = () => setCart(cartCount());
    window.addEventListener(CART_EVENT, onCart);
    return () => window.removeEventListener(CART_EVENT, onCart);
  }, [load]);

  // بازآخوانی وضعیت پس از ورود
  useEffect(() => {
    if (user !== null) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  const enrolled = mine != null && (mine.enrollment_status === "active" || mine.enrollment_status === "completed");
  const pendingEntry = myEntry?.status === "pending" ? myEntry : null;

  const requireAuthThen = (mode: "cart" | "checkout") => {
    if (!course) return;
    if (!getToken()) {
      setAfterAuth(mode);
      setAuthOpen(true);
      return;
    }
    if (mode === "cart") {
      addToCart(course.id);
      setCart(cartCount());
      setOkMsg("به سبد خرید اضافه شد");
    } else {
      addToCart(course.id);
      navigate("/academy/cart?buy=1");
    }
  };

  if (error) {
    return (
      <Box>
        <Header />
        <Container maxWidth="md" sx={{ py: 8, textAlign: "center" }}>
          <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
          <Button component={RouterLink} to="/academy" variant="contained">بازگشت به آکادمی</Button>
        </Container>
        <Footer />
      </Box>
    );
  }

  return (
    <Box>
      <Header />
      {!course && <LinearProgress sx={{ mt: -1 }} />}
      {course && (
        <Box sx={{ background: "linear-gradient(180deg,#fdf3f5 0%,#ffffff 100%)", pb: 6 }}>
          {/* قهرمان دوره */}
          <Container maxWidth="lg" sx={{ py: { xs: 4, md: 5 } }}>
            <Button component={RouterLink} to="/academy" size="small" sx={{ mb: 2 }}>
              ← بازگشت به آکادمی
            </Button>
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1.6fr 1fr" }, gap: { xs: 3, md: 4 } }}>
              <Box>
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap mb={1.5}>
                  {course.is_free
                    ? <Chip color="success" size="small" label="رایگان" sx={{ fontWeight: 700 }} />
                    : <Chip size="small" label={`${fa(course.price_amount)} ریال`} sx={{ fontWeight: 700, bgcolor: "#fbe9ee", color: "primary.main" }} />}
                  {course.free_episodes_count > 0 && (
                    <Chip size="small" variant="outlined" label={`${fa(course.free_episodes_count)} جلسه رایگان`} />
                  )}
                  {course.topic_name && <Chip size="small" variant="outlined" label={course.topic_name} />}
                </Stack>
                <Typography variant="h3" fontWeight={800} sx={{ fontSize: { xs: 28, md: 40 } }}>
                  {course.title}
                </Typography>
                <Typography variant="body1" color="text.secondary" mt={1.5} sx={{ lineHeight: 2.1 }}>
                  {course.summary ?? ""}
                </Typography>
                {course.trailer_url && (
                  <Button variant="outlined" sx={{ mt: 2 }} onClick={() => setTrailerOpen(true)}>
                    ▶ تماشای ویدیوی معرفی
                  </Button>
                )}
              </Box>
              <Box>
                {course.cover_image_url ? (
                  <Box component="img" src={course.cover_image_url} alt={course.title}
                    sx={{ width: "100%", borderRadius: "20px", border: "1px solid #f3dce2", objectFit: "cover", maxHeight: 300 }} />
                ) : (
                  <Box sx={{
                    height: 220, borderRadius: "20px", display: "flex", alignItems: "center", justifyContent: "center",
                    background: "linear-gradient(150deg,#7c2740,#a83a54 60%,#5c4a6e)", color: "#fff", fontSize: 56,
                  }}>✦</Box>
                )}
                <Paper elevation={0} sx={{ mt: 2, p: 2.4, borderRadius: 4, border: "1px solid #f3dce2" }}>
                  {enrolled ? (
                    <Stack spacing={1.2}>
                      <Chip color="success" label={mine?.enrollment_status === "completed" ? "دوره را تکمیل کرده‌اید ✓" : "ثبت‌نام شما فعال است ✓"} />
                      <Typography variant="caption" color="text.secondary">
                        پیشرفت شما: {fa(mine?.episodes.filter((e) => e.watched).length ?? 0)} از {fa(course.episodes_count)} جلسه
                      </Typography>
                    </Stack>
                  ) : pendingEntry ? (
                    <Stack spacing={1.2}>
                      <Alert severity="warning" sx={{ fontSize: 13 }}>ثبت‌نام شما در انتظار پرداخت است</Alert>
                      <Button variant="contained" onClick={() => navigate(`/academy/cart?order=${pendingEntry.order?.id ?? ""}`)}>
                        تکمیل پرداخت ({fa(pendingEntry.order?.payable_amount ?? 0)} ریال)
                      </Button>
                    </Stack>
                  ) : (
                    <Stack spacing={1.2}>
                      {course.is_free ? (
                        <>
                          <Typography variant="body2" color="text.secondary">
                            این دوره رایگان است؛ با ورود بلافاصله ثبت‌نام می‌شوید.
                          </Typography>
                          <Button variant="contained" size="large" onClick={() => requireAuthThen("checkout")}>
                            ثبت‌نام رایگان
                          </Button>
                        </>
                      ) : (
                        <>
                          <Typography variant="h6" fontWeight={800} color="primary.main">
                            {fa(course.price_amount)} ریال
                          </Typography>
                          <Button variant="contained" size="large" onClick={() => requireAuthThen("checkout")}>
                            خرید دوره
                          </Button>
                          <Button variant="outlined" onClick={() => requireAuthThen("cart")}>
                            افزودن به سبد
                          </Button>
                        </>
                      )}
                    </Stack>
                  )}
                  <Divider sx={{ my: 1.5 }} />
                  <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 2 }} component="div">
                    • {course.episodes_count > 0 ? `${fa(course.episodes_count)} جلسه ویدیویی` : "ویدیوها به‌زودی"}
                    {course.total_minutes > 0 ? ` (${fa(course.total_minutes)} دقیقه)` : ""}
                    <br />• جلسه‌های «پیش‌نمایش رایگان» بدون خرید قابل تماشا هستند
                    <br />• پس از پرداخت موفق، دسترسی بلافاصله فعال می‌شود
                  </Typography>
                  <Stack direction="row" spacing={1} mt={1}>
                    <Button component={RouterLink} to="/academy/cart" size="small">سبد خرید{cart > 0 ? ` (${fa(cart)})` : ""}</Button>
                    {user && <Button component={RouterLink} to="/academy/my" size="small">دوره‌های من</Button>}
                  </Stack>
                </Paper>
              </Box>
            </Box>

            {/* توضیحات */}
            {course.description && (
              <Paper elevation={0} sx={{ mt: 4, p: { xs: 2.5, md: 3.5 }, borderRadius: 4, border: "1px solid #f3dce2" }}>
                <Typography variant="h6" fontWeight={800} color="primary.main" mb={1.5}>درباره این دوره</Typography>
                <Typography variant="body2" sx={{ lineHeight: 2.2, whiteSpace: "pre-line" }}>
                  {course.description}
                </Typography>
              </Paper>
            )}

            {/* جلسات */}
            <Paper elevation={0} sx={{ mt: 3, p: { xs: 2.5, md: 3.5 }, borderRadius: 4, border: "1px solid #f3dce2" }}>
              <Typography variant="h6" fontWeight={800} color="primary.main" mb={1.5}>
                جلسات دوره {enrolled ? "(دسترسی شما فعال است)" : ""}
              </Typography>
              {course.episodes.length === 0 && (
                <Typography variant="body2" color="text.secondary">جلسه‌ای ثبت نشده است.</Typography>
              )}
              {(mine?.episodes ?? course.episodes).map((ep) => (
                <EpisodeRow key={ep.id} ep={ep} onPlay={(id) => setPlaySession(id)} />
              ))}
              {!enrolled && course.episodes.some((e) => !e.is_free) && (
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                  🔒 جلسه‌های قفل‌شده پس از خرید و طبق «انتشار پلکانی» هر جلسه باز می‌شوند.
                </Typography>
              )}
            </Paper>
          </Container>
        </Box>
      )}

      {playSession && <EpisodePlayer sessionId={playSession} onClose={() => { setPlaySession(null); void load(); }} />}

      {trailerOpen && course?.trailer_url && (
        <Paper sx={{ position: "fixed", inset: 0, zIndex: 1300, bgcolor: "rgba(20,10,14,.94)", p: { xs: 1.5, md: 4 }, overflow: "auto" }}>
          <Container maxWidth="md">
            <Stack direction="row" justifyContent="flex-end" mb={2}>
              <Button variant="contained" size="small" onClick={() => setTrailerOpen(false)}>بستن ✕</Button>
            </Stack>
            {/\.(mp4|webm|m3u8)(\?|$)/i.test(course.trailer_url) ? (
              <Box component="video" controls autoPlay src={course.trailer_url}
                sx={{ width: "100%", borderRadius: 3, bgcolor: "#000", maxHeight: "72vh" }} />
            ) : (
              <Box sx={{ position: "relative", paddingTop: "56.25%" }}>
                <Box component="iframe" src={course.trailer_url} title="تریلر" allowFullScreen
                  sx={{ position: "absolute", inset: 0, width: "100%", height: "100%", border: 0, borderRadius: 3 }} />
              </Box>
            )}
          </Container>
        </Paper>
      )}

      <AcademyAuthDialog
        open={authOpen}
        onClose={() => setAuthOpen(false)}
        onDone={() => {
          setUser(getStoredUser());
          if (afterAuth === "cart") setOkMsg("به سبد خرید اضافه شد");
          if (afterAuth === "checkout") navigate("/academy/cart?buy=1");
          setAfterAuth(null);
          void load();
        }}
      />

      <Snackbar open={!!okMsg} autoHideDuration={3000} onClose={() => setOkMsg(null)}>
        <Alert severity="success" onClose={() => setOkMsg(null)}>{okMsg}</Alert>
      </Snackbar>
      <Footer />
    </Box>
  );
}
