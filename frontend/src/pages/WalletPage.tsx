import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Paper,
  Stack, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, TextField, Typography,
} from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import {
  adjustWallet, fetchMyWallet, fetchMyWalletEntries, fetchUserWalletEntries, fetchWallets,
  REASON_LABEL, walletTopup, WalletEntry, WalletInfo,
} from "../api/finance";
import { verifyPayment } from "../api/payments";
import { formatJalaliDateTime } from "../utils/jalali";

// فاز ۳۰ - B18 سند جامع: کیف پول، مانده، گردش و شارژ از درگاه (تصمیم D02)
// «مانده با جمع گردش‌ها سازگار و دوباره‌مصرفی ممنوع»

const fa = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : Number(n).toLocaleString("fa-IR");

const DIRECTION: Record<string, { label: string; color: "success" | "error" }> = {
  credit: { label: "بستانکار +", color: "success" },
  debit: { label: "بدهکار −", color: "error" },
};

export default function WalletPage() {
  const { user } = useAuth();
  const roles = user?.roles ?? [];
  const isManager = roles.includes("ORG_MANAGER") || roles.includes("SYSTEM_ADMIN");
  const [tab, setTab] = useState<"mine" | "all">("mine");

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={800}>کیف پول (B18)</Typography>
        <Box flexGrow={1} />
        {isManager && (
          <>
            <Button variant={tab === "mine" ? "contained" : "text"} onClick={() => setTab("mine")}>
              کیف پول من
            </Button>
            <Button variant={tab === "all" ? "contained" : "text"} onClick={() => setTab("all")}>
              کیف پول کاربران
            </Button>
          </>
        )}
      </Box>
      {tab === "mine" ? <MyWallet /> : <UsersWallets />}
    </Stack>
  );
}

/* ------------------------------ کیف پول من ------------------------------ */

function MyWallet() {
  const qc = useQueryClient();
  const [topupOpen, setTopupOpen] = useState(false);
  const wallet = useQuery({ queryKey: ["my-wallet"], queryFn: fetchMyWallet });
  const entries = useQuery({ queryKey: ["my-wallet-entries"], queryFn: fetchMyWalletEntries });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["my-wallet"] });
    qc.invalidateQueries({ queryKey: ["my-wallet-entries"] });
  };

  return (
    <Stack spacing={2}>
      <Paper sx={{ p: 3, display: "flex", alignItems: "center", gap: 3, flexWrap: "wrap" }}>
        <Box>
          <Typography variant="body2" color="text.secondary">مانده قابل استفاده</Typography>
          <Typography variant="h4" fontWeight={800}>
            {fa(wallet.data?.balance)} <span style={{ fontSize: 14 }}>{wallet.data?.currency}</span>
          </Typography>
        </Box>
        <Box flexGrow={1} />
        <Button variant="contained" onClick={() => setTopupOpen(true)}>شارژ از درگاه</Button>
      </Paper>

      <EntriesTable entries={entries.data ?? []} loading={entries.isLoading} />
      <TopupDialog
        open={topupOpen}
        onClose={() => setTopupOpen(false)}
        onDone={() => { refresh(); setTopupOpen(false); }}
      />
    </Stack>
  );
}

function EntriesTable({ entries, loading }: { entries: WalletEntry[]; loading: boolean }) {
  return (
    <TableContainer component={Paper}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>زمان</TableCell>
            <TableCell>نوع</TableCell>
            <TableCell>علت</TableCell>
            <TableCell>مبلغ (ریال)</TableCell>
            <TableCell>مانده پس از تراکنش</TableCell>
            <TableCell>یادداشت</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {loading && <TableRow><TableCell colSpan={6}>در حال بارگذاری…</TableCell></TableRow>}
          {!loading && entries.length === 0 && (
            <TableRow><TableCell colSpan={6}>گردشی ثبت نشده است</TableCell></TableRow>
          )}
          {entries.map((e) => (
            <TableRow key={e.id} hover>
              <TableCell>{formatJalaliDateTime(e.created_at)}</TableCell>
              <TableCell>
                <Chip size="small" color={DIRECTION[e.direction]?.color ?? "default"}
                      label={DIRECTION[e.direction]?.label ?? e.direction} />
              </TableCell>
              <TableCell>{REASON_LABEL[e.reason] ?? e.reason}</TableCell>
              <TableCell>{fa(e.amount)}</TableCell>
              <TableCell>{fa(e.balance_after)}</TableCell>
              <TableCell sx={{ maxWidth: 240 }}>{e.note ?? "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

/* ------------------------------ شارژ از درگاه ------------------------------ */

function TopupDialog({ open, onClose, onDone }: {
  open: boolean; onClose: () => void; onDone: () => void;
}) {
  const [amount, setAmount] = useState("");
  const [step, setStep] = useState<"form" | "gateway" | "done">("form");
  const [authority, setAuthority] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await walletTopup(Number(amount));
      setAuthority(r.authority);
      setStep("gateway");
    } catch (e) {
      setError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const verify = async (approve: boolean) => {
    if (!authority) return;
    setBusy(true);
    try {
      const r = await verifyPayment(authority, approve);
      if (r.ok) {
        setStep("done");
        onDone();
      } else {
        setError(r.reason ?? "پرداخت تأیید نشد");
      }
    } catch (e) {
      setError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const close = () => { onClose(); setStep("form"); setAmount(""); setError(null); setAuthority(null); };

  return (
    <Dialog open={open} onClose={close} maxWidth="xs" fullWidth>
      <DialogTitle>شارژ کیف پول</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          {step === "form" && (
            <>
              <TextField
                autoFocus label="مبلغ شارژ (ریال)" type="number" value={amount}
                onChange={(e) => setAmount(e.target.value)} slotProps={{ htmlInput: { min: 10000 } }}
              />
              <Button variant="contained" disabled={busy || !Number(amount)} onClick={start}>
                {busy ? "در حال اتصال…" : "انتقال به درگاه (sandbox - D02)"}
              </Button>
            </>
          )}
          {step === "gateway" && (
            <>
              <Alert severity="info">درگاه شبیه‌ساز: نتیجه پرداخت را انتخاب کنید (تأیید سمت سرور انجام می‌شود).</Alert>
              <Button variant="contained" disabled={busy} onClick={() => verify(true)}>پرداخت موفق</Button>
              <Button color="error" disabled={busy} onClick={() => verify(false)}>لغو پرداخت</Button>
            </>
          )}
          {step === "done" && <Alert severity="success">کیف پول با موفقیت شارژ شد.</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions><Button onClick={close}>بستن</Button></DialogActions>
    </Dialog>
  );
}

/* ------------------------------ کیف پول کاربران (مدیر) ------------------------------ */

function UsersWallets() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<WalletInfo | null>(null);
  const [adjustFor, setAdjustFor] = useState<WalletInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wallets = useQuery({ queryKey: ["wallets"], queryFn: fetchWallets });
  const entries = useQuery({
    queryKey: ["user-wallet-entries", selected?.user_id],
    queryFn: () => fetchUserWalletEntries(selected!.user_id),
    enabled: !!selected,
  });

  return (
    <Stack spacing={2}>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>کاربر</TableCell>
              <TableCell>نام کاربری</TableCell>
              <TableCell>مانده (ریال)</TableCell>
              <TableCell align="left">عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {wallets.isLoading && <TableRow><TableCell colSpan={4}>در حال بارگذاری…</TableCell></TableRow>}
            {!wallets.isLoading && (wallets.data ?? []).length === 0 && (
              <TableRow><TableCell colSpan={4}>کیف پولی ثبت نشده است</TableCell></TableRow>
            )}
            {(wallets.data ?? []).map((w) => (
              <TableRow key={w.id} hover>
                <TableCell>{w.user_name ?? "—"}</TableCell>
                <TableCell sx={{ direction: "ltr" }}>{w.username ?? "—"}</TableCell>
                <TableCell>{fa(w.balance)}</TableCell>
                <TableCell align="left">
                  <Stack direction="row" spacing={0.5}>
                    <Button size="small" onClick={() => setSelected(w)}>گردش</Button>
                    <Button size="small" variant="outlined" onClick={() => setAdjustFor(w)}>تعدیل</Button>
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {selected && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={700} mb={1}>
            گردش کیف پول — {selected.user_name}
          </Typography>
          <EntriesTable entries={entries.data ?? []} loading={entries.isLoading} />
        </Paper>
      )}

      <AdjustDialog
        wallet={adjustFor}
        onClose={() => setAdjustFor(null)}
        onDone={() => {
          setAdjustFor(null);
          qc.invalidateQueries({ queryKey: ["wallets"] });
          setError(null);
        }}
        onError={(m) => setError(m)}
      />
    </Stack>
  );
}

function AdjustDialog({ wallet, onClose, onDone, onError }: {
  wallet: WalletInfo | null; onClose: () => void; onDone: () => void; onError: (m: string) => void;
}) {
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!wallet || !note.trim() || !Number(amount)) return;
    setBusy(true);
    try {
      await adjustWallet(wallet.user_id, { amount: Number(amount), note: note.trim() });
      onDone();
      setAmount("");
      setNote("");
    } catch (e) {
      onError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={!!wallet} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>تعدیل کیف پول — {wallet?.user_name}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField
            label="مبلغ (مثبت = شارژ، منفی = کسر)" type="number" value={amount}
            onChange={(e) => setAmount(e.target.value)} slotProps={{ htmlInput: { step: "any" } }}
          />
          <TextField label="یادداشت (الزامی)" multiline minRows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" disabled={busy || !note.trim() || !Number(amount)} onClick={submit}>
          ثبت تعدیل
        </Button>
      </DialogActions>
    </Dialog>
  );
}
