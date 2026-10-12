import { Box, Container, Divider, Stack, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { texts } from "../content/texts";

export default function Footer() {
  const year = new Intl.DateTimeFormat("fa-IR", { year: "numeric" }).format(new Date());
  return (
    <Box sx={{ bgcolor: "#5a2a35", color: "#fff", py: 5, mt: 4 }}>
      <Container>
        <Stack direction={{ xs: "column", md: "row" }} spacing={3} justifyContent="space-between">
          <Box>
            <Typography variant="h6" fontWeight={800}>
              {texts.brand}
            </Typography>
            <Typography variant="body2" sx={{ opacity: 0.85 }}>
              {texts.brandSub}
            </Typography>
          </Box>
          <Stack spacing={0.5}>
            <Typography variant="body2">تلفن: {texts.footer.phone}</Typography>
            <Typography variant="body2">{texts.footer.address}</Typography>
            <Typography variant="body2">ساعات کاری: {texts.footer.hours}</Typography>
          </Stack>
          <Stack spacing={1}>
            <RouterLink to="/panel" style={{ color: "#ffd7de", textDecoration: "none" }}>
              ورود به سامانه مدیریت
            </RouterLink>
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
