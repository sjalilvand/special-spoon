import { Alert, Box, Button, Card, CardContent, Stack, TextField, Typography } from "@mui/material";
import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { activate } from "../api/auth";
import { errDetail } from "../api/client";

export default function ActivatePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") ?? "";
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (newPassword !== confirm) {
      setError("تکرار رمز مطابقت ندارد");
      return;
    }
    if (newPassword.length < 10) {
      setError("رمز باید حداقل ۱۰ نویسه باشد");
      return;
    }
    setBusy(true);
    try {
      await activate(token, newPassword);
      setDone(true);
      setTimeout(() => navigate("/login"), 2500);
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
          <Typography variant="h6" fontWeight={700} gutterBottom>
            فعال‌سازی حساب
          </Typography>
          {!token && <Alert severity="warning">لینک فعال‌سازی نامعتبر است.</Alert>}
          {done && (
            <Alert severity="success">
              حساب فعال شد. اکنون می‌توانید وارد شوید.
            </Alert>
          )}
          {!done && token && (
            <>
              {error && (
                <Alert severity="error" sx={{ mt: 2 }}>
                  {error}
                </Alert>
              )}
              <form onSubmit={onSubmit}>
                <Stack spacing={2} mt={2}>
                  <TextField
                    label="رمز عبور شخصی (حداقل ۱۰ نویسه)"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    autoFocus
                  />
                  <TextField
                    label="تکرار رمز عبور"
                    type="password"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    required
                  />
                  <Button type="submit" variant="contained" disabled={busy}>
                    {busy ? "در حال فعال‌سازی…" : "فعال‌سازی حساب"}
                  </Button>
                </Stack>
              </form>
            </>
          )}
          <Box mt={2}>
            <Link to="/login">بازگشت به ورود</Link>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
