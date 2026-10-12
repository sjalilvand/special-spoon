import { Box, Button, Container, Stack, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { SUGGESTED } from "../content/assets";
import { texts } from "../content/texts";

export default function Hero() {
  const slides = texts.hero;
  const [i, setI] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setI((p) => (p + 1) % slides.length), 6000);
    return () => clearInterval(t);
  }, [slides.length]);

  const img = SUGGESTED.hero.length > 0 ? SUGGESTED.hero[i % SUGGESTED.hero.length] : null;
  const bg = img
    ? { backgroundImage: `url(${img})` }
    : { background: "linear-gradient(135deg,#fde7ec 0%,#f6d5e0 55%,#efe0f0 100%)" };

  return (
    <Box sx={{ position: "relative", minHeight: 540, ...bg, backgroundSize: "cover", backgroundPosition: "center", overflow: "hidden" }}>
      {/* پوشش سبک: سمت متن روشن‌تر، سمت تصویر شفاف‌تر */}
      <Box sx={{
        position: "absolute", inset: 0,
        background: "linear-gradient(270deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.25) 45%, rgba(255,251,251,0.88) 100%)",
      }} />
      {/* دایره‌های تزئینی */}
      <Box sx={{ position: "absolute", width: 320, height: 320, borderRadius: "50%", background: "rgba(176,74,90,0.10)", top: -90, left: -70, filter: "blur(2px)" }} />
      <Box sx={{ position: "absolute", width: 200, height: 200, borderRadius: "50%", background: "rgba(122,92,138,0.10)", bottom: -60, right: "28%", filter: "blur(2px)" }} />

      <Container sx={{ position: "relative", py: 13 }}>
        <Stack spacing={2} alignItems={{ xs: "center", md: "flex-start" }} textAlign={{ xs: "center", md: "right" }}>
          <Typography
            variant="caption"
            sx={{ bgcolor: "rgba(255,255,255,0.75)", color: "primary.main", px: 2, py: 0.5, borderRadius: 99, fontWeight: 700 }}
          >
            {texts.brandSub}
          </Typography>
          <Typography variant="h2" fontWeight={800} color="primary.dark" sx={{ textShadow: "0 1px 0 rgba(255,255,255,.6)" }}>
            {slides[i].title}
          </Typography>
          <Typography variant="h6" color="text.primary" sx={{ maxWidth: 620 }}>
            {slides[i].sub}
          </Typography>
          <Stack direction="row" spacing={1.5} mt={2}>
            <Button href="#consult" variant="contained" size="large">{slides[i].cta}</Button>
            <Button href="#services" variant="outlined" size="large" sx={{ bgcolor: "rgba(255,255,255,0.7)" }}>
              خدمات ما
            </Button>
          </Stack>
        </Stack>
        <Stack direction="row" spacing={1} justifyContent={{ xs: "center", md: "flex-start" }} mt={7}>
          {slides.map((_, idx) => (
            <Box
              key={idx}
              onClick={() => setI(idx)}
              sx={{
                width: idx === i ? 28 : 10,
                height: 10,
                borderRadius: 99,
                bgcolor: idx === i ? "primary.main" : "primary.light",
                cursor: "pointer",
                transition: "all .3s",
              }}
            />
          ))}
        </Stack>
      </Container>
    </Box>
  );
}
