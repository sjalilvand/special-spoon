import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, MenuItem, Paper, Stack, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import {
  SESSION_FIELD_LABELS, SESSION_NOTE_STATUS_META, createSession,
  createSessionNoteRevision, fetchAppointments, fetchCaseSessions,
  finalizeSessionNote, saveSessionNote,
} from "../api/schedule";
import type { SessionRow } from "../api/schedule";

export default function CaseSessions({ caseId }: { caseId: string }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const roles = user?.roles ?? [];
  const isCounselor = roles.includes("COUNSELOR");

  const [createOpen, setCreateOpen] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<SessionRow | null>(null);
  const [noteContent, setNoteContent] = useState<Record<string, string>>({});
  const [noteError, setNoteError] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["sessions", caseId],
    queryFn: () => fetchCaseSessions(caseId),
  });

  const { data: openAppts } = useQuery({
    queryKey: ["appointments", caseId, "scheduled"],
    queryFn: () => fetchAppointments({ case_id: caseId, status: "scheduled" }),
    enabled: createOpen && isCounselor,
  });

  useEffect(() => {
    if (createOpen) { setCreateForm({}); setCreateError(null); }
  }, [createOpen]);

  useEffect(() => {
    if (editing) {
      const c: Record<string, string> = {};
      Object.keys(SESSION_FIELD_LABELS).forEach((k) => { c[k] = editing.content[k] ?? ""; });
      setNoteContent(c);
      setNoteError(null);
    }
  }, [editing]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["sessions", caseId] });
    qc.invalidateQueries({ queryKey: ["appointments", caseId] });
  };

  const doCreate = async () => {
    setCreateError(null);
    if (!createForm.occurred_at) {
      setCreateError("تعیین زمان واقعی جلسه الزامی است");
      return;
    }
    try {
      const content: Record<string, string> = {};
      Object.keys(SESSION_FIELD_LABELS).forEach((k) => {
        const v = createForm[k]?.trim();
        if (v) content[k] = v;
      });
      await createSession(caseId, {
        occurred_at: new Date(createForm.occurred_at).toISOString(),
        appointment_id: createForm.appointment_id || undefined,
        content,
      });
      setCreateOpen(false);
      invalidate();
    } catch (e) {
      setCreateError(errDetail(e));
    }
  };

  const doSaveNote = async () => {
    if (!editing) return;
    setNoteError(null);
    try {
      const res = await saveSessionNote(editing.id, {
        content: noteContent,
        expected_version: editing.note_version,
      });
      setEditing(res);
      invalidate();
    } catch (e) {
      setNoteError(errDetail(e));
    }
  };

  const doFinalize = async () => {
    if (!editing || !window.confirm("نهایی‌سازی یادداشت؟ پس از آن بی‌ردپا تغییر نمی‌کند.")) return;
    setNoteError(null);
    try {
      const res = await finalizeSessionNote(editing.id);
      setEditing(res);
      invalidate();
    } catch (e) {
      setNoteError(errDetail(e));
    }
  };

  const doNewRevision = async () => {
    if (!editing || !window.confirm("ایجاد نسخه جدید یادداشت؟")) return;
    setNoteError(null);
    try {
      const res = await createSessionNoteRevision(editing.id);
      setEditing(res);
      invalidate();
    } catch (e) {
      setNoteError(errDetail(e));
    }
  };

  return (
    <Paper sx={{ p: 2 }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
        <Typography variant="subtitle1" fontWeight={700}>جلسات انجام‌شده</Typography>
        {isCounselor && (
          <Button size="small" variant="contained" onClick={() => setCreateOpen(true)}>ثبت جلسه</Button>
        )}
      </Box>
      {error && <Alert severity="error">{errDetail(error)}</Alert>}
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>شماره</TableCell>
              <TableCell>زمان واقعی</TableCell>
              <TableCell>وضعیت یادداشت</TableCell>
              <TableCell>نسخه یادداشت</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={5} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.length === 0 && (
              <TableRow><TableCell colSpan={5}>جلسه‌ای ثبت نشده است.</TableCell></TableRow>
            )}
            {data?.items.map((row) => {
              const m = SESSION_NOTE_STATUS_META[row.note_status] ?? { label: row.note_status, color: "default" as const };
              return (
                <TableRow key={row.id}>
                  <TableCell>{row.session_number}</TableCell>
                  <TableCell>{new Date(row.occurred_at).toLocaleString("fa-IR")}</TableCell>
                  <TableCell><Chip size="small" color={m.color} label={m.label} /></TableCell>
                  <TableCell>{row.note_version}</TableCell>
                  <TableCell>
                    <Button size="small" onClick={() => setEditing(row)}>یادداشت</Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>ثبت جلسه انجام‌شده</DialogTitle>
        <DialogContent>
          {createError && <Alert severity="error" sx={{ mt: 2 }}>{createError}</Alert>}
          <Stack spacing={2} mt={1}>
            <TextField
              label="زمان واقعی جلسه *"
              type="datetime-local"
              value={createForm.occurred_at ?? ""}
              onChange={(e) => setCreateForm((p) => ({ ...p, occurred_at: e.target.value }))}
              required
              fullWidth
            />
            <TextField
              select
              label="اتصال به نوبت (اختیاری — نوبت «انجام‌شده» می‌شود)"
              value={createForm.appointment_id ?? ""}
              onChange={(e) => setCreateForm((p) => ({ ...p, appointment_id: e.target.value }))}
              fullWidth
            >
              <MenuItem value="">— بدون اتصال —</MenuItem>
              {openAppts?.items.map((a) => (
                <MenuItem key={a.id} value={a.id}>
                  {new Date(a.scheduled_at).toLocaleString("fa-IR")}
                </MenuItem>
              ))}
            </TextField>
            {Object.entries(SESSION_FIELD_LABELS).map(([k, label]) => (
              <TextField
                key={k}
                label={label}
                multiline
                minRows={2}
                value={createForm[k] ?? ""}
                onChange={(e) => setCreateForm((p) => ({ ...p, [k]: e.target.value }))}
                fullWidth
              />
            ))}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>انصراف</Button>
          <Button variant="contained" onClick={doCreate}>ثبت جلسه</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={editing !== null} onClose={() => setEditing(null)} maxWidth="sm" fullWidth>
        <DialogTitle>
          یادداشت جلسه {editing?.session_number} — نسخه {editing?.note_version}
        </DialogTitle>
        <DialogContent>
          {noteError && <Alert severity="error" sx={{ mt: 2 }}>{noteError}</Alert>}
          {editing && !editing.can_edit_note && (
            <Alert severity="info" sx={{ mt: 2 }}>
              این یادداشت نهایی شده و بی‌ردپا تغییر نمی‌کند. برای اصلاح، «نسخه جدید» بسازید.
            </Alert>
          )}
          <Stack spacing={2} mt={2}>
            {Object.entries(SESSION_FIELD_LABELS).map(([k, label]) => (
              <TextField
                key={k}
                label={label}
                multiline
                minRows={2}
                value={noteContent[k] ?? ""}
                onChange={(e) => setNoteContent((p) => ({ ...p, [k]: e.target.value }))}
                disabled={editing ? !editing.can_edit_note : true}
                fullWidth
              />
            ))}
          </Stack>
        </DialogContent>
        <DialogActions>
          {editing?.can_edit_note && (
            <>
              <Button onClick={doSaveNote}>ذخیره پیش‌نویس</Button>
              <Button variant="contained" color="success" onClick={doFinalize}>نهایی‌سازی</Button>
            </>
          )}
          {editing && !editing.can_edit_note && isCounselor && (
            <Button variant="contained" onClick={doNewRevision}>نسخه جدید یادداشت</Button>
          )}
          <Button onClick={() => setEditing(null)}>بستن</Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
