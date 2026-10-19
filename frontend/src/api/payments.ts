// فاز ۲۹ - B10/B11 سند جامع: سفارش، پرداخت و فاکتور (تصمیم D02: درگاه پلاگین‌پذیر)
import { apiClient } from "./client";

export interface OrderPayment {
  id: string;
  gateway: string;
  amount: number;
  status: "initiated" | "success" | "failed";
  authority: string;
  gateway_ref: string | null;
  fail_reason: string | null;
  paid_at: string | null;
  created_at: string | null;
}

export interface Order {
  id: string;
  order_number: string;
  owner_user_id: string;
  case_id: string | null;
  appointment_id: string | null;
  service_id: string | null;
  title: string;
  amount: number;
  currency: string;
  discount_amount: number | null;
  payable_amount: number;
  status: "pending" | "paid" | "cancelled" | "failed";
  note: string | null;
  created_at: string | null;
  invoice_id: string | null;
  invoice_number: string | null;
  payments?: OrderPayment[];
}

export interface GatewayInfo {
  code: string;
  title: string;
  enabled: boolean;
  is_default: boolean;
  merchant_configured?: boolean;
  sandbox?: boolean;
}

export interface InvoiceItem {
  id: string;
  description: string;
  quantity: number;
  unit_amount: number;
  line_total: number;
}

export interface Invoice {
  id: string;
  invoice_number: string;
  order_id: string;
  order_number: string | null;
  total_amount: number;
  currency: string;
  buyer_name: string | null;
  buyer_national_id: string | null;
  buyer_email: string | null;
  status: "issued" | "void";
  issued_at: string;
  items: InvoiceItem[];
}

export async function fetchOrders(status?: string): Promise<Order[]> {
  const r = await apiClient.get<{ items: Order[] }>("/orders", {
    params: status ? { status } : {},
  });
  return r.data.items;
}

export async function fetchOrder(id: string): Promise<Order> {
  const r = await apiClient.get<Order>(`/orders/${id}`);
  return r.data;
}

export async function createOrder(payload: {
  appointment_id?: string;
  service_id?: string;
  discount_amount?: number;
  note?: string;
}): Promise<Order> {
  const r = await apiClient.post<Order>("/orders", payload);
  return r.data;
}

export async function cancelOrder(id: string): Promise<Order> {
  const r = await apiClient.post<Order>(`/orders/${id}/cancel`);
  return r.data;
}

export async function fetchGateways(): Promise<GatewayInfo[]> {
  const r = await apiClient.get<{ items: GatewayInfo[] }>("/payments/gateways");
  return r.data.items;
}

export async function startPayment(orderId: string, gateway?: string): Promise<{
  payment_id: string;
  authority: string;
  gateway: string;
  amount: number;
  redirect_url: string;
}> {
  const r = await apiClient.post(`/orders/${orderId}/payments`, { gateway });
  return r.data;
}

export async function verifyPayment(authority: string, approve = true): Promise<{
  payment_id: string;
  authority: string;
  status: string;
  ok: boolean;
  reason: string | null;
  gateway_ref: string | null;
  order_status: string | null;
  idempotent: boolean;
}> {
  const r = await apiClient.post(`/payments/${authority}/verify`, null, {
    params: { approve: approve ? "true" : "false" },
  });
  return r.data;
}

export async function fetchInvoices(): Promise<Invoice[]> {
  const r = await apiClient.get<{ items: Invoice[] }>("/invoices");
  return r.data.items;
}

export async function fetchInvoice(id: string): Promise<Invoice> {
  const r = await apiClient.get<Invoice>(`/invoices/${id}`);
  return r.data;
}
