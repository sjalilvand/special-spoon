import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import {
  APPOINTMENT_STATUS_META, createAppointment, fetchAppointments, updateAppointment,
} from "../api/schedule";
import type { AppointmentRow } from "../api/schedule";
import { formatJalaliDateTime } from "../utils/jalali";

export default function CaseAppointments({ caseId }: { caseId: string }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const roles = user?.roles ?? [];
  const canCreate =
    roles.includes("ORG_MANAGER") || roles.includes("RECEPTION") || roles.includes("COUNSELOR");

  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["appointments", caseId],
    queryFn: () => fetchAppointments({ case_id: caseId }),
  });

  useEffect(() => {
    if (open) setForm({});
  }, [open]);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["appointments", caseId] });

  const setStatus = useMutation({
    mutationFn: (p: { id: AppointmentRow["id"]; status: string }) =>
      updateAppointment(p.id, { status: p.status }),
    onSuccess: invalidate,
    onError: (e) => setError(errDetail(e)),
  });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!form.scheduled_at) {
      setError("تعیین زمان نوبت الزامی است");
      return;
    }
    try {
      await createAppointment({
        case_id: caseId,
        scheduled_at: new Date(form.scheduled_at).toISOString(),
        duration_minutes: form.duration_minutes ? Number(form.duration_minutes) : undefined,
        location: form.location?.trim() || undefined,
        note: form.note?.trim() || undefined,
      });
      setOpen(false);
      invalidate();
    } catch (err) {
      setError(errDetail(err));
    }
  };

  const set = (k: string) => (e: { target: { value: string } }) =>
    setForm((p) => ({ ...p, [k]: e.target.value }));

  return (
    <Paper sx={{ p: 2 }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
        <Typography variant="subtitle1" fontWeight={700}>نوبت‌ها</Typography>
        {canCreate && (
          <Button size="small" variant="contained" onClick={() => setOpen(true)}>نوبت جدید</Button>
        )}
      </Box>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>زمان</TableCell>
              <TableCell>مدت (دقیقه)</TableCell>
              <TableCell>محل</TableCell>
              <TableCell>وضعیت</TableCell>
              {canCreate && <TableCell>عملیات</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={5} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.length === 0 && (
              <TableRow><TableCell colSpan={5}>نوبتی ثبت نشده است.</TableCell></TableRow>
            )}
            {data?.items.map((row) => {
              const m = APPOINTMENT_STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
              return (
                <TableRow key={row.id}>
                  <TableCell>{formatJalaliDateTime(row.scheduled_at)}</TableCell>
                  <TableCell>{row.duration_minutes ?? "—"}</TableCell>
                  <TableCell>{row.location ?? "—"}</TableCell>
                  <TableCell><Chip size="small" color={m.color} label={m.label} /></TableCell>
                  {canCreate && (
                    <TableCell>
                      {row.status === "scheduled" ? (
                        <Stack direction="row" spacing={0.5}>
                          <Button size="small" onClick={() => setStatus.mutate({ id: row.id, status: "done" })}>
                            انجام شد
                          </Button>
                          <Button size="small" color="warning"
                            onClick={() => setStatus.mutate({ id: row.id, status: "no_show" })}>
                            عدم حضور
                          </Button>
                          <Button size="small" color="error"
                            onClick={() => setStatus.mutate({ id: row.id, status: "cancelled" })}>
                            لغو
                          </Button>
                        </Stack>
                      ) : "—"}
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="xs" fullWidth>
        <form onSubmit={submit}>
          <DialogTitle>نوبت جدید</DialogTitle>
          <DialogContent>
            <Stack spacing={2} mt={1}>
              <TextField
                label="زمان نوبت *"
                type="datetime-local"
                value={form.scheduled_at ?? ""}
                onChange={set("scheduled_at")}
                required
                fullWidth
              />
              <TextField
                label="مدت (دقیقه)"
                type="number"
                value={form.duration_minutes ?? ""}
                onChange={set("duration_minutes")}
                fullWidth
              />
              <TextField label="محل" value={form.location ?? ""} onChange={set("location")} fullWidth />
              <TextField label="یادداشت" value={form.note ?? ""} onChange={set("note")} fullWidth multiline minRows={2} />
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setOpen(false)}>انصراف</Button>
            <Button type="submit" variant="contained">ثبت نوبت</Button>
          </DialogActions>
        </form>
      </Dialog>
    </Paper>
  );
}
