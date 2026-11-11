// فاز ۸۶ - آکادمی رز: ویترین عمومی دوره‌ها (فهرست + فیلتر دسته)
import { Box, Card, CardContent, CardMedia, Chip, Container, Paper, Skeleton, Stack, Typography, Button } from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { CART_EVENT, addToCart, cartCount, fetchAcademyCourses, getStoredUser, type AcademyCourseSummary } from "../academy";

const fa = (n: number) => n.toLocaleString("fa-IR");

function PriceBadge({ c }: { c: AcademyCourseSummary }) {
  if (c.is_free) return <Chip size="small" color="success" label="رایگان" sx={{ fontWeight: 700 }} />;
  return <Chip size="small" label={`${fa(c.price_amount)} ریال`} sx={{ fontWeight: 700, bgcolor: "#fbe9ee", color: "primary.main" }} />;
}

export default function AcademyPage() {
  const [courses, setCourses] = useState<AcademyCourseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [topic, setTopic] = useState<string>("");
  const [cart, setCart] = useState(0);
  const [user, setUser] = useState(getStoredUser());

  useEffect(() => {
    document.title = "آکادمی رز | آموزش روان‌شناسی";
    fetchAcademyCourses()
      .then(setCourses)
      .catch((e) => setError(e instanceof Error ? e.message : "خطا"));
    setCart(cartCount());
    const onCart = () => setCart(cartCount());
    window.addEventListener(CART_EVENT, onCart);
    const iv = setInterval(() => setUser(getStoredUser()), 1500);
    return () => {
      window.removeEventListener(CART_EVENT, onCart);
      clearInterval(iv);
    };
  }, []);

  const topics = useMemo(() => {
    const set = new Map<string, number>();
    (courses ?? []).forEach((c) => {
      if (c.topic_name) set.set(c.topic_name, (set.get(c.topic_name) ?? 0) + 1);
    });
    return [...set.keys()];
  }, [courses]);

  const list = (courses ?? []).filter((c) => !topic || c.topic_name === topic);

  return (
    <Box>
      <Header />
      <Box sx={{ background: "linear-gradient(180deg,#fdf3f5 0%,#ffffff 100%)", pb: 6 }}>
        <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 }, minHeight: "55vh" }}>
          <Stack direction="row" alignItems="center" spacing={1.5} flexWrap="wrap" useFlexGap>
            <Typography variant="h4" fontWeight={800} color="primary.main">آکادمی رز</Typography>
            <Chip size="small" label="دوره‌های ویدیویی روان‌شناسی" variant="outlined" />
            <Box flexGrow={1} />
            {user && (
              <Button component={RouterLink} to="/academy/my" variant="outlined" size="small">
                دوره‌های من
              </Button>
            )}
            <Button component={RouterLink} to="/academy/cart" variant="contained" size="small">
              سبد خرید{cart > 0 ? ` (${fa(cart)})` : ""}
            </Button>
          </Stack>
          <Typography variant="body2" color="text.secondary" mt={1} sx={{ lineHeight: 2 }}>
            آموزش گام‌به‌گام با ویدیو؛ جلسه‌های معرفی رایگان هستند و پس از خرید، ویدیوها بسته به انتشار پلکانی هر دوره برای شما باز می‌شود.
          </Typography>

          {topics.length > 1 && (
            <Stack direction="row" spacing={1} mt={2.5} flexWrap="wrap" useFlexGap>
              <Chip label="همه" onClick={() => setTopic("")} color={topic === "" ? "primary" : "default"} variant={topic === "" ? "filled" : "outlined"} />
              {topics.map((t) => (
                <Chip key={t} label={t} onClick={() => setTopic(t)} color={topic === t ? "primary" : "default"} variant={topic === t ? "filled" : "outlined"} />
              ))}
            </Stack>
          )}

          {error && (
            <Paper sx={{ p: 3, mt: 3, textAlign: "center", color: "error.main", border: "1px solid #f0d9df" }}>
              {error}
            </Paper>
          )}

          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2,1fr)", md: "repeat(3,1fr)" }, gap: { xs: 2, md: 3 }, mt: 3 }}>
            {!courses && Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} variant="rounded" height={280} />)}
            {list.map((c) => (
              <Card
                key={c.id}
                elevation={0}
                sx={{
                  height: "100%", borderRadius: "18px", border: "1px solid #f3e2e7",
                  display: "flex", flexDirection: "column", overflow: "hidden",
                  transition: "transform .2s ease, box-shadow .2s ease",
                  "&:hover": { transform: "translateY(-4px)", boxShadow: "0 14px 34px rgba(124,39,64,.12)" },
                }}
              >
                <Box component={RouterLink} to={`/academy/c/${c.slug}`} sx={{ display: "block", textDecoration: "none" }}>
                  {c.cover_image_url ? (
                    <CardMedia component="img" image={c.cover_image_url} alt={c.title} sx={{ height: 170, objectFit: "cover" }} />
                  ) : (
                    <Box sx={{
                      height: 170, display: "flex", alignItems: "center", justifyContent: "center",
                      background: "linear-gradient(150deg,#7c2740,#a83a54 60%,#5c4a6e)", color: "#fff", fontSize: 40,
                    }}>
                      ✦
                    </Box>
                  )}
                </Box>
                <CardContent sx={{ p: 2.4, display: "flex", flexDirection: "column", gap: 1, flexGrow: 1 }}>
                  <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap" useFlexGap>
                    <PriceBadge c={c} />
                    {c.free_episodes_count > 0 && (
                      <Chip size="small" variant="outlined" label={`${fa(c.free_episodes_count)} جلسه رایگان`} />
                    )}
                  </Stack>
                  <Typography variant="h6" fontWeight={800} component={RouterLink} to={`/academy/c/${c.slug}`}
                    sx={{ textDecoration: "none", color: "text.primary", "&:hover": { color: "primary.main" } }}>
                    {c.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.9, flexGrow: 1 }}>
                    {c.summary ?? ""}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {c.episodes_count > 0 ? `${fa(c.episodes_count)} جلسه • ${fa(c.total_minutes)} دقیقه` : "به‌زودی"}
                    {c.topic_name ? ` • ${c.topic_name}` : ""}
                  </Typography>
                  <Stack direction="row" spacing={1} mt={0.5}>
                    <Button size="small" component={RouterLink} to={`/academy/c/${c.slug}`} variant="contained" fullWidth>
                      مشاهده دوره
                    </Button>
                  </Stack>
                  {!c.is_free && (
                    <Button size="small" variant="outlined"
                      onClick={() => { addToCart(c.id); setCart(cartCount()); }}>
                      افزودن به سبد
                    </Button>
                  )}
                </CardContent>
              </Card>
            ))}
          </Box>

          {courses && list.length === 0 && !error && (
            <Paper sx={{ p: 4, mt: 3, textAlign: "center" }}>
              <Typography variant="body1" color="text.secondary">
                هنوز دوره‌ای منتشر نشده است — به‌زودی دوره‌های آکادمی رز اینجا قرار می‌گیرد.
              </Typography>
            </Paper>
          )}
        </Container>
      </Box>
      <Footer />
    </Box>
  );
}
