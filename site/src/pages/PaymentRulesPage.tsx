// فاز ۷۶ (v0.59.0) - صفحهٔ «قوانین پرداخت و استرداد وجه»
//
// صفحهٔ ایستای رسمی سایت برای شفافیت مالی با مراجعین و پیش‌نیاز اعتماد
// درگاه‌های پرداخت (زرین‌پال). لینک آن از فوتر، صفحهٔ رزرو و صفحهٔ نتیجهٔ
// پرداخت در دسترس است.
// فاز ۸۴ — متن‌ها به content/payRules.ts منتقل شد تا از «ویرایشگر صفحات عمومی»
// پنل ادمین ویرایش و منتشر شوند (fallback = پیش‌فرض‌های همان فایل).
import {
  Box, Container, Divider, Paper, Stack, Typography,
} from "@mui/material";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { payRules } from "../content/payRules";

interface RuleSection {
  icon: string;
  title: string;
  items: string[];
}

const SECTIONS: RuleSection[] = payRules.sections as RuleSection[];

export default function PaymentRulesPage() {
  return (
    <Box>
      <Header />
      <Box sx={{ background: "linear-gradient(180deg,#fdf3f5 0%,#ffffff 100%)", pb: 6 }}>
        <Container maxWidth="md" sx={{ py: { xs: 4, md: 6 }, minHeight: "55vh" }}>
          <Typography variant="h4" fontWeight={800} color="primary.main" textAlign="center" mb={1}>
            {payRules.title}
          </Typography>
          <Typography variant="body2" color="text.secondary" textAlign="center" mb={4}>
            {payRules.subtitle}
          </Typography>

          <Paper elevation={0} sx={{
            p: { xs: 2.5, md: 3.5 }, borderRadius: 4, mb: 3,
            background: "linear-gradient(135deg,#fdf3f5,#faf0f2)", border: "1px solid #f0d9df",
          }}>
            <Stack direction="row" spacing={1.5} alignItems="center" mb={1}>
              <Box sx={{ fontSize: 24 }}>📌</Box>
              <Typography variant="h6" fontWeight={800} color="primary.main">{payRules.summaryTitle}</Typography>
            </Stack>
            <Typography variant="body2" sx={{ lineHeight: 2.1 }}>
              {payRules.summary}
            </Typography>
          </Paper>

          {SECTIONS.map((s) => (
            <Paper key={s.title} elevation={0} sx={{
              p: { xs: 2.5, md: 3.5 }, borderRadius: 4, border: "1px solid #f3dce2", mb: 2.5,
            }}>
              <Stack direction="row" spacing={1.5} alignItems="center" mb={1.5}>
                <Box sx={{ fontSize: 26 }}>{s.icon}</Box>
                <Typography variant="h6" fontWeight={800} color="primary.main">{s.title}</Typography>
              </Stack>
              <Stack spacing={1.2} component="ul" sx={{ m: 0, p: 0, listStyle: "none" }}>
                {s.items.map((t, i) => (
                  <Stack key={i} direction="row" spacing={1.2} alignItems="flex-start">
                    <Box sx={{
                      mt: "7px", width: 7, height: 7, borderRadius: "50%",
                      bgcolor: "primary.main", flexShrink: 0,
                    }} />
                    <Typography variant="body2" sx={{ lineHeight: 2 }}>{t}</Typography>
                  </Stack>
                ))}
              </Stack>
            </Paper>
          ))}

          <Paper elevation={0} sx={{
            p: { xs: 2.5, md: 3.5 }, borderRadius: 4, mb: 2,
            background: "linear-gradient(135deg,#fdf3f5,#faf0f2)", border: "1px solid #f0d9df",
          }}>
            <Typography variant="h6" fontWeight={800} color="primary.main" mb={1.5}>{payRules.contactTitle}</Typography>
            <Typography variant="body2" sx={{ lineHeight: 2 }}>
              {payRules.contact}
            </Typography>
          </Paper>

          <Divider sx={{ my: 3 }} />
          <Typography variant="caption" color="text.secondary" display="block" textAlign="center">
            {payRules.footnote}
          </Typography>
        </Container>
      </Box>
      <Footer />
    </Box>
  );
}
