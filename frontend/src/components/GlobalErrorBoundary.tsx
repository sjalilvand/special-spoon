// فاز ۵۱: مرز خطا (Error Boundary) سراسری — به‌جای «صفحهٔ سفید» هنگام کرش
// رندر هر مسیر، پیام فارسیِ قابل‌فهم + دکمهٔ تازه‌سازی نمایش داده می‌شود.
// علت ساخت: کرش «items.find is not a function» در مانیتورینگ فرایندها کل
// درخت React را می‌انداخت و کاربر صفحهٔ خالی می‌دید.
import { Component, ErrorInfo, ReactNode } from "react";
import { Box, Button, Paper, Stack, Typography } from "@mui/material";
import ErrorOutlineRoundedIcon from "@mui/icons-material/ErrorOutlineRounded";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

class GlobalErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("Rosepsy panel render error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <Box minHeight="60vh" display="flex" alignItems="center" justifyContent="center" p={3}>
          <Paper variant="outlined" sx={{ p: 4, maxWidth: 560, textAlign: "center" }}>
            <ErrorOutlineRoundedIcon color="error" sx={{ fontSize: 48, mb: 1 }} />
            <Typography variant="h6" fontWeight={800} gutterBottom>
              نمایش این بخش با خطا مواجه شد
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              مشکلی در نمایش این صفحه پیش آمد؛ سایر بخش‌ها از منوی بالا در دسترس‌اند.
              اگر تکرار شد، صفحه را تازه‌سازی کنید یا با پشتیبانی تماس بگیرید.
            </Typography>
            <Typography
              variant="caption" color="text.disabled" sx={{ display: "block", mb: 2, direction: "ltr" }}
            >
              {this.state.error.message}
            </Typography>
            <Stack direction="row" spacing={1.5} justifyContent="center">
              <Button variant="contained" onClick={() => window.location.reload()}>
                تازه‌سازی صفحه
              </Button>
              <Button variant="outlined" onClick={() => this.setState({ error: null })}>
                تلاش مجدد
              </Button>
            </Stack>
          </Paper>
        </Box>
      );
    }
    return this.props.children;
  }
}

export default GlobalErrorBoundary;
