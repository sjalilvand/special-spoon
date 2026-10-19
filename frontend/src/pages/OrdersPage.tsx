import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControl,
  InputLabel, MenuItem, Paper, Select, Stack, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import { apiClient } from "../api/client";
import {
  createOrder, cancelOrder, fetchGateways, fetchOrders, Order, startPayment, verifyPayment,
} from "../api/payments";
import {
  createDiscount, executeRefundRequest, fetchDiscounts, fetchRefundRequests,
  payOrderFromWallet, RefundRequestRow, reviewRefundRequest, updateDiscount, validateDiscount,
} from "../api/finance";
import { formatJalaliDateTime } from "../utils/jalali";

// فاز ۲۹/۳۰ - B10/B19/B20 سند جامع: سفارش و پرداخت، کد تخفیف و استرداد؛
// تأیید قطعی سمت سرور، callback تکراری بی‌اثر، سقف تخفیف، اجرای تکراری ممنوع

const fa = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : Number(n).toLocaleString("fa-IR");

const ORDER_STATUS: Record<string, { label: string; color: "success" | "warning" | "error" | "default" }> = {
  pending: { label: "در انتظار پرداخت", color: "warning" },
  paid: { label: "پرداخت‌شده", color: "success" },
  cancelled: { label: "لغوشده", color: "default" },
  failed: { label: "ناموفق", color: "error" },
};

const REFUND_STATUS: Record<string, { label: string; color: "success" | "warning" | "error" | "default" | "info" }> = {
  pending: { label: "در انتظار بررسی", color: "warning" },
  approved: { label: "تأییدشده", color: "info" },
  rejected: { label: "ردشده", color: "error" },
  executed: { label: "اجرا شده", color: "success" },
};

const DISCOUNT_KIND: Record<string, string> = { amount: "مبلغ ثابت (ریال)", percent: "درصد" };

export default function OrdersPage() {
  const { user } = useAuth();
  const roles = user?.roles ?? [];
  const isManager = roles.includes("ORG_MANAGER") || roles.includes("SYSTEM_ADMIN");
  const [tab, setTab] = useState<"orders" | "discounts" | "refunds">("orders");

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
        <Typography variant="h6" fontWeight={800}>سفارش و پرداخت</Typography>
        <Box flexGrow={1} />
        <Button variant={tab === "orders" ? "contained" : "text"} onClick={() => setTab("orders")}>
          سفارش‌ها (B10)
        </Button>
        <Button variant={tab === "discounts" ? "contained" : "text"} onClick={() => setTab("discounts")}>
          کدهای تخفیف (B19)
        </Button>
        <Button variant={tab === "refunds" ? "contained" : "text"} onClick={() => setTab("refunds")}>
          استردادها (B20)
        </Button>
      </Box>
      {tab === "orders" && <OrdersTab />}
      {tab === "discounts" && <DiscountsTab canManage={isManager} />}
      {tab === "refunds" && <RefundsTab isManager={isManager} />}
    </Stack>
  );
}

/* ============================== سفارش‌ها ============================== */

function OrdersTab() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [newOpen, setNewOpen] = useState(false);

  const orders = useQuery({
    queryKey: ["orders", statusFilter],
    queryFn: () => fetchOrders(statusFilter || undefined),
  });
  const gateways = useQuery({ queryKey: ["gateways"], queryFn: fetchGateways });

  const cancelMut = useMutation({
    mutationFn: cancelOrder,
    onSuccess: (o) => {
      qc.invalidateQueries({ queryKey: ["orders"] });
      setOkMsg(`سفارش ${o.order_number} لغو شد (سهمیه کد تخفیف آزاد گردید)`);
      setError(null);
    },
    onError: (e) => setError(errDetail(e)),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["orders"] });
    qc.invalidateQueries({ queryKey: ["invoices"] });
    qc.invalidateQueries({ queryKey: ["my-wallet"] });
    qc.invalidateQueries({ queryKey: ["my-wallet-entries"] });
  };

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>وضعیت</InputLabel>
          <Select value={statusFilter} label="وضعیت" onChange={(e) => setStatusFilter(e.target.value)}>
            <MenuItem value="">همه</MenuItem>
            {Object.entries(ORDER_STATUS).map(([k, v]) => (
              <MenuItem key={k} value={k}>{v.label}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <Box flexGrow={1} />
        <Button variant="contained" onClick={() => setNewOpen(true)}>+ سفارش جدید</Button>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {okMsg && <Alert severity="success" onClose={() => setOkMsg(null)}>{okMsg}</Alert>}

      {(gateways.data ?? []).length > 0 && (
        <Paper sx={{ p: 1.25, display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
          <Typography variant="body2" color="text.secondary">درگاه‌ها (D02):</Typography>
          {(gateways.data ?? []).map((g) => (
            <Chip
              key={g.code}
              size="small"
              color={g.enabled ? (g.is_default ? "primary" : "default") : "default"}
              label={`${g.title}${g.is_default ? " — پیش‌فرض" : ""}${g.enabled ? "" : " — غیرفعال"}`}
              variant={g.enabled ? "filled" : "outlined"}
            />
          ))}
        </Paper>
      )}

      <OrdersTable
        orders={orders.data ?? []}
        loading={orders.isLoading}
        onCancel={(o) => cancelMut.mutate(o.id)}
        onChanged={(msg) => { refresh(); setOkMsg(msg); setError(null); }}
        onError={(m) => setError(m)}
        onOpenInvoice={(id) => navigate(`/invoices/${id}`)}
      />

      <NewOrderDialog
        open={newOpen}
        onClose={() => setNewOpen(false)}
        onCreated={(o) => {
          refresh();
          setNewOpen(false);
          setOkMsg(`سفارش ${o.order_number} ساخته شد`);
        }}
        onError={(m) => setError(m)}
      />
    </Stack>
  );
}

function OrdersTable(props: {
  orders: Order[];
  loading: boolean;
  onCancel: (o: Order) => void;
  onChanged: (msg: string) => void;
  onError: (m: string) => void;
  onOpenInvoice: (id: string) => void;
}) {
  const [payFor, setPayFor] = useState<Order | null>(null);
  return (
    <>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>شماره</TableCell>
              <TableCell>عنوان</TableCell>
              <TableCell>مبلغ</TableCell>
              <TableCell>تخفیف</TableCell>
              <TableCell>قابل پرداخت</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>فاکتور</TableCell>
              <TableCell>ایجاد</TableCell>
              <TableCell align="left">عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {props.loading && <TableRow><TableCell colSpan={9}>در حال بارگذاری…</TableCell></TableRow>}
            {!props.loading && props.orders.length === 0 && (
              <TableRow><TableCell colSpan={9}>سفارشی یافت نشد</TableCell></TableRow>
            )}
            {props.orders.map((o) => (
              <TableRow key={o.id} hover>
                <TableCell sx={{ direction: "ltr" }}>{o.order_number}</TableCell>
                <TableCell sx={{ maxWidth: 200 }}>
                  {o.title}
                  {o.kind === "topup" && <Chip size="small" sx={{ mx: 0.5 }} label="شارژ کیف پول" />}
                </TableCell>
                <TableCell>{fa(o.amount)}</TableCell>
                <TableCell>
                  {o.discount_amount ? (
                    <span>
                      −{fa(o.discount_amount)} {o.discount_code && <Chip size="small" label={o.discount_code} />}
                    </span>
                  ) : "—"}
                </TableCell>
                <TableCell>{fa(o.payable_amount)}</TableCell>
                <TableCell>
                  <Chip size="small" color={ORDER_STATUS[o.status]?.color ?? "default"}
                        label={ORDER_STATUS[o.status]?.label ?? o.status} />
                </TableCell>
                <TableCell>
                  {o.invoice_id ? (
                    <Button size="small" onClick={() => props.onOpenInvoice(o.invoice_id!)}>
                      {o.invoice_number}
                    </Button>
                  ) : "—"}
                </TableCell>
                <TableCell>{formatJalaliDateTime(o.created_at)}</TableCell>
                <TableCell align="left">
                  <Stack direction="row" spacing={0.5}>
                    {o.status === "pending" && (
                      <Button size="small" variant="contained" onClick={() => setPayFor(o)}>پرداخت</Button>
                    )}
                    {o.status === "pending" && (
                      <Button size="small" color="error" onClick={() => props.onCancel(o)}>لغو</Button>
                    )}
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <PayDialog
        order={payFor}
        onClose={() => setPayFor(null)}
        onChanged={(msg) => { props.onChanged(msg); setPayFor(null); }}
        onError={props.onError}
      />
    </>
  );
}

/* ------------------------------ جریان پرداخت ------------------------------ */

function PayDialog(props: {
  order: Order | null;
  onClose: () => void;
  onChanged: (msg: string) => void;
  onError: (m: string) => void;
}) {
  const qc = useQueryClient();
  const gateways = useQuery({ queryKey: ["gateways"], queryFn: fetchGateways });
  const enabledGateways = (gateways.data ?? []).filter((g) => g.enabled);
  const [gateway, setGateway] = useState<string>("");
  const [step, setStep] = useState<"init" | "gateway" | "result">("init");
  const [authority, setAuthority] = useState<string | null>(null);
  const [redirectUrl, setRedirectUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [gwAction, setGwAction] = useState<"approve" | "cancel">("approve");

  const reset = () => { setStep("init"); setAuthority(null); setResult(null); setGateway(""); };

  const init = async () => {
    if (!props.order) return;
    setBusy(true);
    try {
      const r = await startPayment(props.order.id, gateway || undefined);
      setAuthority(r.authority);
      setRedirectUrl(r.redirect_url);
      setStep("gateway");
    } catch (e) {
      props.onError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const doVerify = async (approve: boolean) => {
    if (!authority) return;
    setBusy(true);
    try {
      const r = await verifyPayment(authority, approve);
      if (r.ok) {
        setResult({ ok: true, text: `پرداخت تأیید شد (رسید: ${r.gateway_ref ?? "—"}) — فاکتور صادر گردید` });
        props.onChanged("پرداخت موفق و فاکتور صادر شد");
      } else {
        setResult({ ok: false, text: `پرداخت تأیید نشد: ${r.reason ?? "نامشخص"}` });
      }
      setStep("result");
    } catch (e) {
      props.onError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const payWallet = async () => {
    if (!props.order) return;
    setBusy(true);
    try {
      const r = await payOrderFromWallet(props.order.id);
      setResult({ ok: true, text: `پرداخت از کیف پول انجام شد (${fa(r.amount)} ریال) — فاکتور صادر گردید` });
      props.onChanged("پرداخت از کیف پول موفق بود");
      qc.invalidateQueries({ queryKey: ["my-wallet"] });
      setStep("result");
    } catch (e) {
      props.onError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={!!props.order} onClose={props.onClose} maxWidth="sm" fullWidth>
      <DialogTitle>پرداخت سفارش {props.order?.order_number}</DialogTitle>
      <DialogContent>
        {props.order && (
          <Typography variant="body1" sx={{ mb: 2 }}>
            مبلغ قابل پرداخت: <b>{fa(props.order.payable_amount)}</b> {props.order.currency}
          </Typography>
        )}
        {step === "init" && (
          <Stack spacing={2}>
            <Button variant="contained" color="secondary" disabled={busy} onClick={payWallet}>
              پرداخت از کیف پول (B18)
            </Button>
            <FormControl fullWidth size="small">
              <InputLabel>درگاه پرداخت (D02)</InputLabel>
              <Select value={gateway} label="درگاه پرداخت (D02)" onChange={(e) => setGateway(e.target.value)}>
                <MenuItem value=""><em>پیش‌فرض سامانه</em></MenuItem>
                {enabledGateways.map((g) => (
                  <MenuItem key={g.code} value={g.code}>{g.title}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <Button variant="contained" disabled={busy} onClick={init}>
              {busy ? "در حال اتصال…" : "انتقال به درگاه"}
            </Button>
          </Stack>
        )}
        {step === "gateway" && (
          <Stack spacing={2}>
            <Alert severity="info">
              این صفحه درگاه <b>شبیه‌ساز sandbox</b> است؛ در تولید (زرین‌پال) کاربر به
              صفحه واقعی درگاه هدایت می‌شود و پس از بازگشت، تأیید سمت سرور انجام می‌گیرد.
            </Alert>
            {redirectUrl && (
              <Typography variant="body2" sx={{ direction: "ltr", wordBreak: "break-all" }}>
                {redirectUrl}
              </Typography>
            )}
            <FormControl fullWidth size="small">
              <InputLabel>نتیجه درگاه شبیه‌ساز</InputLabel>
              <Select value={gwAction} label="نتیجه درگاه شبیه‌ساز"
                      onChange={(e) => setGwAction(e.target.value as "approve" | "cancel")}>
                <MenuItem value="approve">پرداخت موفق در درگاه</MenuItem>
                <MenuItem value="cancel">لغو توسط کاربر</MenuItem>
              </Select>
            </FormControl>
            <Button variant="contained" disabled={busy} onClick={() => doVerify(gwAction === "approve")}>
              {busy ? "در حال تأیید…" : "بازگشت از درگاه و تأیید سمت سرور"}
            </Button>
          </Stack>
        )}
        {step === "result" && result && (
          <Alert severity={result.ok ? "success" : "error"}>{result.text}</Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={() => { props.onClose(); reset(); }}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}

/* ------------------------------ سفارش جدید ------------------------------ */

function NewOrderDialog(props: {
  open: boolean;
  onClose: () => void;
  onCreated: (o: Order) => void;
  onError: (m: string) => void;
}) {
  const [serviceId, setServiceId] = useState("");
  const [discountCode, setDiscountCode] = useState("");
  const [preview, setPreview] = useState<{ valid: boolean; amount: number; reason: string | null } | null>(null);
  const [busy, setBusy] = useState(false);

  const services = useQuery({
    queryKey: ["all-services"],
    queryFn: async () => {
      const r = await apiClient.get("/services", { params: { status: "active", page_size: 100 } });
      return r.data.items as { id: string; title: string; current_price: number | null; current_currency: string | null }[];
    },
    enabled: props.open,
  });

  const checkCode = async () => {
    if (!discountCode.trim() || !Number(serviceId)) return;
    const svc = (services.data ?? []).find((s) => s.id === serviceId);
    if (!svc?.current_price) return;
    try {
      const r = await validateDiscount(discountCode.trim(), svc.current_price);
      setPreview({ valid: r.valid, amount: r.discount_amount, reason: r.reason });
    } catch (e) {
      props.onError(errDetail(e));
    }
  };

  const submit = async () => {
    if (!serviceId) return;
    setBusy(true);
    try {
      const o = await createOrder({
        service_id: serviceId,
        discount_code: discountCode.trim() || undefined,
      });
      props.onCreated(o);
      setServiceId("");
      setDiscountCode("");
      setPreview(null);
    } catch (e) {
      props.onError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={props.open} onClose={props.onClose} maxWidth="sm" fullWidth>
      <DialogTitle>سفارش جدید (B10)</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <Alert severity="info" sx={{ py: 1 }}>
            برای سفارشِ نوبت، مبلغ از <b>snapshot تعرفه</b> نوبت ساخته می‌شود (B07)؛
            کد تخفیف اعمال‌شده روی «قابل پرداخت» اثر می‌گذارد.
          </Alert>
          <FormControl fullWidth size="small" required>
            <InputLabel>خدمت</InputLabel>
            <Select value={serviceId} label="خدمت" onChange={(e) => { setServiceId(e.target.value); setPreview(null); }}>
              {(services.data ?? []).map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.title} {s.current_price !== null ? `— ${fa(s.current_price)} ${s.current_currency ?? "IRR"}` : ""}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Stack direction="row" spacing={1} alignItems="center">
            <TextField
              label="کد تخفیف (اختیاری — B19)" value={discountCode}
              onChange={(e) => { setDiscountCode(e.target.value); setPreview(null); }}
              slotProps={{ htmlInput: { style: { textTransform: "uppercase" } } }}
            />
            <Button disabled={!discountCode.trim() || !serviceId} onClick={checkCode}>بررسی</Button>
          </Stack>
          {preview && (
            <Alert severity={preview.valid ? "success" : "warning"} sx={{ py: 1 }}>
              {preview.valid ? `کد معتبر — تخفیف: ${fa(preview.amount)} ریال` : `کد نامعتبر: ${preview.reason}`}
            </Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={props.onClose}>انصراف</Button>
        <Button variant="contained" disabled={!serviceId || busy} onClick={submit}>ایجاد سفارش</Button>
      </DialogActions>
    </Dialog>
  );
}

/* ============================== کدهای تخفیف (B19) ============================== */

function DiscountsTab({ canManage }: { canManage: boolean }) {
  const qc = useQueryClient();
  const [newOpen, setNewOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  const discounts = useQuery({ queryKey: ["discounts"], queryFn: fetchDiscounts });

  const toggleMut = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      updateDiscount(id, { is_active }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["discounts"] });
      setOkMsg("وضعیت کد به‌روزرسانی شد");
      setError(null);
    },
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Stack spacing={2}>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {okMsg && <Alert severity="success" onClose={() => setOkMsg(null)}>{okMsg}</Alert>}
      {canManage && (
        <Box display="flex" justifyContent="flex-end">
          <Button variant="contained" onClick={() => setNewOpen(true)}>+ کد تخفیف جدید</Button>
        </Box>
      )}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>کد</TableCell>
              <TableCell>نوع</TableCell>
              <TableCell>مقدار</TableCell>
              <TableCell>سقف کل</TableCell>
              <TableCell>سقف هر کاربر</TableCell>
              <TableCell>اعتبار</TableCell>
              <TableCell>مصرف مؤثر</TableCell>
              <TableCell>وضعیت</TableCell>
              {canManage && <TableCell align="left">عملیات</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {discounts.isLoading && <TableRow><TableCell colSpan={9}>در حال بارگذاری…</TableCell></TableRow>}
            {!discounts.isLoading && (discounts.data ?? []).length === 0 && (
              <TableRow><TableCell colSpan={9}>کد تخفیفی ثبت نشده است</TableCell></TableRow>
            )}
            {(discounts.data ?? []).map((d) => (
              <TableRow key={d.id} hover>
                <TableCell sx={{ direction: "ltr", fontWeight: 700 }}>{d.code}</TableCell>
                <TableCell>{DISCOUNT_KIND[d.kind]}</TableCell>
                <TableCell>{d.kind === "percent" ? `${fa(d.value)}٪` : fa(d.value)}</TableCell>
                <TableCell>{d.max_uses ? fa(d.max_uses) : "بدون سقف"}</TableCell>
                <TableCell>{d.max_uses_per_user ? fa(d.max_uses_per_user) : "—"}</TableCell>
                <TableCell>
                  {d.starts_at ? `${d.starts_at} → ${d.expires_at ?? "باز"}` : d.expires_at ? `تا ${d.expires_at}` : "همیشه"}
                </TableCell>
                <TableCell>{fa(d.effective_uses ?? 0)}</TableCell>
                <TableCell>
                  <Chip size="small" color={d.is_active ? "success" : "default"}
                        label={d.is_active ? "فعال" : "غیرفعال"} />
                </TableCell>
                {canManage && (
                  <TableCell align="left">
                    <Button size="small" onClick={() =>
                      toggleMut.mutate({ id: d.id, is_active: !d.is_active })}>
                      {d.is_active ? "غیرفعال‌سازی" : "فعال‌سازی"}
                    </Button>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <NewDiscountDialog
        open={newOpen}
        onClose={() => setNewOpen(false)}
        onCreated={() => { setNewOpen(false); qc.invalidateQueries({ queryKey: ["discounts"] }); setOkMsg("کد تخفیف ایجاد شد"); }}
        onError={(m) => setError(m)}
      />
    </Stack>
  );
}

function NewDiscountDialog({ open, onClose, onCreated, onError }: {
  open: boolean; onClose: () => void; onCreated: () => void; onError: (m: string) => void;
}) {
  const [form, setForm] = useState({
    code: "", kind: "amount", value: "", max_uses: "", max_uses_per_user: "",
    expires_at: "", min_order_amount: "", note: "",
  });
  const [busy, setBusy] = useState(false);

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    setBusy(true);
    try {
      await createDiscount({
        code: form.code.trim().toUpperCase(),
        kind: form.kind,
        value: Number(form.value),
        max_uses: form.max_uses ? Number(form.max_uses) : undefined,
        max_uses_per_user: form.max_uses_per_user ? Number(form.max_uses_per_user) : undefined,
        expires_at: form.expires_at || undefined,
        min_order_amount: form.min_order_amount ? Number(form.min_order_amount) : undefined,
        note: form.note || undefined,
      });
      onCreated();
      setForm({ code: "", kind: "amount", value: "", max_uses: "", max_uses_per_user: "", expires_at: "", min_order_amount: "", note: "" });
    } catch (e) {
      onError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>کد تخفیف جدید (B19)</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <Stack direction="row" spacing={2}>
            <TextField required label="کد" value={form.code} sx={{ direction: "ltr" }}
                       onChange={(e) => set("code", e.target.value)} />
            <FormControl fullWidth size="small">
              <InputLabel>نوع</InputLabel>
              <Select value={form.kind} label="نوع" onChange={(e) => set("kind", e.target.value)}>
                <MenuItem value="amount">مبلغ ثابت (ریال)</MenuItem>
                <MenuItem value="percent">درصد</MenuItem>
              </Select>
            </FormControl>
            <TextField required label={form.kind === "percent" ? "درصد (۱-۱۰۰)" : "مبلغ (ریال)"}
                       type="number" value={form.value} onChange={(e) => set("value", e.target.value)} />
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField label="سقف کل (اختیاری)" type="number" fullWidth value={form.max_uses}
                       onChange={(e) => set("max_uses", e.target.value)} />
            <TextField label="سقف هر کاربر (اختیاری)" type="number" fullWidth value={form.max_uses_per_user}
                       onChange={(e) => set("max_uses_per_user", e.target.value)} />
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField label="تاریخ پایان (میلادی YYYY-MM-DD)" fullWidth slotProps={{ htmlInput: { dir: "ltr" } }}
                       value={form.expires_at} onChange={(e) => set("expires_at", e.target.value)} />
            <TextField label="حداقل مبلغ سفارش (ریال)" type="number" fullWidth value={form.min_order_amount}
                       onChange={(e) => set("min_order_amount", e.target.value)} />
          </Stack>
          <TextField label="یادداشت" multiline minRows={2} value={form.note} onChange={(e) => set("note", e.target.value)} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" disabled={busy || !form.code.trim() || !Number(form.value)} onClick={submit}>
          ایجاد
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/* ============================== استردادها (B20) ============================== */

function RefundsTab({ isManager }: { isManager: boolean }) {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");
  const [reviewFor, setReviewFor] = useState<{ row: RefundRequestRow; action: "approve" | "reject" } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  const refunds = useQuery({
    queryKey: ["refund-requests", statusFilter],
    queryFn: () => fetchRefundRequests(statusFilter || undefined),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["refund-requests"] });
    qc.invalidateQueries({ queryKey: ["orders"] });
    qc.invalidateQueries({ queryKey: ["my-wallet"] });
    qc.invalidateQueries({ queryKey: ["my-wallet-entries"] });
  };

  const reviewMut = useMutation({
    mutationFn: ({ id, action, note }: { id: string; action: "approve" | "reject"; note?: string }) =>
      reviewRefundRequest(id, action, note),
    onSuccess: (r) => { refresh(); setReviewFor(null); setOkMsg(`بررسی انجام شد: ${REFUND_STATUS[r.status]?.label ?? r.status}`); setError(null); },
    onError: (e) => setError(errDetail(e)),
  });

  const executeMut = useMutation({
    mutationFn: (id: string) => executeRefundRequest(id),
    onSuccess: (r) => { refresh(); setOkMsg(`استرداد اجرا شد (${fa(r.refund?.amount)} ریال از مسیر ${r.refund?.channel === "wallet" ? "کیف پول" : "درگاه"})`); setError(null); },
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Stack spacing={2}>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {okMsg && <Alert severity="success" onClose={() => setOkMsg(null)}>{okMsg}</Alert>}
      <Box display="flex" justifyContent="flex-end">
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>وضعیت</InputLabel>
          <Select value={statusFilter} label="وضعیت" onChange={(e) => setStatusFilter(e.target.value)}>
            <MenuItem value="">همه</MenuItem>
            {Object.entries(REFUND_STATUS).map(([k, v]) => (
              <MenuItem key={k} value={k}>{v.label}</MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>سفارش</TableCell>
              <TableCell>درخواست‌دهنده</TableCell>
              <TableCell>مبلغ (ریال)</TableCell>
              <TableCell>دلیل</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>یادداشت بررسی</TableCell>
              <TableCell>ثبت</TableCell>
              {isManager && <TableCell align="left">عملیات</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {refunds.isLoading && <TableRow><TableCell colSpan={isManager ? 8 : 7}>در حال بارگذاری…</TableCell></TableRow>}
            {!refunds.isLoading && (refunds.data ?? []).length === 0 && (
              <TableRow><TableCell colSpan={isManager ? 8 : 7}>درخواستی یافت نشد</TableCell></TableRow>
            )}
            {(refunds.data ?? []).map((r) => (
              <TableRow key={r.id} hover>
                <TableCell sx={{ direction: "ltr" }}>{r.order_number ?? "—"}</TableCell>
                <TableCell>{r.requested_by_name ?? "—"}</TableCell>
                <TableCell>{fa(r.amount)}</TableCell>
                <TableCell sx={{ maxWidth: 200 }}>{r.reason}</TableCell>
                <TableCell>
                  <Chip size="small" color={REFUND_STATUS[r.status]?.color ?? "default"}
                        label={REFUND_STATUS[r.status]?.label ?? r.status} />
                </TableCell>
                <TableCell sx={{ maxWidth: 180 }}>{r.decision_note ?? "—"}</TableCell>
                <TableCell>{formatJalaliDateTime(r.created_at)}</TableCell>
                {isManager && (
                  <TableCell align="left">
                    <Stack direction="row" spacing={0.5}>
                      {r.status === "pending" && (
                        <>
                          <Button size="small" color="success"
                                  onClick={() => setReviewFor({ row: r, action: "approve" })}>تأیید</Button>
                          <Button size="small" color="error"
                                  onClick={() => setReviewFor({ row: r, action: "reject" })}>رد</Button>
                        </>
                      )}
                      {r.status === "approved" && (
                        <Button size="small" variant="contained" onClick={() => executeMut.mutate(r.id)}>اجرا</Button>
                      )}
                    </Stack>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <ReviewDialog
        state={reviewFor}
        onClose={() => setReviewFor(null)}
        onSubmit={(note) => {
          if (reviewFor) reviewMut.mutate({ id: reviewFor.row.id, action: reviewFor.action, note });
        }}
        busy={reviewMut.isPending}
      />
    </Stack>
  );
}

function ReviewDialog({ state, onClose, onSubmit, busy }: {
  state: { row: RefundRequestRow; action: "approve" | "reject" } | null;
  onClose: () => void;
  onSubmit: (note: string) => void;
  busy: boolean;
}) {
  const [note, setNote] = useState("");
  return (
    <Dialog open={!!state} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>
        {state?.action === "approve" ? "تأیید درخواست استرداد" : "رد درخواست استرداد"}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {state && (
            <Typography variant="body2">
              سفارش {state.row.order_number} — مبلغ {fa(state.row.amount)} ریال
            </Typography>
          )}
          <TextField label="یادداشت (اختیاری)" multiline minRows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button
          variant="contained" color={state?.action === "approve" ? "success" : "error"}
          disabled={busy} onClick={() => { onSubmit(note); setNote(""); }}
        >
          ثبت بررسی
        </Button>
      </DialogActions>
    </Dialog>
  );
}
