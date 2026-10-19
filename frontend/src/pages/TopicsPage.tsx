// فاز ۳۳ - B32 سند جامع: دسته‌بندی موضوعی — slug یکتا، چرخه ممنوع،
// حذف دسته استفاده‌شده ممنوع، «دسته غیرفعال در صفحات عمومی نشان داده نشود»
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControl,
  InputLabel, ListItemText, MenuItem, OutlinedInput, Paper, Select, Snackbar, Stack, Switch,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { errDetail } from "../api/client";
import { fetchAllServices } from "../api/branches";
import {
  Topic, createTopic, deleteTopic, fetchTopics, setTopicServices, updateTopic,
} from "../api/topics";

const fa = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : n.toLocaleString("fa-IR");

export default function TopicsPage() {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [linkTopic, setLinkTopic] = useState<Topic | null>(null);
  const [editTopic, setEditTopic] = useState<Topic | null>(null);

  const topics = useQuery({ queryKey: ["topics"], queryFn: () => fetchTopics(true) });
  const services = useQuery({ queryKey: ["all-services"], queryFn: fetchAllServices });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["topics"] });
    qc.invalidateQueries({ queryKey: ["public-topics"] });
  };

  const createMut = useMutation({
    mutationFn: createTopic,
    onSuccess: (t) => { invalidate(); setCreateOpen(false); setOkMsg(`دسته «${t.name}» ایجاد شد`); },
    onError: (e) => setError(errDetail(e)),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) => updateTopic(id, payload),
    onSuccess: (t) => { invalidate(); setEditTopic(null); setOkMsg(`دسته «${t.name}» به‌روزرسانی شد`); },
    onError: (e) => setError(errDetail(e)),
  });
  const toggleMut = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => updateTopic(id, { is_active }),
    onSuccess: (t) => {
      invalidate();
      setOkMsg(t.is_active ? "دسته فعال شد و در صفحات عمومی دیده می‌شود" : "دسته غیرفعال شد و از صفحات عمومی حذف می‌شود");
    },
    onError: (e) => setError(errDetail(e)),
  });
  const deleteMut = useMutation({
    mutationFn: deleteTopic,
    onSuccess: () => { invalidate(); setOkMsg("دسته حذف شد"); },
    onError: (e) => setError(errDetail(e)),
  });
  const linkMut = useMutation({
    mutationFn: ({ id, serviceIds }: { id: string; serviceIds: string[] }) => setTopicServices(id, serviceIds),
    onSuccess: (t) => { invalidate(); setLinkTopic(null); setOkMsg(`خدمات دسته «${t.name}» تنظیم شد (${t.service_count} خدمت)`); },
    onError: (e) => setError(errDetail(e)),
  });

  const items = [...(topics.data ?? [])].sort((a, b) =>
    a.sort_order - b.sort_order || a.name.localeCompare(b.name, "fa"));

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={800}>دسته‌بندی موضوعی (B32)</Typography>
        <Chip size="small" variant="outlined" label="پیش‌نیاز محتوا/دوره (B33–B36)" />
        <Box flexGrow={1} />
        <Button variant="contained" onClick={() => setCreateOpen(true)}>دسته جدید</Button>
      </Box>
      <Alert severity="info">
        دسته‌بندی سلسله‌مراتبی خدمات؛ پایه فهرست‌های موضوعی محتوا، دوره و آزمون.
        دسته غیرفعال در صفحات عمومی نشان داده نمی‌شود؛ حذف دسته دارای خدمت یا زیر‌دسته ممنوع است.
      </Alert>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>نام</TableCell>
              <TableCell>slug</TableCell>
              <TableCell>والد</TableCell>
              <TableCell>ترتیب</TableCell>
              <TableCell>خدمات</TableCell>
              <TableCell>زیر‌دسته</TableCell>
              <TableCell>فعال</TableCell>
              <TableCell align="left">عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((t) => (
              <TableRow key={t.id} sx={{ opacity: t.is_active ? 1 : 0.55 }}>
                <TableCell>{t.name}</TableCell>
                <TableCell dir="ltr" sx={{ fontFamily: "monospace", fontSize: 12 }}>{t.slug}</TableCell>
                <TableCell>{t.parent_name ?? "—"}</TableCell>
                <TableCell>{fa(t.sort_order)}</TableCell>
                <TableCell>{fa(t.service_count)}</TableCell>
                <TableCell>{fa(t.children_count)}</TableCell>
                <TableCell>
                  <Switch
                    size="small" checked={t.is_active}
                    onChange={(e) => toggleMut.mutate({ id: t.id, is_active: e.target.checked })}
                  />
                </TableCell>
                <TableCell align="left">
                  <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                    <Button size="small" onClick={() => setLinkTopic(t)}>خدمات</Button>
                    <Button size="small" onClick={() => setEditTopic(t)}>ویرایش</Button>
                    <Button
                      size="small" color="error"
                      disabled={t.service_count > 0 || t.children_count > 0}
                      title={t.service_count > 0 || t.children_count > 0 ? "دسته استفاده‌شده حذف نمی‌شود" : ""}
                      onClick={() => { if (confirm(`حذف دسته «${t.name}»؟`)) deleteMut.mutate(t.id); }}
                    >
                      حذف
                    </Button>
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
            {items.length === 0 && (
              <TableRow><TableCell colSpan={8} align="center" sx={{ py: 4, color: "text.secondary" }}>
                دسته‌ای ثبت نشده است.
              </TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <CreateTopicDialog
        open={createOpen}
        topics={items}
        loading={createMut.isPending}
        onClose={() => setCreateOpen(false)}
        onSubmit={(data) => createMut.mutate(data)}
      />
      <EditTopicDialog
        topic={editTopic}
        topics={items}
        loading={updateMut.isPending}
        onClose={() => setEditTopic(null)}
        onSubmit={(id, payload) => updateMut.mutate({ id, payload })}
      />
      <LinkServicesDialog
        topic={linkTopic}
        services={services.data ?? []}
        loading={linkMut.isPending}
        onClose={() => setLinkTopic(null)}
        onSubmit={(id, ids) => linkMut.mutate({ id, serviceIds: ids })}
      />

      <Snackbar open={!!okMsg} autoHideDuration={4000} onClose={() => setOkMsg(null)}
                anchorOrigin={{ vertical: "bottom", horizontal: "center" }}>
        <Alert severity="success" variant="filled">{okMsg}</Alert>
      </Snackbar>
    </Stack>
  );
}

// ---------------------------------------------------------------- dialogs
function CreateTopicDialog({ open, topics, loading, onClose, onSubmit }: {
  open: boolean;
  topics: Topic[];
  loading: boolean;
  onClose: () => void;
  onSubmit: (payload: Record<string, unknown>) => void;
}) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [parentId, setParentId] = useState("");
  const [description, setDescription] = useState("");
  const [sortOrder, setSortOrder] = useState(0);
  const active = topics.filter((t) => t.is_active);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({
      name, slug, sort_order: sortOrder,
      parent_id: parentId || null,
      description: description || null,
    });
    setName(""); setSlug(""); setParentId(""); setDescription(""); setSortOrder(0);
  };
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>دسته موضوعی جدید</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField label="نام دسته" required value={name}
                       onChange={(e) => setName(e.target.value)} />
            <TextField label="slug (لاتین کوچک)" required dir="ltr" value={slug}
                       helperText="مثال: anxiety، mental-health"
                       onChange={(e) => setSlug(e.target.value)} />
            <FormControl size="small">
              <InputLabel>والد (اختیاری)</InputLabel>
              <Select value={parentId} label="والد (اختیاری)"
                      onChange={(e) => setParentId(e.target.value as string)}>
                <MenuItem value=""><em>— بدون والد (ریشه) —</em></MenuItem>
                {active.map((t) => <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>)}
              </Select>
            </FormControl>
            <TextField label="توضیح (اختیاری)" multiline minRows={2} value={description}
                       onChange={(e) => setDescription(e.target.value)} />
            <TextField label="ترتیب نمایش" type="number" value={sortOrder}
                       inputProps={{ min: 0 }}
                       onChange={(e) => setSortOrder(Number(e.target.value || 0))} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={loading}>ایجاد</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function EditTopicDialog({ topic, topics, loading, onClose, onSubmit }: {
  topic: Topic | null;
  topics: Topic[];
  loading: boolean;
  onClose: () => void;
  onSubmit: (id: string, payload: Record<string, unknown>) => void;
}) {
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState("");
  const [description, setDescription] = useState("");
  const [sortOrder, setSortOrder] = useState(0);
  const [key, setKey] = useState("");

  // پر کردن فرم هنگام باز شدن
  if (topic && key !== topic.id) {
    setKey(topic.id);
    setName(topic.name);
    setParentId(topic.parent_id ?? "");
    setDescription(topic.description ?? "");
    setSortOrder(topic.sort_order);
  }
  if (!topic) return null;
  const candidates = topics.filter((t) => t.id !== topic.id && t.is_active);
  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={(e) => { e.preventDefault(); onSubmit(topic.id, {
        name, parent_id: parentId || null, description: description || null, sort_order: sortOrder,
      }); }}>
        <DialogTitle>ویرایش دسته «{topic.name}»</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField label="نام دسته" required value={name} onChange={(e) => setName(e.target.value)} />
            <FormControl size="small">
              <InputLabel>والد</InputLabel>
              <Select value={parentId} label="والد" onChange={(e) => setParentId(e.target.value as string)}>
                <MenuItem value=""><em>— بدون والد (ریشه) —</em></MenuItem>
                {candidates.map((t) => <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>)}
              </Select>
            </FormControl>
            <TextField label="توضیح" multiline minRows={2} value={description}
                       onChange={(e) => setDescription(e.target.value)} />
            <TextField label="ترتیب نمایش" type="number" value={sortOrder} inputProps={{ min: 0 }}
                       onChange={(e) => setSortOrder(Number(e.target.value || 0))} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={loading}>ذخیره</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function LinkServicesDialog({ topic, services, loading, onClose, onSubmit }: {
  topic: Topic | null;
  services: { id: string; title: string; status: string }[];
  loading: boolean;
  onClose: () => void;
  onSubmit: (id: string, ids: string[]) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [key, setKey] = useState("");

  if (topic && key !== topic.id) {
    setKey(topic.id);
    setSelected(topic.service_ids ?? []); // وضعیت فعلی از سرور
  }
  if (!topic) return null;
  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>خدمات دسته «{topic.name}»</DialogTitle>
      <form onSubmit={(e) => { e.preventDefault(); onSubmit(topic.id, selected); }}>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            مجموعه کامل جایگزین می‌شود — خدمات فعلی دسته با انتخاب‌های زیر جایگزین خواهند شد.
          </Alert>
          <FormControl size="small" fullWidth>
            <InputLabel>خدمات</InputLabel>
            <Select multiple value={selected}
                    onChange={(e) => setSelected(e.target.value as string[])}
                    input={<OutlinedInput label="خدمات" />}
                    renderValue={(sel) => (sel as string[])
                      .map((id) => services.find((s) => s.id === id)?.title ?? "؟").join("، ")}>
              {services.map((s) => (
                <MenuItem key={s.id} value={s.id} disabled={s.status !== "active"}>
                  <ListItemText primary={s.title}
                                secondary={s.status !== "active" ? "غیرفعال" : undefined} />
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={loading}>ذخیره</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
