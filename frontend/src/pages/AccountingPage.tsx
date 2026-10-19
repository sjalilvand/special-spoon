import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem,
  Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  TextField, Typography,
} from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  ACCOUNT_TYPE_LABEL, Account, backfillJournalEntries, createAccount, createManualEntry,
  createSettlementDraft, fetchAccounts, fetchJournalEntries, fetchReconciliation,
  fetchSettlements, fetchTrialBalance, JournalEntry, KIND_LABEL, reverseEntry, SOURCE_LABEL,
  settleSettlement, Settlement, TrialBalanceRow,
} from "../api/accounting";
import { errDetail } from "../api/client";

// فاز ۳۱ - B22 سند جامع: کدینگ، سند حسابداری، تسویه، مغایرت و گزارش مالی
// قواعد سند: «سند متوازن و قابل ردیابی به رویداد مالی» + «فروش گزارش با داده مالی تطبیق کند»

const fa = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : Number(n).toLocaleString("fa-IR");

const TYPE_COLOR: Record<string, "primary" | "warning" | "default" | "success" | "error"> = {
  asset: "primary",
  liability: "warning",
  equity: "default",
  revenue: "success",
  expense: "error",
};

export default function AccountingPage() {
  const [tab, setTab] = useState<"accounts" | "entries" | "settlements" | "reports">("entries");

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={800}>حسابداری (B22)</Typography>
        <Box flexGrow={1} />
        {(
          [
            ["entries", "اسناد"],
            ["accounts", "کدینگ حساب‌ها"],
            ["settlements", "تسویه"],
            ["reports", "تراز و مغایرت"],
          ] as const
        ).map(([key, label]) => (
          <Button key={key} variant={tab === key ? "contained" : "text"} onClick={() => setTab(key)}>
            {label}
          </Button>
        ))}
      </Box>
      {tab === "accounts" && <AccountsTab />}
      {tab === "entries" && <EntriesTab />}
      {tab === "settlements" && <SettlementsTab />}
      {tab === "reports" && <ReportsTab />}
    </Stack>
  );
}

/* ------------------------------ کدینگ ------------------------------ */

function AccountsTab() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [form, setForm] = useState({ code: "", name: "", type: "expense", description: "" });
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => fetchAccounts(true) });

  const submit = async () => {
    setErr(null);
    try {
      await createAccount({
        code: form.code.trim(),
        name: form.name.trim(),
        type: form.type as Account["type"],
        description: form.description.trim() || null,
      });
      setOpen(false);
      setForm({ code: "", name: "", type: "expense", description: "" });
      qc.invalidateQueries({ queryKey: ["accounts"] });
    } catch (e) {
      setErr(errDetail(e));
    }
  };

  const items = [...(accounts.data ?? [])].sort((a, b) => a.code.localeCompare(b.code));

  return (
    <Stack spacing={2}>
      <Box display="flex" justifyContent="flex-end">
        <Button variant="contained" onClick={() => setOpen(true)}>حساب جدید</Button>
      </Box>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>کد</TableCell>
              <TableCell>نام حساب</TableCell>
              <TableCell>نوع</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>سیستمی</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((a) => (
              <TableRow key={a.id}>
                <TableCell sx={{ fontFamily: "monospace", fontWeight: 700 }}>{a.code}</TableCell>
                <TableCell>{a.name}</TableCell>
                <TableCell>
                  <Chip size="small" color={TYPE_COLOR[a.type] ?? "default"} label={ACCOUNT_TYPE_LABEL[a.type] ?? a.type} />
                </TableCell>
                <TableCell>
                  <Chip size="small" color={a.is_active ? "success" : "default"} label={a.is_active ? "فعال" : "غیرفعال"} />
                </TableCell>
                <TableCell>{a.is_system ? "—" : ""}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>سرفصل جدید</DialogTitle>
        <DialogContent>
          {err && <Alert severity="error" sx={{ mt: 1 }}>{err}</Alert>}
          <Stack spacing={2} mt={1}>
            <TextField label="کد حساب" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })}
              placeholder="مثلاً 6101" inputProps={{ pattern: "[0-9]*" }} />
            <TextField label="نام حساب" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <TextField select label="نوع" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              {Object.entries(ACCOUNT_TYPE_LABEL).map(([k, v]) => (
                <MenuItem key={k} value={k}>{v}</MenuItem>
              ))}
            </TextField>
            <TextField label="شرح (اختیاری)" value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })} multiline rows={2} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>انصراف</Button>
          <Button variant="contained" onClick={submit} disabled={!form.code || !form.name}>ثبت</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

/* ------------------------------ اسناد ------------------------------ */

function EntriesTab() {
  const qc = useQueryClient();
  const [sourceType, setSourceType] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [detail, setDetail] = useState<JournalEntry | null>(null);
  const [manualOpen, setManualOpen] = useState(false);
  const entries = useQuery({
    queryKey: ["journal-entries", sourceType],
    queryFn: () => fetchJournalEntries({ source_type: sourceType || undefined, limit: 200 }),
  });

  const doBackfill = async () => {
    setErr(null);
    try {
      await backfillJournalEntries();
      qc.invalidateQueries({ queryKey: ["journal-entries"] });
    } catch (e) {
      setErr(errDetail(e));
    }
  };

  return (
    <Stack spacing={2}>
      {err && <Alert severity="error">{err}</Alert>}
      <Box display="flex" gap={1.5} flexWrap="wrap" alignItems="center">
        <TextField select size="small" label="منبع رویداد" value={sourceType}
          onChange={(e) => setSourceType(e.target.value)} sx={{ minWidth: 180 }}>
          <MenuItem value="">همه</MenuItem>
          {Object.entries(SOURCE_LABEL).map(([k, v]) => (
            <MenuItem key={k} value={k}>{v}</MenuItem>
          ))}
        </TextField>
        <Box flexGrow={1} />
        <Button variant="contained" onClick={() => setManualOpen(true)}>سند دستی</Button>
        <Button onClick={doBackfill}>سند رویدادهای بدون سند (backfill)</Button>
      </Box>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>شماره سند</TableCell>
              <TableCell>تاریخ</TableCell>
              <TableCell>شرح</TableCell>
              <TableCell>نوع</TableCell>
              <TableCell>منبع</TableCell>
              <TableCell>برگشتی</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(entries.data ?? []).map((e) => (
              <TableRow key={e.id} hover sx={{ cursor: "pointer" }} onClick={() => setDetail(e)}>
                <TableCell sx={{ fontFamily: "monospace" }}>{e.entry_no}</TableCell>
                <TableCell>{e.entry_date ?? "—"}</TableCell>
                <TableCell>{e.description}</TableCell>
                <TableCell>{KIND_LABEL[e.kind] ?? e.kind}</TableCell>
                <TableCell>
                  <Chip size="small" label={SOURCE_LABEL[e.source_type] ?? e.source_type}
                    color={e.source_type === "manual" ? "secondary" : "default"} />
                </TableCell>
                <TableCell>{e.is_reversal ? <Chip size="small" color="warning" label="برگشتی" /> : ""}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <EntryDetailDialog entry={detail} onClose={() => setDetail(null)} />
      <ManualEntryDialog open={manualOpen} onClose={() => setManualOpen(false)} />
    </Stack>
  );
}

function EntryDetailDialog({ entry, onClose }: { entry: JournalEntry | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [err, setErr] = useState<string | null>(null);
  if (!entry) return null;
  const dr = entry.lines.reduce((s, l) => s + l.debit, 0);
  const cr = entry.lines.reduce((s, l) => s + l.credit, 0);

  const doReverse = async () => {
    setErr(null);
    try {
      await reverseEntry(entry.id);
      qc.invalidateQueries({ queryKey: ["journal-entries"] });
      onClose();
    } catch (e) {
      setErr(errDetail(e));
    }
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>
        سند {entry.entry_no} {entry.is_reversal && <Chip size="small" color="warning" label="برگشتی" sx={{ mx: 1 }} />}
      </DialogTitle>
      <DialogContent>
        {err && <Alert severity="error" sx={{ mb: 1 }}>{err}</Alert>}
        <Typography variant="body2" color="text.secondary" mb={1}>
          {entry.description} — {SOURCE_LABEL[entry.source_type]} / {KIND_LABEL[entry.kind] ?? entry.kind}
        </Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>کد</TableCell>
              <TableCell>حساب</TableCell>
              <TableCell align="left">بدهکار</TableCell>
              <TableCell align="left">بستانکار</TableCell>
              <TableCell>شرح ردیف</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {entry.lines.map((l) => (
              <TableRow key={l.id}>
                <TableCell sx={{ fontFamily: "monospace" }}>{l.account_code}</TableCell>
                <TableCell>{l.account_name}</TableCell>
                <TableCell align="left">{l.debit ? fa(l.debit) : "—"}</TableCell>
                <TableCell align="left">{l.credit ? fa(l.credit) : "—"}</TableCell>
                <TableCell>{l.description}</TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell colSpan={2}><strong>جمع</strong></TableCell>
              <TableCell align="left"><strong>{fa(dr)}</strong></TableCell>
              <TableCell align="left"><strong>{fa(cr)}</strong></TableCell>
              <TableCell>
                {Math.abs(dr - cr) < 0.01
                  ? <Chip size="small" color="success" label="متوازن" />
                  : <Chip size="small" color="error" label="نامتوازن" />}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </DialogContent>
      <DialogActions>
        {!entry.is_reversal && (
          <Button color="warning" onClick={doReverse}>ثبت سند برگشتی</Button>
        )}
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}

function ManualEntryDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => fetchAccounts(true), enabled: open });
  const [description, setDescription] = useState("");
  const [lines, setLines] = useState([
    { account_id: "", debit: "", credit: "" },
    { account_id: "", debit: "", credit: "" },
  ]);
  const [err, setErr] = useState<string | null>(null);

  const totalDr = lines.reduce((s, l) => s + (Number(l.debit) || 0), 0);
  const totalCr = lines.reduce((s, l) => s + (Number(l.credit) || 0), 0);
  const balanced = totalDr > 0 && Math.abs(totalDr - totalCr) < 0.01;

  const submit = async () => {
    setErr(null);
    try {
      await createManualEntry({
        description,
        lines: lines.map((l) => ({
          account_id: l.account_id,
          debit: Number(l.debit) || 0,
          credit: Number(l.credit) || 0,
        })),
      });
      qc.invalidateQueries({ queryKey: ["journal-entries"] });
      setDescription("");
      setLines([
        { account_id: "", debit: "", credit: "" },
        { account_id: "", debit: "", credit: "" },
      ]);
      onClose();
    } catch (e) {
      setErr(errDetail(e));
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>سند دستی — قاعده «سند متوازن»</DialogTitle>
      <DialogContent>
        {err && <Alert severity="error" sx={{ mb: 1 }}>{err}</Alert>}
        <TextField fullWidth label="شرح سند" value={description}
          onChange={(e) => setDescription(e.target.value)} sx={{ my: 1.5 }} />
        <Stack spacing={1.5}>
          {lines.map((l, i) => (
            <Stack key={i} direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
              <TextField select size="small" label="حساب" value={l.account_id}
                onChange={(e) => {
                  const next = [...lines];
                  next[i] = { ...next[i], account_id: e.target.value };
                  setLines(next);
                }}
                sx={{ minWidth: 260 }}>
                {(accounts.data ?? []).map((a) => (
                  <MenuItem key={a.id} value={a.id}>{a.code} — {a.name}</MenuItem>
                ))}
              </TextField>
              <TextField size="small" type="number" label="بدهکار" value={l.debit}
                onChange={(e) => {
                  const next = [...lines];
                  next[i] = { ...next[i], debit: e.target.value, credit: e.target.value ? "0" : next[i].credit };
                  setLines(next);
                }}
                sx={{ width: 140 }} />
              <TextField size="small" type="number" label="بستانکار" value={l.credit}
                onChange={(e) => {
                  const next = [...lines];
                  next[i] = { ...next[i], credit: e.target.value, debit: e.target.value ? "0" : next[i].debit };
                  setLines(next);
                }}
                sx={{ width: 140 }} />
              {lines.length > 2 && i >= 2 && (
                <Button size="small" color="error" onClick={() => setLines(lines.filter((_, j) => j !== i))}>حذف</Button>
              )}
            </Stack>
          ))}
        </Stack>
        <Box mt={2} display="flex" gap={2} alignItems="center">
          <Button size="small" onClick={() => setLines([...lines, { account_id: "", debit: "", credit: "" }])}>
            + ردیف
          </Button>
          <Chip size="small" color={balanced ? "success" : "default"}
            label={`بدهکار ${fa(totalDr)} / بستانکار ${fa(totalCr)}`} />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" onClick={submit}
          disabled={!description || !balanced || lines.some((l) => !l.account_id)}>
          ثبت سند
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/* ------------------------------ تسویه ------------------------------ */

function SettlementsTab() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [settleTarget, setSettleTarget] = useState<Settlement | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [form, setForm] = useState({ gateway: "sandbox", period_start: "", period_end: "", note: "" });
  const rows = useQuery({ queryKey: ["settlements"], queryFn: () => fetchSettlements() });

  const createDraft = async () => {
    setErr(null);
    try {
      await createSettlementDraft({
        gateway: form.gateway as "sandbox" | "zarinpal",
        period_start: form.period_start || null,
        period_end: form.period_end || null,
        note: form.note || null,
      });
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["settlements"] });
    } catch (e) {
      setErr(errDetail(e));
    }
  };

  return (
    <Stack spacing={2}>
      {err && <Alert severity="error">{err}</Alert>}
      <Box display="flex" justifyContent="flex-end">
        <Button variant="contained" onClick={() => { setErr(null); setOpen(true); }}>پیش‌نویس تسویه جدید</Button>
      </Box>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>شماره</TableCell>
              <TableCell>درگاه</TableCell>
              <TableCell>دوره</TableCell>
              <TableCell>تعداد پرداخت</TableCell>
              <TableCell>ناخالص</TableCell>
              <TableCell>کارمزد</TableCell>
              <TableCell>خالص</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {(rows.data ?? []).map((s) => (
              <TableRow key={s.id}>
                <TableCell sx={{ fontFamily: "monospace" }}>{s.settlement_no}</TableCell>
                <TableCell>{s.gateway === "wallet" ? "کیف پول" : s.gateway}</TableCell>
                <TableCell>
                  {s.period_start ? `${s.period_start} تا ${s.period_end ?? "—"}` : "—"}
                </TableCell>
                <TableCell>{fa(s.payments_count)}</TableCell>
                <TableCell>{fa(s.gross_amount)}</TableCell>
                <TableCell>{s.fee_amount === null ? "—" : fa(s.fee_amount)}</TableCell>
                <TableCell>{s.net_amount === null ? "—" : fa(s.net_amount)}</TableCell>
                <TableCell>
                  <Chip size="small" color={s.status === "settled" ? "success" : "warning"}
                    label={s.status === "settled" ? "تسویه‌شده" : "پیش‌نویس"} />
                </TableCell>
                <TableCell>
                  {s.status === "draft" && (
                    <Button size="small" onClick={() => setSettleTarget(s)}>تسویه</Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>پیش‌نویس تسویه دوره درگاه</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField select label="درگاه" value={form.gateway}
              onChange={(e) => setForm({ ...form, gateway: e.target.value })}>
              <MenuItem value="sandbox">شبیه‌ساز (sandbox)</MenuItem>
              <MenuItem value="zarinpal">زرین‌پال</MenuItem>
            </TextField>
            <Stack direction="row" spacing={1.5}>
              <TextField fullWidth type="date" label="از تاریخ" value={form.period_start}
                onChange={(e) => setForm({ ...form, period_start: e.target.value })}
                InputLabelProps={{ shrink: true }} />
              <TextField fullWidth type="date" label="تا تاریخ" value={form.period_end}
                onChange={(e) => setForm({ ...form, period_end: e.target.value })}
                InputLabelProps={{ shrink: true }} />
            </Stack>
            <TextField label="یادداشت (اختیاری)" value={form.note}
              onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>انصراف</Button>
          <Button variant="contained" onClick={createDraft}>ساخت پیش‌نویس</Button>
        </DialogActions>
      </Dialog>

      <SettleDialog target={settleTarget} onClose={() => setSettleTarget(null)} />
    </Stack>
  );
}

function SettleDialog({ target, onClose }: { target: Settlement | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [fee, setFee] = useState("0");
  const [err, setErr] = useState<string | null>(null);
  if (!target) return null;

  const submit = async () => {
    setErr(null);
    try {
      await settleSettlement(target.id, Number(fee) || 0);
      qc.invalidateQueries({ queryKey: ["settlements"] });
      qc.invalidateQueries({ queryKey: ["journal-entries"] });
      onClose();
    } catch (e) {
      setErr(errDetail(e));
    }
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>اجرای تسویه {target.settlement_no}</DialogTitle>
      <DialogContent>
        {err && <Alert severity="error" sx={{ mb: 1 }}>{err}</Alert>}
        <Typography variant="body2" mb={2}>
          ناخالص: <strong>{fa(target.gross_amount)}</strong> ریال — با ثبت تسویه، سند متوازن
          «بانک + کارمزد | درگاه» ثبت می‌شود.
        </Typography>
        <TextField fullWidth type="number" label="کارمزد درگاه (ریال)" value={fee}
          onChange={(e) => setFee(e.target.value)} />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" onClick={submit}>تسویه و ثبت سند</Button>
      </DialogActions>
    </Dialog>
  );
}

/* ------------------------------ تراز و مغایرت ------------------------------ */

function ReportsTab() {
  const tb = useQuery({ queryKey: ["trial-balance"], queryFn: fetchTrialBalance });
  const rec = useQuery({ queryKey: ["reconciliation"], queryFn: fetchReconciliation });

  return (
    <Stack spacing={2}>
      <Box display="flex" gap={1.5} flexWrap="wrap">
        <Chip
          color={tb.data?.is_balanced ? "success" : "error"}
          label={tb.data?.is_balanced ? "دفتر متوازن است" : "دفتر نامتوازن است!"}
        />
        <Chip label={`جمع بدهکار: ${fa(tb.data?.total_debit ?? 0)}`} />
        <Chip label={`جمع بستانکار: ${fa(tb.data?.total_credit ?? 0)}`} />
      </Box>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>کد</TableCell>
              <TableCell>حساب</TableCell>
              <TableCell>نوع</TableCell>
              <TableCell align="left">بدهکار</TableCell>
              <TableCell align="left">بستانکار</TableCell>
              <TableCell align="left">مانده</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(tb.data?.items ?? []).map((row: TrialBalanceRow) => (
              <TableRow key={row.id}>
                <TableCell sx={{ fontFamily: "monospace" }}>{row.code}</TableCell>
                <TableCell>{row.name}</TableCell>
                <TableCell>
                  <Chip size="small" color={TYPE_COLOR[row.type] ?? "default"} label={ACCOUNT_TYPE_LABEL[row.type]} />
                </TableCell>
                <TableCell align="left">{row.debit ? fa(row.debit) : "—"}</TableCell>
                <TableCell align="left">{row.credit ? fa(row.credit) : "—"}</TableCell>
                <TableCell align="left" sx={{ fontWeight: 700 }}>{fa(row.balance)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {rec.data && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={700} mb={1.5}>مغایرت و تطبیق فروش (B24×B22)</Typography>
          <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap mb={2}>
            <Chip color={rec.data.ledger.is_balanced ? "success" : "error"}
              label={rec.data.ledger.is_balanced ? "توازن دفتر: بله" : "توازن دفتر: خیر"} />
            {(
              [
                ["پرداخت‌ها", rec.data.events.payments],
                ["استردادها", rec.data.events.refunds],
                ["تعدیل‌ها", rec.data.events.wallet_adjustments],
              ] as const
            ).map(([label, ev]) => (
              <Chip key={label}
                color={ev.uncovered === 0 ? "success" : "error"}
                label={`${label}: ${ev.total} رویداد — ${ev.uncovered} بدون سند`} />
            ))}
          </Stack>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>تطبیق فروش گزارش با دفتر</TableCell>
                <TableCell align="left">مبلغ (ریال)</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              <TableRow>
                <TableCell>فروش گزارش (سفارش‌های خدمت، خالص پس از استرداد)</TableCell>
                <TableCell align="left">{fa(rec.data.sales_reconciliation.sales_report_amount)}</TableCell>
              </TableRow>
              <TableRow>
                <TableCell>درآمد شناسایی‌شده در دفتر (خالص)</TableCell>
                <TableCell align="left">{fa(rec.data.sales_reconciliation.journal_revenue_amount)}</TableCell>
              </TableRow>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>اختلاف</TableCell>
                <TableCell align="left" sx={{ fontWeight: 700 }}>
                  {fa(rec.data.sales_reconciliation.difference)}{" "}
                  <Chip size="small" color={rec.data.sales_reconciliation.reconciled ? "success" : "warning"}
                    label={rec.data.sales_reconciliation.reconciled ? "تطبیق دارد" : "مغایرت"} />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </Paper>
      )}
    </Stack>
  );
}
