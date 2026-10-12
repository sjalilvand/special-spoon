import { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { AppBar, Box, Button, Chip, Container, Toolbar, Typography } from "@mui/material";
import { useAuth } from "../auth/AuthContext";

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const roles = user?.roles ?? [];
  const has = (rs: string[]) => rs.some((r) => roles.includes(r));

  return (
    <Box minHeight="100vh" bgcolor="grey.50">
      <AppBar position="static" color="primary" elevation={1}>
        <Toolbar sx={{ gap: 1.5, flexWrap: "wrap" }}>
          <Typography variant="h6" sx={{ cursor: "pointer", fontWeight: 700 }} onClick={() => navigate("/")}>
            Rosepsy | پنل مدیریت
          </Typography>
          {has(["ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "SYSTEM_ADMIN"]) && (
            <Button color="inherit" onClick={() => navigate("/dashboard")}>داشبورد</Button>
          )}
          {has(["ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR"]) && (
            <Button color="inherit" onClick={() => navigate("/cases")}>پرونده‌ها</Button>
          )}
          {has(["ORG_MANAGER", "RECEPTION"]) && (
            <Button color="inherit" onClick={() => navigate("/consultation-requests")}>درخواست‌ها</Button>
          )}
          {has(["COUNSELOR"]) && (
            <Button color="inherit" onClick={() => navigate("/worklist")}>کارتابل</Button>
          )}
          {has(["COUNSELOR"]) && (
            <Button color="inherit" onClick={() => navigate("/my-assessments")}>ارزیابی‌های من</Button>
          )}
          {has(["TECHNICAL_SUPERVISOR"]) && (
            <Button color="inherit" onClick={() => navigate("/reviews")}>بررسی‌های فنی</Button>
          )}
          {has(["TECHNICAL_SUPERVISOR"]) && (
            <Button color="inherit" onClick={() => navigate("/supervised-cases")}>تحت نظارت</Button>
          )}
          {has(["APPLICANT"]) && (
            <Button color="inherit" onClick={() => navigate("/me")}>پنل من</Button>
          )}
          {has(["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR"]) && (
            <Button color="inherit" onClick={() => navigate("/counselors")}>مشاوران</Button>
          )}
          {has(["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION"]) && (
            <Button color="inherit" onClick={() => navigate("/applicants")}>متقاضیان</Button>
          )}
          {has(["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION"]) && (
            <Button color="inherit" onClick={() => navigate("/imports")}>ورود اکسل</Button>
          )}
          {has(["SYSTEM_ADMIN"]) && (
            <Button color="inherit" onClick={() => navigate("/users")}>کاربران</Button>
          )}
          {has(["SYSTEM_ADMIN"]) && (
            <Button color="inherit" onClick={() => navigate("/audit-events")}>رخدادها</Button>
          )}
          <Box flexGrow={1} />
          <Button color="inherit" onClick={() => navigate("/change-password")}>تغییر رمز</Button>
          <Chip size="small" color="secondary" label={user?.display_name ?? ""} />
          <Button color="inherit" onClick={async () => { await logout(); navigate("/login"); }}>خروج</Button>
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ mt: 4, pb: 6 }}>
        {children}
      </Container>
    </Box>
  );
}
