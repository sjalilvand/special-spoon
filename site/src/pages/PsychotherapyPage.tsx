import { Box, Button, Container, Paper, Stack, Typography } from "@mui/material";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { psycho } from "../content/psycho";

export default function PsychotherapyPage() {
  return (
    <Box>
      <Header />
      <Box sx={{ background: "linear-gradient(135deg,#b04a5a 0%,#7a5c8a 100%)", color: "#fff", py: 8 }}>
        <Container>
          <Typography variant="h2" fontWeight={800}>{psycho.title}</Typography>
        </Container>
      </Box>

      <Container sx={{ py: 6 }}>
        <Typography variant="body1" sx={{ lineHeight: 2.2, fontSize: 17 }}>
          {psycho.intro}
        </Typography>
      </Container>

      <Container sx={{ pb: 6 }}>
        <Stack spacing={6}>
          {psycho.treatments.map((t, idx) => {
            const flipped = idx % 2 === 1;
            return (
              <Paper key={t.title} elevation={2} sx={{ p: { xs: 2, md: 4 }, borderRadius: 4 }}>
                <Stack
                  direction={{ xs: "column", md: flipped ? "row-reverse" : "row" }}
                  spacing={3}
                  alignItems="center"
                >
                  {t.img ? (
                    <Box
                      component="img"
                      src={t.img}
                      alt={t.title}
                      sx={{ width: { xs: "100%", md: 340 }, borderRadius: 3, boxShadow: 2 }}
                    />
                  ) : (
                    <Box sx={{
                      width: { xs: "100%", md: 340 }, height: 180, borderRadius: 3,
                      background: "linear-gradient(135deg,#fde7ec 0%,#efe0f0 100%)",
                    }} />
                  )}
                  <Box>
                    <Typography variant="h5" fontWeight={800} color="primary.main" mb={1}>
                      {t.title}
                    </Typography>
                    <Typography variant="body1" sx={{ lineHeight: 2 }}>{t.text}</Typography>
                  </Box>
                </Stack>
              </Paper>
            );
          })}
        </Stack>
      </Container>

      <Box sx={{ bgcolor: "#fdf2f4", py: 8 }}>
        <Container>
          <Typography variant="h4" fontWeight={800} color="primary.main" textAlign="center" mb={5}>
            {psycho.whyTitle}
          </Typography>
          <Box display="grid" gridTemplateColumns={{ xs: "1fr", sm: "1fr 1fr", md: "1fr 1fr 1fr" }} gap={3}>
            {psycho.whyUs.map((w) => (
              <Paper key={w.text} className="hover-lift" elevation={2} sx={{ p: 3, textAlign: "center", borderRadius: 4 }}>
                {w.icon ? (
                  <Box component="img" src={w.icon} alt="" sx={{ height: 90, mx: "auto", mb: 1.5 }} />
                ) : (
                  <Box sx={{ fontSize: 44, mb: 1 }}>✨</Box>
                )}
                <Typography variant="body2" sx={{ lineHeight: 1.9 }}>{w.text}</Typography>
              </Paper>
            ))}
          </Box>
        </Container>
      </Box>

      <Box sx={{ py: 6, textAlign: "center" }}>
        <Button href="/#consult" variant="contained" size="large">
          درخواست مشاوره
        </Button>
      </Box>

      <Footer />
    </Box>
  );
}
