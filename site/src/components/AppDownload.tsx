import { Box, Button, Container, Paper, Stack, Typography } from "@mui/material";
import SectionTitle from "./SectionTitle";
import { texts } from "../content/texts";

/** فاز ۶۸ - بخش دانلود اپلیکیشن اندروید رزپسی با QR روی صفحهٔ اصلی */
export default function AppDownload() {
  const t = texts.appDownload;
  return (
    <Box sx={{ py: { xs: 6, md: 9 }, background: "linear-gradient(180deg,#faf5f6 0%,#ffffff 100%)" }}>
      <Container maxWidth="lg">
        <SectionTitle label={t.label} title={t.title} sub={t.sub} />
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", md: "1.45fr 1fr" },
            gap: { xs: 2.5, md: 4 },
            alignItems: "stretch",
          }}
        >
          <Paper
            elevation={0}
            sx={{
              p: { xs: 2.6, md: 3.4 },
              borderRadius: "20px",
              border: "1px solid #f3e2e7",
              background: "linear-gradient(160deg,#ffffff 0%,#faf1f3 100%)",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
            }}
          >
            <Stack spacing={1.5}>
              {t.points.map((p) => (
                <Stack key={p} direction="row" spacing={1.4} alignItems="center">
                  <Box sx={{ width: 9, height: 9, borderRadius: "50%", bgcolor: "primary.main", flexShrink: 0 }} />
                  <Typography variant="body1" sx={{ lineHeight: 1.9 }}>{p}</Typography>
                </Stack>
              ))}
            </Stack>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.6} mt={2.8}>
              <Button
                component="a"
                href="/app/rosepsy-1.0.0.apk"
                download="rosepsy-1.0.0.apk"
                size="large"
                sx={{ bgcolor: "primary.main", color: "#fff", fontWeight: 800, px: 3.4, "&:hover": { bgcolor: "primary.dark" } }}
              >
                {t.download}
              </Button>
              <Button
                href="/booking"
                size="large"
                variant="outlined"
                sx={{ px: 3.2, color: "primary.main", borderColor: "#e5c3cc", "&:hover": { borderColor: "primary.main", bgcolor: "#fdf1f4" } }}
              >
                رزرو نوبت آنلاین
              </Button>
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: "block", lineHeight: 2 }}>
              {t.installNote}
            </Typography>
          </Paper>
          <Paper
            elevation={0}
            sx={{
              p: { xs: 2.6, md: 3 },
              borderRadius: "20px",
              border: "1px solid #f3e2e7",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 1.2,
              textAlign: "center",
            }}
          >
            <Box
              component="img"
              src="/app/qr.svg"
              alt={t.qrHint}
              sx={{ width: { xs: 180, md: 215 }, height: "auto", borderRadius: "12px", border: "1px solid #f0dfe4" }}
            />
            <Typography variant="body2" fontWeight={800}>{t.qrHint}</Typography>
            <Typography variant="caption" color="text.secondary">{t.qrSub}</Typography>
          </Paper>
        </Box>
      </Container>
    </Box>
  );
}
