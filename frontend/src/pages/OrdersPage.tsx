import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControl,
  InputLabel, MenuItem, Paper, Select, Stack, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { errDetail } from "../api/client";
import { apiClient } from "../api/client";
import { createOrder, cancelOrder, fetchGateways, fetchOrders, Order, startPayment, verifyPayment } from "../api/payments";
import { formatJalaliDateTime } from "../utils/jalali";

// فاز ۲۹ - B10 سند جامع: سفارش و پرداخت — تأیید قطعی سمت سرور،
// callback تکراری بی‌اثر؛ درگاه پیش‌فرض sandbox (تصمیم D02)

const fa = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : Number(n).toLocaleString("fa-IR");

const ORDER_STATUS: Record<string, { label: string; color: "success" | "warning" | "error" | "default" }> = {
  pending: { label: "در انتظار پرداخت", color: "warning" },
  paid: { label: "پرداخت‌شده", color: "success" },
  cancelled: { label: "لغوشده", color: "default" },
  failed: { label: "ناموفق", color: "error" },
};


export default function OrdersPage() {
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
      setOkMsg(`سفارش ${o.order_number} لغو شد`);
      setError(null);
    },
    onError: (e) => setError(errDetail(e)),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["orders"] });
    qc.invalidateQueries({ queryKey: ["invoices"] });
  };

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={800}>سفارش‌ها و پرداخت (B10)</Typography>
        <Box flexGrow={1} />
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>وضعیت</InputLabel>
          <Select value={statusFilter} label="وضعیت" onChange={(e) => setStatusFilter(e.target.value)}>
            <MenuItem value="">همه</MenuItem>
            {Object.entries(ORDER_STATUS).map(([k, v]) => (
              <MenuItem key={k} value={k}>{v.label}</MenuItem>
            ))}
          </Select>
        </FormControl>
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

/* ------------------------------ جدول سفارش‌ها ------------------------------ */

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
              <TableCell>مبلغ (ریال)</TableCell>
              <TableCell>قابل پرداخت</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>فاکتور</TableCell>
              <TableCell>ایجاد</TableCell>
              <TableCell align="left">عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {props.loading && <TableRow><TableCell colSpan={8}>در حال بارگذاری…</TableCell></TableRow>}
            {!props.loading && props.orders.length === 0 && (
              <TableRow><TableCell colSpan={8}>سفارشی یافت نشد</TableCell></TableRow>
            )}
            {props.orders.map((o) => (
              <TableRow key={o.id} hover>
                <TableCell sx={{ direction: "ltr" }}>{o.order_number}</TableCell>
                <TableCell sx={{ maxWidth: 220 }}>{o.title}</TableCell>
                <TableCell>{fa(o.amount)}</TableCell>
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
  const [discount, setDiscount] = useState("");
  const [busy, setBusy] = useState(false);

  const services = useQuery({
    queryKey: ["all-services"],
    queryFn: async () => {
      const r = await apiClient.get("/services", { params: { status: "active", page_size: 100 } });
      return r.data.items as { id: string; title: string; current_price: number | null; current_currency: string | null }[];
    },
    enabled: props.open,
  });

  const submit = async () => {
    if (!serviceId) return;
    setBusy(true);
    try {
      const o = await createOrder({
        service_id: serviceId,
        discount_amount: discount ? Number(discount) : undefined,
      });
      props.onCreated(o);
      setServiceId("");
      setDiscount("");
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
            برای سفارشِ نوبت، از صفحه پرونده/نوبت‌ها شماره نوبت را همراه داشته باشید؛
            مبلغ سفارش از <b>snapshot تعرفه</b> نوبت یا تعرفه جاری خدمت ساخته می‌شود (B07).
          </Alert>
          <FormControl fullWidth size="small" required>
            <InputLabel>خدمت</InputLabel>
            <Select value={serviceId} label="خدمت" onChange={(e) => setServiceId(e.target.value)}>
              {(services.data ?? []).map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.title} {s.current_price !== null ? `— ${fa(s.current_price)} ${s.current_currency ?? "IRR"}` : ""}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="تخفیف (ریال — اختیاری)" type="number" value={discount}
            onChange={(e) => setDiscount(e.target.value)} slotProps={{ htmlInput: { min: 0 } }}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={props.onClose}>انصراف</Button>
        <Button variant="contained" disabled={!serviceId || busy} onClick={submit}>ایجاد سفارش</Button>
      </DialogActions>
    </Dialog>
  );
}
