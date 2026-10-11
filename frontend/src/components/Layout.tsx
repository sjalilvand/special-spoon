import { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { AppBar, Box, Button, Chip, Container, Toolbar, Typography } from "@mui/material";
import { useAuth } from "../auth/AuthContext";

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.roles.includes("SYSTEM_ADMIN") ?? false;

  return (
    <Box minHeight="100vh" bgcolor="grey.50">
      <AppBar position="static" color="primary" elevation={1}>
        <Toolbar sx={{ gap: 1.5 }}>
          <Typography
            variant="h6"
            sx={{ flexGrow: 1, cursor: "pointer", fontWeight: 700 }}
            onClick={() => navigate("/")}
          >
            Rosepsy
          </Typography>
          {isAdmin && (
            <Button color="inherit" onClick={() => navigate("/users")}>
              کاربران
            </Button>
          )}
          <Button color="inherit" onClick={() => navigate("/change-password")}>
            تغییر رمز
          </Button>
          <Chip size="small" color="secondary" label={user?.display_name ?? ""} />
          <Button
            color="inherit"
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
          >
            خروج
          </Button>
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ mt: 4, pb: 6 }}>
        {children}
      </Container>
    </Box>
  );
}
