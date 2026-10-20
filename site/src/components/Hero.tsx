import { Box, Button, Container, Stack, Typography } from "@mui/material";
import { texts } from "../content/texts";

const HERO_IMG = "/assets/img-12.png"; // بنر اصلی — از دارایی‌های موجود

export default function Hero() {
  return (
    <Box sx={{ position: "relative", overflow: "hidden", pt: { xs: 5, md: 8 }, pb: { xs: 7, md: 10 } }}>
      {/* تزئینات پس‌زمینه */}
      <Box className="decor-blob" sx={{ width: 420, height: 420, background: "rgba(208,107,128,.20)", top: -140, right: -120 }} />
      <Box className="decor-blob" sx={{ width: 360, height: 360, background: "rgba(138,118,160,.16)", bottom: -160, left: -100 }} />
      <Box className="decor-ring" sx={{ width: 220, height: 220, top: 40, left: "38%", display: { xs: "none", md: "block" } }} />

      <Container maxWidth="lg">
        <Stack direction={{ xs: "column-reverse", md: "row" }} spacing={{ xs: 5, md: 6 }} alignItems="center">
          {/* متن هیرو */}
          <Box sx={{ flex: 1.15 }}>
            <Box
              className="fade-up"
              sx={{
                display: "inline-flex", alignItems: "center", gap: 1,
                bgcolor: "#fff", border: "1px solid #f0d9df", borderRadius: 99,
                px: 2, py: 0.7, mb: 3, boxShadow: "0 6px 18px rgba(168,58,84,.08)",
              }}
            >
              <Box sx={{ width: 8, height: 8, borderRadius: "50%", background: "#a83a54" }} />
              <Typography variant="caption" fontWeight={700} color="primary.main">
                مرکز تخصصی سلامت روان — حضوری و آنلاین
              </Typography>
            </Box>

            <Typography
              className="fade-up-d1"
              variant="h2"
              fontWeight={800}
              sx={{ fontSize: { xs: 34, sm: 44, md: 52 }, lineHeight: 1.4, mb: 2.5 }}
            >
              آرامش، از یک <span className="grad-text">گفت‌وگوی امن</span> آغاز می‌شود
            </Typography>

            <Typography className="fade-up-d2" variant="h6" color="text.secondary" sx={{ fontWeight: 400, lineHeight: 2, maxWidth: 560, mb: 4 }}>
              در مرکز رز، فضایی بدون قضاوت برایتان فراهم شده تا با تکیه بر دانش روز روان‌شناسی
              و تیمی از متخصصان دارای مجوز، مسیر بهبودتان را با اطمینان جلو ببرید — حضوری یا آنلاین.
            </Typography>

            <Stack className="fade-up-d3" direction={{ xs: "column", sm: "row" }} spacing={1.6}>
              <Button href="/booking" variant="contained" size="large" sx={{ px: 4, py: 1.6, fontSize: 16 }}>
                رزرو نوبت آنلاین
              </Button>
              <Button
                href="#services"
                size="large"
                sx={{ px: 4, py: 1.6, fontSize: 16, color: "primary.main", border: "1.5px solid #ecc8d1", bgcolor: "#fff", "&:hover": { bgcolor: "#faf0f3", borderColor: "primary.main" } }}
              >
                آشنایی با خدمات
              </Button>
            </Stack>

            {/* نوار اعتماد */}
            <Stack direction="row" spacing={{ xs: 3, md: 4 }} sx={{ mt: 5, flexWrap: "wrap", rowGap: 2 }}>
              {texts.stats.slice(0, 3).map((s) => (
                <Box key={s.label}>
                  <Typography variant="h5" fontWeight={800} color="primary.main">{s.n}</Typography>
                  <Typography variant="caption" color="text.secondary" fontWeight={600}>{s.label}</Typography>
                </Box>
              ))}
            </Stack>
          </Box>

          {/* کلاژ تصویری */}
          <Box sx={{ flex: 1, position: "relative", width: "100%", maxWidth: 520 }}>
            <Box
              sx={{
                position: "relative", borderRadius: "28px", overflow: "hidden",
                boxShadow: "0 30px 70px rgba(124,39,64,.18)",
                border: "6px solid #fff",
                bgcolor: "#fff",
              }}
            >
              <Box
                component="img"
                src={HERO_IMG}
                alt={texts.brand}
                sx={{ width: "100%", display: "block", minHeight: { xs: 260, md: 380 }, objectFit: "cover" }}
              />
              {/* لایه گرم روی تصویر */}
              <Box sx={{ position: "absolute", inset: 0, background: "linear-gradient(200deg,rgba(168,58,84,.05) 30%,rgba(92,42,53,.28) 100%)" }} />
            </Box>

            {/* چیپ‌های شناور */}
            {texts.heroChips.map((c, i) => (
              <Box
                key={c.label}
                className="float-chip"
                sx={{
                  display: { xs: i === 1 ? "flex" : "none", md: "flex" },
                  alignItems: "center", gap: 1, px: 1.8, py: 1.1,
                  bottom: [undefined, 26, 150][i],
                  right: [undefined, -18, undefined][i],
                  left: [undefined, undefined, -22][i],
                  top: [undefined, undefined, 40][i],
                  animationDelay: `${i * 0.9}s`,
                }}
              >
                <Box component="span" sx={{ fontSize: 20 }}>{c.icon}</Box>
                <Typography variant="caption" fontWeight={700} color="text.primary">{c.label}</Typography>
              </Box>
            ))}
          </Box>
        </Stack>
      </Container>
    </Box>
  );
}
