// فاز ۳۰ - B18/B19/B20 سند جامع: کیف پول، کد تخفیف و استرداد وجه
import { apiClient } from "./client";

/* ------------------------------ B18 کیف پول ------------------------------ */

export interface WalletInfo {
  id: string;
  user_id: string;
  user_name: string | null;
  username?: string | null;
  balance: number;
  currency: string;
  is_active?: boolean;
}

export interface WalletEntry {
  id: string;
  direction: "credit" | "debit";
  reason: "topup" | "payment" | "refund" | "adjustment";
  amount: number;
  balance_after: number;
  currency: string;
  order_id: string | null;
  payment_id: string | null;
  refund_id: string | null;
  note: string | null;
  created_at: string | null;
}

export const REASON_LABEL: Record<string, string> = {
  topup: "شارژ از درگاه",
  payment: "پرداخت سفارش",
  refund: "بازگشت استرداد",
  adjustment: "تعدیل مدیریتی",
};

export async function fetchMyWallet(): Promise<WalletInfo> {
  return (await apiClient.get<WalletInfo>("/wallet")).data;
}

export async function fetchMyWalletEntries(): Promise<WalletEntry[]> {
  return (await apiClient.get<{ items: WalletEntry[] }>("/wallet/entries")).data.items;
}

export async function walletTopup(amount: number, gateway?: string): Promise<{
  order_id: string;
  order_number: string;
  payment_id: string;
  authority: string;
  redirect_url: string;
}> {
  const r = await apiClient.post("/wallet/topup", { amount, gateway });
  return r.data;
}

export async function payOrderFromWallet(orderId: string): Promise<{
  payment_id: string;
  gateway: string;
  amount: number;
  order_status: string;
}> {
  const r = await apiClient.post(`/orders/${orderId}/pay-from-wallet`);
  return r.data;
}

export async function fetchWallets(): Promise<WalletInfo[]> {
  return (await apiClient.get<{ items: WalletInfo[] }>("/wallets")).data.items;
}

export async function fetchUserWalletEntries(userId: string): Promise<WalletEntry[]> {
  return (await apiClient.get<{ items: WalletEntry[] }>(`/wallets/${userId}/entries`)).data.items;
}

export async function adjustWallet(userId: string, payload: {
  amount: number;
  note: string;
}): Promise<WalletInfo> {
  const r = await apiClient.post<WalletInfo>(`/wallets/${userId}/adjust`, payload);
  return r.data;
}

/* ------------------------------ B19 کد تخفیف ------------------------------ */

export interface Discount {
  id: string;
  code: string;
  kind: "amount" | "percent";
  value: number;
  currency: string;
  max_uses: number | null;
  max_uses_per_user: number | null;
  starts_at: string | null;
  expires_at: string | null;
  min_order_amount: number | null;
  is_active: boolean;
  note: string | null;
  effective_uses?: number;
  created_at: string | null;
}

export async function fetchDiscounts(): Promise<Discount[]> {
  return (await apiClient.get<{ items: Discount[] }>("/discounts")).data.items;
}

export async function createDiscount(payload: Record<string, unknown>): Promise<Discount> {
  const r = await apiClient.post<Discount>("/discounts", payload);
  return r.data;
}

export async function updateDiscount(id: string, payload: Record<string, unknown>): Promise<Discount> {
  const r = await apiClient.patch<Discount>(`/discounts/${id}`, payload);
  return r.data;
}

export async function validateDiscount(code: string, amount: number): Promise<{
  valid: boolean;
  reason: string | null;
  discount_amount: number;
}> {
  const r = await apiClient.post("/discounts/validate", { code, amount });
  return r.data;
}

/* ------------------------------ B20 استرداد ------------------------------ */

export interface RefundRequestRow {
  id: string;
  order_id: string;
  order_number: string | null;
  requested_by: string;
  requested_by_name: string | null;
  amount: number;
  currency: string;
  reason: string;
  status: "pending" | "approved" | "rejected" | "executed";
  decided_at: string | null;
  decision_note: string | null;
  created_at: string | null;
  refund: {
    id: string;
    channel: string;
    gateway: string | null;
    gateway_ref: string | null;
    amount: number;
    executed_at: string | null;
  } | null;
}

export async function createRefundRequest(payload: {
  order_id: string;
  amount: number;
  reason: string;
}): Promise<RefundRequestRow> {
  const r = await apiClient.post<RefundRequestRow>("/refund-requests", payload);
  return r.data;
}

export async function fetchRefundRequests(status?: string): Promise<RefundRequestRow[]> {
  return (
    await apiClient.get<{ items: RefundRequestRow[] }>("/refund-requests", {
      params: status ? { status } : {},
    })
  ).data.items;
}

export async function reviewRefundRequest(id: string, action: "approve" | "reject", note?: string): Promise<RefundRequestRow> {
  const r = await apiClient.post<RefundRequestRow>(`/refund-requests/${id}/review`, { action, note });
  return r.data;
}

export async function executeRefundRequest(id: string): Promise<RefundRequestRow> {
  const r = await apiClient.post<RefundRequestRow>(`/refund-requests/${id}/execute`);
  return r.data;
}
