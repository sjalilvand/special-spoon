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
    <Box sx={{ position: "relative", minHeight: 460, ...bg, backgroundSize: "cover", backgroundPosition: "center" }}>
      <Box sx={{ position: "absolute", inset: 0, background: "rgba(255,255,255,0.55)" }} />
      <Container sx={{ position: "relative", py: 12 }}>
        <Stack spacing={2} alignItems={{ xs: "center", md: "flex-start" }} textAlign={{ xs: "center", md: "right" }}>
          <Typography variant="h3" fontWeight={800} color="primary.main">
            {slides[i].title}
          </Typography>
          <Typography variant="h6" color="text.primary" sx={{ maxWidth: 640 }}>
            {slides[i].sub}
          </Typography>
          <Button href="#consult" variant="contained" size="large" sx={{ mt: 2 }}>
            {slides[i].cta}
          </Button>
        </Stack>
        <Stack direction="row" spacing={1} justifyContent="center" mt={6}>
          {slides.map((_, idx) => (
            <Box
              key={idx}
              onClick={() => setI(idx)}
              sx={{
                width: idx === i ? 26 : 10,
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
