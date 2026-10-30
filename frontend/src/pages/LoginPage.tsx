import { Alert, Box, Button, Card, CardContent, Divider, Stack, TextField, Typography } from "@mui/material";
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";

// ورود یکپارچه (SSO) با رز هاب — Rose Hub
const ROSE_HUB_LAUNCH_URL =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_ROSE_HUB_LAUNCH_URL ||
  "http://130.185.73.157:8082/api/sso/launch?clientId=rose-psy-5c3f9b";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const me = await login(username.trim(), password);
      if (me.must_change_password) navigate("/change-password");
      else navigate("/");
    } catch (err) {
      setError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh" bgcolor="grey.100">
      <Card sx={{ minWidth: 380 }}>
        <CardContent sx={{ p: 4 }}>
          <Typography variant="h5" fontWeight={700} gutterBottom>
            Rosepsy
          </Typography>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            ورود به سامانه مشاوره روان‌شناختی سازمانی
          </Typography>
          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
          <form onSubmit={onSubmit}>
            <Stack spacing={2} mt={2}>
              <TextField
                label="نام کاربری"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                required
              />
              <TextField
                label="رمز عبور"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <Button type="submit" variant="contained" disabled={busy}>
                {busy ? "در حال ورود…" : "ورود"}
              </Button>
              <Divider>
                <Typography variant="caption" color="text.secondary">یا</Typography>
              </Divider>
              <Button
                variant="outlined"
                color="secondary"
                onClick={() => { window.location.href = ROSE_HUB_LAUNCH_URL; }}
              >
                ورود یکپارچه با رز هاب (SSO)
              </Button>
            </Stack>
          </form>
        </CardContent>
      </Card>
    </Box>
  );
}
