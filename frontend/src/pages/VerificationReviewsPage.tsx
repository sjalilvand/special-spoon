import {
  Alert, Box, Button, Chip, CircularProgress, Paper, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { errDetail } from "../api/client";
import { fetchVerificationReviews, reviewCredential } from "../api/catalog";
import type { CounselorCredential } from "../api/catalog";
import { formatJalali } from "../utils/jalali";

// فاز ۲۸ - B05 سند جامع: صفحه /verification-reviews
// بازبینی مدارک مشاوران؛ نتیجه تأیید مستقیماً مشاور را «قابل رزرو» می‌کند

const KIND: Record<string, string> = {
  license: "مجوز حرفه‌ای",
  degree: "مدرک تحصیلی",
  certificate: "گواهی‌نامه",
};

const STATUS: Record<string, { label: string; color: "warning" | "success" | "error" }> = {
  pending: { label: "در انتظار بررسی", color: "warning" },
  approved: { label: "تأییدشده", color: "success" },
  rejected: { label: "ردشده", color: "error" },
};

export default function VerificationReviewsPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<"pending" | "approved" | "rejected" | "all">("pending");
  const [error, setError] = useState<string | null>(null);

  const { data: items, isLoading } = useQuery({
    queryKey: ["verification-reviews", statusFilter],
    queryFn: () => fetchVerificationReviews(statusFilter),
  });

  const review = useMutation({
    mutationFn: ({ id, action, note }: { id: string; action: "approve" | "reject"; note?: string }) =>
      reviewCredential(id, action, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["verification-reviews"] });
      queryClient.invalidateQueries({ queryKey: ["counselors"] });
    },
    onError: (e) => setError(errDetail(e)),
  });

  const decide = (row: CounselorCredential, action: "approve" | "reject") => {
    const note = action === "reject" ? window.prompt("دلیل رد (اختیاری):") ?? undefined : undefined;
    if (action === "approve" && !window.confirm(`تأیید «${row.title}» برای ${row.counselor_name ?? "این مشاور"}؟`)) return;
    review.mutate({ id: row.id, action, note });
  };

  return (
    <Stack spacing={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center" gap={2} flexWrap="wrap">
        <Typography variant="h6" fontWeight={700}>بازبینی صلاحیت مشاوران (B05)</Typography>
        <Stack direction="row" spacing={1}>
          {([["pending", "در انتظار"], ["approved", "تأییدشده"], ["rejected", "ردشده"], ["all", "همه"]] as const).map(
            ([v, label]) => (
              <Chip key={v} label={label} clickable color={statusFilter === v ? "primary" : "default"}
                onClick={() => setStatusFilter(v)} />
            ),
          )}
        </Stack>
      </Box>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      <Alert severity="info" variant="outlined">
        مشاور بدون حداقل یک مدرک «تأییدشده و معتبر» در فهرست قابل رزرو عمومی نمایش داده نمی‌شود
        (قاعده B05 سند جامع).
      </Alert>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>مشاور</TableCell>
              <TableCell>نوع</TableCell>
              <TableCell>عنوان مدرک</TableCell>
              <TableCell>شماره</TableCell>
              <TableCell>صدور</TableCell>
              <TableCell>انقضا</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={8} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {items?.map((row) => {
              const st = STATUS[row.verification_status] ?? { label: row.verification_status, color: "default" as never };
              return (
                <TableRow key={row.id}>
                  <TableCell>{row.counselor_name ?? row.counselor_code ?? row.counselor_id}</TableCell>
                  <TableCell>{KIND[row.kind] ?? row.kind}</TableCell>
                  <TableCell>{row.title}</TableCell>
                  <TableCell>{row.license_number ?? "—"}</TableCell>
                  <TableCell>{row.issued_at ? formatJalali(row.issued_at) : "—"}</TableCell>
                  <TableCell>{row.expires_at ? formatJalali(row.expires_at) : "—"}</TableCell>
                  <TableCell>
                    <Chip size="small" label={st.label} color={st.color} />
                    {row.review_note && (
                      <Typography variant="caption" display="block" color="text.secondary">
                        {row.review_note}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    {row.verification_status === "pending" ? (
                      <Stack direction="row" spacing={1}>
                        <Button size="small" color="success" onClick={() => decide(row, "approve")}>تأیید</Button>
                        <Button size="small" color="error" onClick={() => decide(row, "reject")}>رد</Button>
                      </Stack>
                    ) : "—"}
                  </TableCell>
                </TableRow>
              );
            })}
            {!isLoading && items?.length === 0 && (
              <TableRow><TableCell colSpan={8} align="center">موردی برای نمایش وجود ندارد</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}
