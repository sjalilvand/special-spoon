// فاز ۸۶ - آکادمی رز: دیالوگ ورود با کد یک‌بارمصرف (پیامکی) برای خرید و پخش
import {
  Alert, Box, Button, Dialog, DialogContent, DialogTitle, Snackbar, Stack, TextField, Typography,
} from "@mui/material";
import { useState } from "react";
import { academyRequestCode, academyVerifyCode, saveSession } from "../academy";

export default function AcademyAuthDialog({ open, onClose, onDone }: {
  open: boolean;
  onClose: () => void;
  onDone?: () => void;
}) {
  const [step, setStep] = useState<"mobile" | "code">("mobile");
  const [mobile, setMobile] = useState("");
  const [fullName, setFullName] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  const reset = () => {
    setStep("mobile"); setMobile(""); setFullName(""); setCode("");
    setDevCode(null); setError(null); setOkMsg(null);
  };

  const requestCode = async () => {
    setError(null);
    setBusy(true);
    try {
      const res = await academyRequestCode(mobile.trim());
      setStep("code");
      setOkMsg("کد تأیید ارسال شد");
      if (res.dev_code) setDevCode(res.dev_code);
    } catch (e) {
      setError(e instanceof Error ? e.message : "خطا");
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    setError(null);
    setBusy(true);
    try {
      const s = await academyVerifyCode(mobile.trim(), code.trim(), fullName.trim() || undefined);
      saveSession(s);
      setOkMsg(`خوش آمدید ${s.user.display_name}`);
      setTimeout(() => {
        reset();
        onClose();
        onDone?.();
      }, 600);
    } catch (e) {
      setError(e instanceof Error ? e.message : "خطا");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Dialog open={open} onClose={() => { reset(); onClose(); }} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 800, color: "primary.main" }}>
          {step === "mobile" ? "ورود به آکادمی رز" : "کد تأیید"}
        </DialogTitle>
        <DialogContent>
          {step === "mobile" ? (
            <Stack spacing={2} mt={1}>
              <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.9 }}>
                برای خرید دوره و تماشای ویدیوها با شماره موبایل وارد شوید. حساب شما خودکار ساخته می‌شود.
              </Typography>
              <TextField
                label="شماره موبایل" dir="ltr" value={mobile}
                onChange={(e) => setMobile(e.target.value)}
                placeholder="09121234567"
                inputProps={{ inputMode: "numeric", maxLength: 14 }}
              />
              <TextField
                label="نام و نام خانوادگی (اختیاری)" value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
              <Button variant="contained" disabled={busy || mobile.trim().length < 10} onClick={requestCode}>
                {busy ? "..." : "دریافت کد تأیید"}
              </Button>
            </Stack>
          ) : (
            <Stack spacing={2} mt={1}>
              <Typography variant="body2" color="text.secondary" dir="ltr" textAlign="center">
                {mobile}
              </Typography>
              <TextField
                label="کد ۵ رقمی" dir="ltr" value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                inputProps={{ inputMode: "numeric", maxLength: 8 }}
                autoFocus
              />
              {devCode && (
                <Alert severity="info" sx={{ fontSize: 13 }}>
                  حالت توسعه — کد شما: <strong dir="ltr">{devCode}</strong>
                </Alert>
              )}
              <Button variant="contained" disabled={busy || code.trim().length < 4} onClick={verify}>
                {busy ? "..." : "ورود"}
              </Button>
              <Button size="small" onClick={() => setStep("mobile")}>ویرایش شماره</Button>
            </Stack>
          )}
        </DialogContent>
      </Dialog>
      <Snackbar open={!!error} autoHideDuration={5000} onClose={() => setError(null)}>
        <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>
      </Snackbar>
      <Snackbar open={!!okMsg} autoHideDuration={3000} onClose={() => setOkMsg(null)}>
        <Alert severity="success" onClose={() => setOkMsg(null)}>{okMsg}</Alert>
      </Snackbar>
      <Box aria-hidden />
    </>
  );
}
