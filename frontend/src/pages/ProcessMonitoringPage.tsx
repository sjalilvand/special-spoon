// فاز ۴۹ - B42: مانیتورینگ وضعیت درخواست در فرایند — خط‌زمانی گام‌ها، گام
// فعال فعلی، شروع فرایند برای یک موضوع (درخواست مشاوره/پرونده/متقاضی/دستی)،
// ثبت گام و انتقال وضعیت (تکمیل/لغو/تعلیق/ادامه).
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, MenuItem, Paper, Stack, Step, StepConnector, StepLabel, Stepper,
  Table, TableBody, TableCell, TableContainer, TableHead, TablePagination, TableRow,
  TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { errDetail } from "../api/client";
import BpmnDiagram from "../components/BpmnDiagram";
import {
  ProcessDefinitionInfo, ProcessInstanceInfo, fetchProcessDiagram, fetchProcessInstances, fetchProcesses,
  recordProcessEvent, startProcessInstance, transitionProcessInstance,
} from "../api/processes";
import { fetchConsultationRequests } from "../api/siteops";
import type { ConsultationRow } from "../api/siteops";
import { formatJalaliDateTime } from "../utils/jalali";

const SUBJECT_TYPES: Record<string, string> = {
  consultation_request: "درخواست مشاوره",
  case: "پرونده",
  applicant: "متقاضی",
  manual: "موضوع دستی",
};

const INSTANCE_STATUS: Record<string, { label: string; color: "success" | "warning" | "info" | "default" }> = {
  running: { label: "در جریان", color: "info" },
  suspended: { label: "معلق", color: "warning" },
  completed: { label: "تکمیل‌شده", color: "success" },
  cancelled: { label: "لغوشده", color: "default" },
};

const EVENT_STATUS: Record<string, { label: string; color: string }> = {
  done: { label: "انجام‌شده", color: "#2e7d32" },
  active: { label: "گام فعال", color: "#ed8c37" },
  pending: { label: "در انتظار", color: "#8a8a8a" },
  skipped: { label: "ردشده", color: "#8a8a8a" },
  failed: { label: "ناموفق", color: "#c62828" },
};

export default function ProcessMonitoringPage() {
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  // فیلتر موضوع (از دکمه «فرایند» در درخواست‌های مشاوره یا انتخاب دستی)
  const [subjectType, setSubjectType] = useState<string>(searchParams.get("subject_type") ?? "");
  const [subjectId, setSubjectId] = useState<string>(searchParams.get("subject_id") ?? "");
  const subjectLabel = searchParams.get("label") ?? "";
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(0);

  const [selectedInstanceId, setSelectedInstanceId] = useState<string | null>(null);
  const [startOpen, setStartOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  const instances = useQuery({
    queryKey: ["process-instances", subjectType, subjectId, statusFilter, page],
    queryFn: () => fetchProcessInstances({
      subject_type: subjectType || undefined,
      subject_id: subjectId || undefined,
      status: statusFilter || undefined,
      page: page + 1,
      page_size: 10,
    }),
  });

  const definitions = useQuery({
    queryKey: ["processes-for-monitor"],
    queryFn: fetchProcesses,
  });

  useEffect(() => {
    if (searchParams.get("subject_type") !== null) {
      setSubjectType(searchParams.get("subject_type")!);
      setSubjectId(searchParams.get("subject_id") ?? "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const clearSubject = () => {
    setSubjectType("");
    setSubjectId("");
    setSearchParams({});
  };

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["process-instances"] });
    // فاز ۵۹: به‌روزرسانی نمودار زنده و جزئیات پس از ثبت گام/انتقال
    qc.invalidateQueries({ queryKey: ["process-instance"] });
    qc.invalidateQueries({ queryKey: ["process-instance-diagram"] });
  };

  const selectedInstance = useMemo(
    () => instances.data?.items.find((i) => i.id === selectedInstanceId) ?? null,
    [instances.data, selectedInstanceId],
  );

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="h5" fontWeight={800}>مانیتورینگ فرایندها (B42)</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          وضعیت هر درخواست/موضوع در فرایندهای سازمانی: کدام گام‌ها انجام شده، گام فعال چیست و
          چه کسی چه زمانی هر گام را ثبت کرده است.
        </Typography>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {okMsg && <Alert severity="success" onClose={() => setOkMsg(null)}>{okMsg}</Alert>}

      {/* فیلتر موضوع */}
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
          <TextField
            select size="small" label="نوع موضوع" sx={{ minWidth: 180 }}
            value={subjectType} onChange={(e) => { setSubjectType(e.target.value); setSubjectId(""); setPage(0); }}
          >
            <MenuItem value="">— همه موضوع‌ها —</MenuItem>
            {Object.entries(SUBJECT_TYPES).map(([k, v]) => (
              <MenuItem key={k} value={k}>{v}</MenuItem>
            ))}
          </TextField>
          {subjectType && (
            <TextField
              size="small" label="شناسه موضوع (اختیاری)" sx={{ minWidth: 260 }}
              value={subjectId} onChange={(e) => { setSubjectId(e.target.value.trim()); setPage(0); }}
              placeholder="UUID یا کد — خالی = همه"
              slotProps={{ htmlInput: { dir: "ltr" } }}
            />
          )}
          <TextField
            select size="small" label="وضعیت" sx={{ minWidth: 150 }}
            value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
          >
            <MenuItem value="">— همه —</MenuItem>
            {Object.entries(INSTANCE_STATUS).map(([k, v]) => (
              <MenuItem key={k} value={k}>{v.label}</MenuItem>
            ))}
          </TextField>
          {(subjectType || subjectId) && (
            <Button size="small" onClick={clearSubject}>حذف فیلتر موضوع</Button>
          )}
          <Box flexGrow={1} />
          <Button variant="contained" onClick={() => setStartOpen(true)}>+ شروع فرایند برای موضوع</Button>
        </Stack>
        {subjectType && subjectLabel && (
          <Alert severity="info" sx={{ mt: 1.5 }} onClose={clearSubject}>
            پیگیری «{subjectLabel}» در فرایندها — {SUBJECT_TYPES[subjectType] ?? subjectType}
          </Alert>
        )}
      </Paper>

      {/* فهرست نمونه‌ها */}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>فرایند</TableCell>
              <TableCell>نسخه</TableCell>
              <TableCell>موضوع</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>گام فعلی</TableCell>
              <TableCell>شروع</TableCell>
              <TableCell>پایان</TableCell>
              <TableCell align="left">عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {instances.isLoading && (
              <TableRow><TableCell colSpan={8} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {!instances.isLoading && (instances.data?.items.length ?? 0) === 0 && (
              <TableRow><TableCell colSpan={8} align="center">نمونه‌ای یافت نشد</TableCell></TableRow>
            )}
            {(instances.data?.items ?? []).map((i) => {
              const st = INSTANCE_STATUS[i.status] ?? { label: i.status_label, color: "default" as const };
              return (
                <TableRow key={i.id} hover selected={i.id === selectedInstanceId}>
                  <TableCell>
                    <Typography variant="body2" fontWeight={700}>{i.definition_title}</Typography>
                    <Typography variant="caption" color="text.secondary" dir="ltr">{i.definition_code}</Typography>
                  </TableCell>
                  <TableCell>{i.version_number?.toLocaleString("fa-IR") ?? "—"}</TableCell>
                  <TableCell>
                    <Typography variant="body2">{i.subject_label ?? i.subject_id.slice(0, 8)}</Typography>
                    <Typography variant="caption" color="text.secondary">{SUBJECT_TYPES[i.subject_type] ?? i.subject_type}</Typography>
                  </TableCell>
                  <TableCell><Chip size="small" color={st.color} label={st.label} /></TableCell>
                  <TableCell>{i.current_element_name ?? "—"}</TableCell>
                  <TableCell>{formatJalaliDateTime(i.started_at)}</TableCell>
                  <TableCell>{i.finished_at ? formatJalaliDateTime(i.finished_at) : "—"}</TableCell>
                  <TableCell align="left">
                    <Button size="small" onClick={() => setSelectedInstanceId(i.id === selectedInstanceId ? null : i.id)}>
                      {i.id === selectedInstanceId ? "بستن" : "پیگیری"}
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <TablePagination
          component="div" count={instances.data?.total ?? 0} page={page}
          onPageChange={(_, p) => setPage(p)} rowsPerPage={10} rowsPerPageOptions={[10]}
          labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`}
        />
      </TableContainer>

      {/* جزئیات + خط‌زمانی */}
      {selectedInstance && (
        <InstanceDetail
          instance={selectedInstance}
          onChanged={() => { refresh(); setOkMsg("ثبت شد"); }}
          onError={setError}
        />
      )}

      <StartInstanceDialog
        open={startOpen}
        definitions={definitions.data ?? []}
        presetType={subjectType}
        presetId={subjectId}
        onClose={() => setStartOpen(false)}
        onSaved={(inst) => {
          setStartOpen(false);
          setOkMsg("فرایند برای موضوع شروع شد");
          setSelectedInstanceId(inst.id);
          refresh();
        }}
        onError={setError}
      />
    </Stack>
  );
}

/* ------------------------------ جزئیات نمونه ------------------------------ */

function InstanceDetail({ instance, onChanged, onError }: {
  instance: ProcessInstanceInfo;
  onChanged: () => void;
  onError: (m: string) => void;
}) {
  const [eventOpen, setEventOpen] = useState(false);
  const [showTimeline, setShowTimeline] = useState(false);
  const detail = useQuery({
    queryKey: ["process-instance", instance.id],
    queryFn: () => import("../api/processes").then((m) => m.fetchProcessInstance(instance.id)),
  });
  // فاز ۵۹: دیاگرام BPMN زنده — وضعیت روی خود نمودار فرایند
  const diagram = useQuery({
    queryKey: ["process-instance-diagram", instance.id],
    queryFn: () => fetchProcessDiagram(instance.id),
  });

  const inst = detail.data ?? instance;
  const events = inst.events ?? [];
  const st = INSTANCE_STATUS[inst.status] ?? { label: inst.status_label, color: "default" as const };

  const transition = useMutation({
    mutationFn: (action: string) =>
      import("../api/processes").then(() =>
        transitionProcessInstance(inst.id, { action: action as "complete" | "cancel" | "suspend" | "resume" })),
    onSuccess: () => { onChanged(); },
    onError: (e) => onError(errDetail(e)),
  });

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap mb={1.5}>
        <Typography variant="subtitle1" fontWeight={800}>
          {inst.definition_title} — نسخه {inst.version_number?.toLocaleString("fa-IR")}
        </Typography>
        <Chip size="small" color={st.color} label={st.label} />
        <Box flexGrow={1} />
        {inst.status === "running" && (
          <>
            <Button size="small" variant="outlined" onClick={() => setEventOpen(true)}>+ ثبت گام</Button>
            <Button size="small" color="warning" disabled={transition.isPending} onClick={() => transition.mutate("suspend")}>تعلیق</Button>
            <Button size="small" color="success" disabled={transition.isPending} onClick={() => transition.mutate("complete")}>تکمیل</Button>
            <Button size="small" color="error" disabled={transition.isPending} onClick={() => transition.mutate("cancel")}>لغو</Button>
          </>
        )}
        {inst.status === "suspended" && (
          <Button size="small" color="info" disabled={transition.isPending} onClick={() => transition.mutate("resume")}>ادامه</Button>
        )}
      </Stack>

      <Typography variant="body2" color="text.secondary" mb={2}>
        موضوع: {SUBJECT_TYPES[inst.subject_type] ?? inst.subject_type} — {inst.subject_label ?? inst.subject_id}
        {inst.note ? ` · یادداشت: ${inst.note}` : ""}
      </Typography>

      {/* فاز ۵۹: شبیه‌سازی بصری فرایند — وضعیت هر عنصر روی نمودار BPMN */}
      {diagram.isLoading && (
        <Box textAlign="center" py={3}><CircularProgress size={28} /></Box>
      )}
      {diagram.isError && (
        <Alert severity="warning" sx={{ mb: 1 }}>
          نمایش نمودار فرایند ممکن نشد — {errDetail(diagram.error)}
        </Alert>
      )}
      {diagram.data && diagram.data.nodes.length > 0 && (
        <Box mb={2}>
          <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
            <Typography variant="subtitle2" fontWeight={800}>نقشهٔ فرایند و وضعیت زنده</Typography>
            {inst.current_element_name && (
              <Chip size="small" color="warning" label={`گام فعلی: ${inst.current_element_name}`} />
            )}
            <Box flexGrow={1} />
            {events.length > 0 && (
              <Button size="small" onClick={() => setShowTimeline(!showTimeline)}>
                {showTimeline ? "پنهان‌کردن خط‌زمانی" : "نمایش خط‌زمانی گام‌ها"}
              </Button>
            )}
          </Stack>
          <BpmnDiagram
            nodes={diagram.data.nodes}
            edges={diagram.data.edges}
            states={diagram.data.states}
          />
        </Box>
      )}

      {showTimeline && events.length > 0 && (
        <Stepper
          nonLinear alternativeLabel
          activeStep={events.findIndex((e) => e.status === "active") === -1
            ? events.length
            : events.findIndex((e) => e.status === "active")}
          connector={<StepConnector sx={{ "& .MuiStepConnector-line": { borderColor: "#e5c9cf" } }} />}
        >
          {events.map((e) => {
            const es = EVENT_STATUS[e.status] ?? { label: e.status, color: "#8a8a8a" };
            return (
              <Step key={e.id} completed={e.status === "done"}>
                <StepLabel
                  optional={
                    <Typography variant="caption" sx={{ color: es.color }}>
                      {es.label}
                      {e.occurred_at ? ` — ${formatJalaliDateTime(e.occurred_at)}` : ""}
                    </Typography>
                  }
                  sx={{
                    "& .MuiStepIcon-root": {
                      color: e.status === "done" ? "#2e7d32" : e.status === "active" ? "#ed8c37" : "#bdbdbd",
                      "&.Mui-active": { color: "#ed8c37" },
                    },
                  }}
                >
                  <Typography variant="body2" fontWeight={700}>{e.element_name}</Typography>
                  {e.note && <Typography variant="caption" color="text.secondary">{e.note}</Typography>}
                </StepLabel>
              </Step>
            );
          })}
        </Stepper>
      )}

      <RecordEventDialog
        open={eventOpen}
        instanceId={inst.id}
        onClose={() => setEventOpen(false)}
        onSaved={() => { setEventOpen(false); onChanged(); }}
        onError={onError}
      />
    </Paper>
  );
}

/* ------------------------------ ثبت گام ------------------------------ */

function RecordEventDialog({ open, instanceId, onClose, onSaved, onError }: {
  open: boolean;
  instanceId: string;
  onClose: () => void;
  onSaved: () => void;
  onError: (m: string) => void;
}) {
  const [name, setName] = useState("");
  const [type, setType] = useState("task");
  const [status, setStatus] = useState("done");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      await recordProcessEvent(instanceId, {
        element_name: name.trim(),
        element_type: type,
        status,
        note: note || undefined,
      });
      setName(""); setNote("");
      onSaved();
    } catch (e) {
      onError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>ثبت گام فرایند</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField required label="نام گام *" value={name} onChange={(e) => setName(e.target.value)}
            helperText="مثال: ثبت اطلاعات فردی مراجع، بررسی نتیجه ارجاع" />
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField select fullWidth label="نوع عنصر" value={type} onChange={(e) => setType(e.target.value)}>
              <MenuItem value="task">فعالیت / وظیفه</MenuItem>
              <MenuItem value="gateway">گیت‌وی تصمیم</MenuItem>
              <MenuItem value="start">رویداد شروع</MenuItem>
              <MenuItem value="end">رویداد پایان</MenuItem>
              <MenuItem value="intermediate">رخداد میانی</MenuItem>
            </TextField>
            <TextField select fullWidth label="وضعیت گام" value={status} onChange={(e) => setStatus(e.target.value)}>
              <MenuItem value="done">انجام‌شده</MenuItem>
              <MenuItem value="active">گام فعال (فعلی)</MenuItem>
              <MenuItem value="pending">در انتظار</MenuItem>
              <MenuItem value="skipped">ردشده</MenuItem>
              <MenuItem value="failed">ناموفق</MenuItem>
            </TextField>
          </Stack>
          <TextField label="یادداشت" multiline minRows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" disabled={busy || !name.trim()} onClick={submit}>
          {busy ? "در حال ثبت…" : "ثبت گام"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/* ------------------------------ شروع فرایند ------------------------------ */

function StartInstanceDialog({ open, definitions, presetType, presetId, onClose, onSaved, onError }: {
  open: boolean;
  definitions: ProcessDefinitionInfo[];
  presetType: string;
  presetId: string;
  onClose: () => void;
  onSaved: (i: ProcessInstanceInfo) => void;
  onError: (m: string) => void;
}) {
  const published = definitions.filter((d) => d.current_version);
  const [definitionId, setDefinitionId] = useState("");
  const [subjectType, setSubjectType] = useState(presetType || "consultation_request");
  const [subjectId, setSubjectId] = useState(presetId);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // انتخاب از درخواست‌های اخیر (برای راحتی)
  const requests = useQuery({
    queryKey: ["recent-requests-for-monitor"],
    queryFn: () => fetchConsultationRequests({ page: 1 }),
    enabled: open && subjectType === "consultation_request",
  });
  const [reqFilter, setReqFilter] = useState("");
  const reqItems: ConsultationRow[] = (requests.data?.items ?? []).filter(
    (r) => !reqFilter.trim() || (r.full_name ?? "").includes(reqFilter.trim()),
  );

  useEffect(() => {
    if (open) {
      setSubjectType(presetType || "consultation_request");
      setSubjectId(presetId);
      setFormError(null);
    }
  }, [open, presetType, presetId]);

  const submit = async () => {
    setFormError(null);
    setBusy(true);
    try {
      const inst = await startProcessInstance({
        definition_id: definitionId,
        subject_type: subjectType,
        subject_id: subjectId,
        subject_label: label || undefined,
      });
      onSaved(inst);
    } catch (e) {
      setFormError(errDetail(e));
      onError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>شروع فرایند برای یک موضوع</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {formError && <Alert severity="error">{formError}</Alert>}
          <TextField
            select required label="فرایند (نسخه منتشرشده) *" value={definitionId}
            onChange={(e) => setDefinitionId(e.target.value)}
          >
            <MenuItem value="">— انتخاب کنید —</MenuItem>
            {published.map((d) => (
              <MenuItem key={d.id} value={d.id}>
                {d.code} — {d.title} (نسخه {d.current_version!.version_number.toLocaleString("fa-IR")})
              </MenuItem>
            ))}
          </TextField>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              select fullWidth required label="نوع موضوع *" value={subjectType}
              onChange={(e) => { setSubjectType(e.target.value); setSubjectId(""); }}
            >
              {Object.entries(SUBJECT_TYPES).map(([k, v]) => (
                <MenuItem key={k} value={k}>{v}</MenuItem>
              ))}
            </TextField>
            <TextField
              fullWidth required label="شناسه موضوع *" value={subjectId}
              onChange={(e) => setSubjectId(e.target.value.trim())}
              helperText="شناسه درخواست/پرونده/متقاضی"
              slotProps={{ htmlInput: { dir: "ltr" } }}
            />
          </Stack>
          {subjectType === "consultation_request" && reqItems.length > 0 && (
            <Box>
              <TextField
                size="small" fullWidth label="جست‌وجوی درخواست (نام)" value={reqFilter}
                onChange={(e) => setReqFilter(e.target.value)} sx={{ mb: 1 }}
              />
              <Stack spacing={0.5} sx={{ maxHeight: 180, overflowY: "auto" }}>
                {reqItems.slice(0, 8).map((r) => (
                  <Button
                    key={r.id} size="small" variant={subjectId === r.id ? "contained" : "outlined"}
                    onClick={() => { setSubjectId(r.id); setLabel(r.full_name); }}
                    sx={{ justifyContent: "flex-start" }}
                  >
                    {r.full_name} — {r.topic} ({r.status === "new" ? "جدید" : r.status === "in_review" ? "در بررسی" : r.status})
                  </Button>
                ))}
              </Stack>
            </Box>
          )}
          <TextField label="برچسب موضوع (نمایشی)" value={label} onChange={(e) => setLabel(e.target.value)} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" disabled={busy || !definitionId || !subjectId.trim()} onClick={submit}>
          {busy ? "در حال شروع…" : "شروع فرایند"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
