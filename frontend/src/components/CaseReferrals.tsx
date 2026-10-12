import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, FormControl, FormControlLabel, InputLabel, MenuItem, Paper, Radio,
  RadioGroup, Select, Stack, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import {
  REFERRAL_DIRECTION_LABELS, REFERRAL_STATUS_META, createReferral, fetchCaseReferrals, updateReferral,
} from "../api/referrals";
import type { ReferralRow } from "../api/referrals";
import { fetchCounselorOptions, fetchServiceLocations } from "../api/people";
import type { IdName } from "../api/people";

export default function CaseReferrals({ caseId }: { caseId: string }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const roles = user?.roles ?? [];
  const canWrite = roles.includes("COUNSELOR") || roles.includes("ORG_MANAGER");

  const [createOpen, setCreateOpen] = useState(false);
  const [updateRow, setUpdateRow] = useState<ReferralRow | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["referrals", caseId],
    queryFn: () => fetchCaseReferrals(caseId),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["referrals", caseId] });

  return (
    <Paper sx={{ p: 2 }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
        <Typography variant="subtitle1" fontWeight={700}>ارجاع‌ها</Typography>
        {canWrite && (
          <Button size="small" variant="contained" onClick={() => setCreateOpen(true)}>ارجاع جدید</Button>
        )}
      </Box>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {isLoading && <CircularProgress size={24} />}

      <Stack spacing={1.5}>
        {data?.items.length === 0 && (
          <Typography variant="body2" color="text.secondary">ارجاعی ثبت نشده است.</Typography>
        )}
        {data?.items.map((row) => {
          const st = REFERRAL_STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
          return (
            <Box key={row.id} sx={{ border: 1, borderColor: "divider", borderRadius: 2, p: 2 }}>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Chip size="small" color={st.color} label={st.label} />
                <Chip size="small" variant="outlined"
                  label={REFERRAL_DIRECTION_LABELS[row.direction] ?? row.direction} />
                {row.target_label && (
                  <Typography variant="body2">{row.target_label}</Typography>
                )}
                <Box flexGrow={1} />
                <Typography variant="caption" color="text.secondary">
                  {row.referral_date ? new Date(row.referral_date).toLocaleDateString("fa-IR") : "—"} — {row.requested_by_name ?? ""}
                </Typography>
              </Stack>
              <Typography variant="body2" mt={0.5}>
                <b>علت:</b> {row.reason}
              </Typography>
              {row.notes && (
                <Typography variant="body2" color="text.secondary">
                  <b>یادداشت:</b> {row.notes}
                </Typography>
              )}
              {row.outcome && (
                <Typography variant="body2" color="primary.main">
                  <b>نتیجه:</b> {row.outcome}
                  {row.outcome_date ? ` (${new Date(row.outcome_date).toLocaleDateString("fa-IR")})` : ""}
                </Typography>
              )}
              {canWrite && !["completed", "cancelled"].includes(row.status) && (
                <Button size="small" variant="outlined" sx={{ mt: 1 }} onClick={() => setUpdateRow(row)}>
                  پیگیری / ثبت نتیجه
                </Button>
              )}
            </Box>
          );
        })}
      </Stack>

      <CreateReferralDialog
        open={createOpen}
        caseId={caseId}
        onClose={() => setCreateOpen(false)}
        invalidate={invalidate}
        onError={setError}
      />
      <UpdateReferralDialog
        row={updateRow}
        onClose={() => setUpdateRow(null)}
        invalidate={invalidate}
        onError={setError}
      />
    </Paper>
  );
}

function CreateReferralDialog({ open, caseId, onClose, invalidate, onError }: {
  open: boolean; caseId: string; onClose: () => void; invalidate: () => void; onError: (m: string) => void;
}) {
  const [direction, setDirection] = useState<"internal" | "cross_center" | "external">("internal");
  const [counselorId, setCounselorId] = useState("");
  const [serviceLocationId, setServiceLocationId] = useState("");
  const [centerName, setCenterName] = useState("");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [referralDate, setReferralDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: counselors } = useQuery({
    queryKey: ["counselor-options"],
    queryFn: fetchCounselorOptions,
    enabled: open && direction === "internal",
  });
  const { data: locations } = useQuery({
    queryKey: ["locations"],
    queryFn: fetchServiceLocations,
    enabled: open && direction === "cross_center",
  });

  useEffect(() => {
    if (open) {
      setDirection("internal"); setCounselorId(""); setServiceLocationId("");
      setCenterName(""); setReason(""); setNotes(""); setReferralDate(""); setFormError(null);
    }
  }, [open]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await createReferral(caseId, {
        direction,
        to_counselor_id: direction === "internal" ? counselorId || undefined : undefined,
        to_service_location_id: direction === "cross_center" ? serviceLocationId || undefined : undefined,
        to_center_name: direction === "external" ? centerName.trim() || undefined : undefined,
        reason: reason.trim(),
        notes: notes.trim() || undefined,
        referral_date: referralDate.trim() || undefined,
      });
      invalidate();
      onClose();
    } catch (err) {
      setFormError(errDetail(err));
      onError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>ثبت ارجاع جدید</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          <Stack spacing={2} mt={2}>
            <FormControl>
              <RadioGroup row value={direction} onChange={(e) => setDirection(e.target.value as typeof direction)}>
                <FormControlLabel value="internal" control={<Radio />} label="داخلی (مشاور دیگر)" />
                <FormControlLabel value="cross_center" control={<Radio />} label="بین‌مرکزی (شعبه)" />
                <FormControlLabel value="external" control={<Radio />} label="خارجی" />
              </RadioGroup>
            </FormControl>

            {direction === "internal" && (
              <FormControl size="small" fullWidth required>
                <InputLabel>مشاور مقصد *</InputLabel>
                <Select value={counselorId} label="مشاور مقصد *"
                  onChange={(e) => setCounselorId(e.target.value)}>
                  <MenuItem value="">— انتخاب کنید —</MenuItem>
                  {counselors?.items.map((o: IdName) => (
                    <MenuItem key={o.id} value={o.id}>{o.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}

            {direction === "cross_center" && (
              <FormControl size="small" fullWidth required>
                <InputLabel>مرکز مقصد *</InputLabel>
                <Select value={serviceLocationId} label="مرکز مقصد *"
                  onChange={(e) => setServiceLocationId(e.target.value)}>
                  <MenuItem value="">— انتخاب کنید —</MenuItem>
                  {locations?.map((l) => (
                    <MenuItem key={l.id} value={l.id}>{l.title} ({l.code})</MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}

            {direction === "external" && (
              <TextField
                label="نام مرکز/پزشک خارجی *"
                value={centerName}
                onChange={(e) => setCenterName(e.target.value)}
                required
                fullWidth
              />
            )}

            <TextField
              label="علت ارجاع *"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
              multiline
              minRows={2}
              fullWidth
            />
            <TextField
              label="یادداشت (اختیاری)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              multiline
              minRows={2}
              fullWidth
            />
            <TextField
              label="تاریخ ارجاع (مثال: 1403/06/01 شمسی یا 2024-08-22 میلادی)"
              value={referralDate}
              onChange={(e) => setReferralDate(e.target.value)}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>
            {busy ? "در حال ثبت…" : "ثبت ارجاع"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function UpdateReferralDialog({ row, onClose, invalidate, onError }: {
  row: ReferralRow | null; onClose: () => void; invalidate: () => void; onError: (m: string) => void;
}) {
  const qc = useQueryClient();
  const [status, setStatus] = useState("accepted");
  const [outcome, setOutcome] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (row) {
      setStatus(row.status === "initiated" ? "accepted" : row.status);
      setOutcome(row.outcome ?? "");
      setNotes(row.notes ?? "");
      setFormError(null);
    }
  }, [row]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!row) return;
    setFormError(null);
    setBusy(true);
    try {
      await updateReferral(row.id, {
        status,
        outcome: outcome.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      invalidate();
      qc.invalidateQueries({ queryKey: ["worklist-referrals"] });
      onClose();
    } catch (err) {
      setFormError(errDetail(err));
      onError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={row !== null} onClose={onClose} maxWidth="xs" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>پیگیری ارجاع</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          <Stack spacing={2} mt={2}>
            <FormControl size="small" fullWidth>
              <InputLabel>وضعیت</InputLabel>
              <Select value={status} label="وضعیت" onChange={(e) => setStatus(e.target.value)}>
                {Object.entries(REFERRAL_STATUS_META).map(([k, v]) => (
                  <MenuItem key={k} value={k}>{v.label}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="نتیجه ارجاع"
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
              multiline
              minRows={2}
              fullWidth
            />
            <TextField
              label="یادداشت"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              multiline
              minRows={2}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>ثبت</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
