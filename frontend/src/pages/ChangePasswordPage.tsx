import { Alert, Button, Card, CardContent, Stack, TextField, Typography } from "@mui/material";
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import { changePassword } from "../api/auth";

export default function ChangePasswordPage() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (newPassword !== confirm) {
      setError("تکرار رمز جدید مطابقت ندارد");
      return;
    }
    if (newPassword.length < 10) {
      setError("رمز جدید باید حداقل ۱۰ نویسه باشد");
      return;
    }
    setBusy(true);
    try {
      await changePassword(currentPassword, newPassword);
      await logout();
      navigate("/login");
    } catch (err) {
      setError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card sx={{ maxWidth: 480, mx: "auto" }}>
      <CardContent sx={{ p: 4 }}>
        <Typography variant="h6" fontWeight={700} gutterBottom>
          تغییر رمز عبور
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          پس از تغییر رمز، همه نشست‌های فعال باطل می‌شوند و باید دوباره وارد شوید.
        </Typography>
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
        <form onSubmit={onSubmit}>
          <Stack spacing={2} mt={2}>
            <TextField
              label="رمز عبور فعلی"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
            <TextField
              label="رمز جدید (حداقل ۱۰ نویسه)"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
            <TextField
              label="تکرار رمز جدید"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
            <Button type="submit" variant="contained" disabled={busy}>
              {busy ? "در حال ثبت…" : "ثبت رمز جدید"}
            </Button>
          </Stack>
        </form>
      </CardContent>
    </Card>
  );
}
