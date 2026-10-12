import { Box, Container, Divider, Stack, Typography } from "@mui/material";
import { CONTACT_ICONS } from "../content/assets";
import { texts } from "../content/texts";

function ContactLine({ icon, text }: { icon: string; text: string }) {
  return (
    <Stack direction="row" spacing={1} alignItems="center">
      <Box component="img" src={icon} alt="" sx={{ width: 16, height: 16, opacity: 0.9 }} />
      <Typography variant="body2" sx={{ opacity: 0.9 }}>{text}</Typography>
    </Stack>
  );
}

export default function Footer() {
  const year = new Intl.DateTimeFormat("fa-IR", { year: "numeric" }).format(new Date());
  return (
    <Box id="contact" sx={{ background: "linear-gradient(135deg,#5a2a35 0%,#43202a 100%)", color: "#fff", py: 6, mt: 4 }}>
      <Container>
        <Stack direction={{ xs: "column", md: "row" }} spacing={4} justifyContent="space-between">
          <Box>
            <Stack direction="row" spacing={1.5} alignItems="center" mb={1}>
              <Box component="img" src="/assets/img-4.png" alt={texts.brand} sx={{ height: 40, bgcolor: "#fff", borderRadius: 2, p: 0.5 }} />
              <Typography variant="h6" fontWeight={800}>{texts.brand}</Typography>
            </Stack>
            <Typography variant="body2" sx={{ opacity: 0.85, maxWidth: 320 }}>
              {texts.brandSub} — مسیر بهبود شما، با تیمی که کنارتان می‌ماند.
            </Typography>
          </Box>
          <Stack spacing={1.2}>
            <ContactLine icon={CONTACT_ICONS.phone} text={`تلفن: ${texts.footer.phone}`} />
            <ContactLine icon={CONTACT_ICONS.mail} text="info@rosepsy.local" />
            <ContactLine icon={CONTACT_ICONS.location} text={texts.footer.address} />
            <Typography variant="body2" sx={{ opacity: 0.85 }}>ساعات کاری: {texts.footer.hours}</Typography>
          </Stack>
          <Stack spacing={1}>
            <Typography variant="subtitle2" sx={{ opacity: 0.7 }}>دسترسی سریع</Typography>
            <a href="#services" style={{ color: "#ffd7de", textDecoration: "none" }}>خدمات</a>
            <a href="#counselors" style={{ color: "#ffd7de", textDecoration: "none" }}>مشاوران</a>
            <a href="/panel" style={{ color: "#ffd7de", textDecoration: "none" }}>ورود به سامانه مدیریت</a>
          </Stack>
        </Stack>
        <Divider sx={{ my: 3, borderColor: "#ffffff33" }} />
        <Typography variant="caption" sx={{ opacity: 0.7 }}>
          © {year} {texts.brand} — تمامی حقوق محفوظ است.
        </Typography>
      </Container>
    </Box>
  );
}
