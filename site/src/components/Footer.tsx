import { Box, Container, Divider, Stack, Typography } from "@mui/material";
import { texts } from "../content/texts";

function ContactLine({ icon, text }: { icon: string; text: string }) {
  return (
    <Stack direction="row" spacing={1.2} alignItems="center">
      <Box component="span" sx={{ fontSize: 16 }}>{icon}</Box>
      <Typography variant="body2" sx={{ opacity: 0.88 }}>{text}</Typography>
    </Stack>
  );
}

export default function Footer() {
  const year = new Intl.DateTimeFormat("fa-IR", { year: "numeric" }).format(new Date());
  return (
    <Box
      id="contact"
      sx={{
        background: "linear-gradient(160deg,#3d1e26 0%,#4d2430 55%,#3a2b3d 100%)",
        color: "#fff", py: { xs: 5, md: 7 }, mt: 2,
      }}
    >
      <Container maxWidth="lg">
        <Stack
          direction={{ xs: "column", md: "row" }}
          spacing={{ xs: 4, md: 5 }}
          justifyContent="space-between"
        >
          {/* برند */}
          <Box sx={{ maxWidth: 320 }}>
            <Stack direction="row" spacing={1.5} alignItems="center" mb={1.5}>
              <Box
                sx={{
                  width: 44, height: 44, borderRadius: "14px",
                  background: "linear-gradient(135deg,#b34460,#8a2f47)",
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22,
                }}
              >
                🌹
              </Box>
              <Typography variant="h6" fontWeight={800}>{texts.brand}</Typography>
            </Stack>
            <Typography variant="body2" sx={{ opacity: 0.85, lineHeight: 2.1 }}>
              {texts.brandSub} — جایی که سلامت روان شما، با دانش روز و قلبی گرم دنبال می‌شود.
            </Typography>
          </Box>

          {/* دسترسی سریع */}
          <Box>
            <Typography variant="subtitle2" sx={{ opacity: 0.65, mb: 1.5, fontWeight: 700 }}>دسترسی سریع</Typography>
            <Stack spacing={1.1}>
              {[
                { href: "#services", label: "خدمات" },
                { href: "#steps", label: "مسیر دریافت نوبت" },
                { href: "#counselors", label: "مشاوران" },
                { href: "#academy", label: "آکادمی رز" },
                { href: "/booking", label: "رزرو نوبت آنلاین" },
                { href: "/panel/", label: "ورود به سامانه مدیریت" },
              ].map((l) => (
                <a key={l.href} href={l.href} style={{ color: "#f2cdd5", textDecoration: "none", fontSize: 14 }}>
                  {l.label}
                </a>
              ))}
            </Stack>
          </Box>

          {/* خدمات */}
          <Box>
            <Typography variant="subtitle2" sx={{ opacity: 0.65, mb: 1.5, fontWeight: 700 }}>خدمات پرطرفدار</Typography>
            <Stack spacing={1.1}>
              {texts.services.slice(0, 5).map((s) => (
                <a key={s.title} href="#services" style={{ color: "#f2cdd5", textDecoration: "none", fontSize: 14 }}>
                  {s.title}
                </a>
              ))}
            </Stack>
          </Box>

          {/* تماس */}
          <Box>
            <Typography variant="subtitle2" sx={{ opacity: 0.65, mb: 1.5, fontWeight: 700 }}>تماس با ما</Typography>
            <Stack spacing={1.4}>
              <ContactLine icon="📞" text={`تلفن: ${texts.footer.phone}`} />
              <ContactLine icon="✉️" text="info@rosepsy.local" />
              <ContactLine icon="📍" text={texts.footer.address} />
              <ContactLine icon="🕘" text={`ساعات کاری: ${texts.footer.hours}`} />
            </Stack>
          </Box>
        </Stack>

        <Divider sx={{ my: 3.5, borderColor: "#ffffff22" }} />
        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={1}>
          <Typography variant="caption" sx={{ opacity: 0.7 }}>
            © {year} {texts.brand} — تمامی حقوق محفوظ است.
          </Typography>
          <Typography variant="caption" sx={{ opacity: 0.55 }}>
            طراحی‌شده برای آرامش شما 🌿
          </Typography>
        </Stack>
      </Container>
    </Box>
  );
}
