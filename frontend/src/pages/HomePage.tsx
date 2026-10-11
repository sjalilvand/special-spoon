import { Chip, Paper, Stack, Typography } from "@mui/material";
import { useAuth } from "../auth/AuthContext";
import { roleTitle } from "../api/auth";

export default function HomePage() {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <Paper sx={{ p: 4 }}>
      <Typography variant="h5" fontWeight={700}>
        خوش آمدید، {user.display_name}
      </Typography>
      <Stack direction="row" spacing={1} mt={2} flexWrap="wrap" useFlexGap>
        {user.roles.map((r) => (
          <Chip key={r} label={roleTitle(r)} color="primary" variant="outlined" />
        ))}
      </Stack>
      <Typography mt={3} color="text.secondary">
        فاز ۲ تکمیل شد: ورود، نقش‌ها، مدیر اولیه و مدیریت حساب.
        فاز بعدی: مشاوران، متقاضیان و سه قالب اکسل (بند ۸ سند).
      </Typography>
      {user.must_change_password && (
        <Typography mt={1} color="warning.main">
          تغییر رمز عبور اولیه الزامی است — از منوی بالا «تغییر رمز» را انتخاب کنید.
        </Typography>
      )}
    </Paper>
  );
}
