import { useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { errDetail } from "../api/client";
import {
  DATA_SCOPE_OPTIONS,
  createRole,
  deleteRole,
  fetchPermissionCatalog,
  fetchRoles,
  saveRolePermissions,
} from "../api/rbac";

/**
 * فاز ۵۲ - صفحهٔ «نقش‌ها و دسترسی‌ها»:
 * - سمت راست: فهرست نقش‌ها (+ نقش جدید)؛ سمت چپ: ماتریس دسترسی نقش انتخابی؛
 * - ماتریس: هر سطر یک بخش (صفحه‌های پنل) و هر ستون یک دسترسی با تیک گرافیکی؛
 * - «سطح دسترسی روی داده» نقش با همان رابط تیک/لیست انتخاب می‌شود؛
 * - ذخیره با PUT /rbac/roles/{code} — اثر عملیاتی از طریق require_perm سرور.
 */

export default function RolesPermissionsPage() {
  const queryClient = useQueryClient();
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const catalog = useQuery({ queryKey: ["rbac-catalog"], queryFn: fetchPermissionCatalog });
  const roles = useQuery({ queryKey: ["rbac-roles"], queryFn: fetchRoles });

  const selected = useMemo(() => {
    const items = roles.data ?? [];
    if (!items.length) return null;
    return items.find((r) => r.code === selectedCode) ?? items[0];
  }, [roles.data, selectedCode]);

  const save = useMutation({
    mutationFn: (p: { code: string; title: string; data_scope: string; permissions: string[] }) =>
      saveRolePermissions(p.code, {
        title: p.title,
        data_scope: p.data_scope,
        permissions: p.permissions,
      }),
    onSuccess: (_r, p) => {
      setSuccess(`ماتریس دسترسی «${p.title}» ذخیره شد`);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["rbac-roles"] });
    },
    onError: (e) => {
      setError(errDetail(e));
      setSuccess(null);
    },
  });

  const removeRole = useMutation({
    mutationFn: deleteRole,
    onSuccess: () => {
      setSuccess("نقش حذف شد");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["rbac-roles"] });
    },
    onError: (e) => {
      setError(errDetail(e));
      setSuccess(null);
    },
  });

  if (catalog.isLoading || roles.isLoading) {
    return <CircularProgress sx={{ mx: "auto", display: "block", mt: 8 }} />;
  }

  return (
    <Stack spacing={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center" gap={2}>
        <Typography variant="h6" fontWeight={700}>
          نقش‌ها و دسترسی‌ها
        </Typography>
        <Button variant="contained" onClick={() => setCreateOpen(true)}>
          نقش جدید
        </Button>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert severity="success" onClose={() => setSuccess(null)}>{success}</Alert>}

      <Stack direction="row" spacing={2} alignItems="flex-start">
        {/* ستون نقش‌ها */}
        <Paper sx={{ width: 320, flexShrink: 0 }} variant="outlined">
          <Box sx={{ p: 1.5, borderBottom: 1, borderColor: "divider" }}>
            <Typography variant="subtitle2" color="text.secondary">
              نقش‌ها
            </Typography>
          </Box>
          <Box>
            {(roles.data ?? []).map((r) => (
              <Box
                key={r.code}
                onClick={() => setSelectedCode(r.code)}
                sx={{
                  px: 1.5,
                  py: 1.2,
                  cursor: "pointer",
                  bgcolor: selected?.code === r.code ? "action.selected" : "transparent",
                  "&:hover": { bgcolor: "action.hover" },
                }}
              >
                <Typography variant="body2" fontWeight={600}>
                  {r.title}
                </Typography>
                <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }} flexWrap="wrap" useFlexGap>
                  <Chip size="small" variant="outlined" label={r.code} sx={{ fontSize: 11 }} />
                  <Chip
                    size="small"
                    label={r.is_system ? "سیستمی" : "سفارشی"}
                    color={r.is_system ? "primary" : "default"}
                    sx={{ fontSize: 11 }}
                  />
                  <Chip size="small" variant="outlined" label={`${r.member_count ?? 0} کاربر`} sx={{ fontSize: 11 }} />
                </Stack>
              </Box>
            ))}
          </Box>
        </Paper>

        {/* ماتریس دسترسی */}
        {selected && (
          <PermissionMatrix
            key={selected.code}
            role={selected}
            sections={catalog.data ?? []}
            saving={save.isPending}
            onSave={(dataScope, permissions) =>
              save.mutate({
                code: selected.code,
                title: selected.title,
                data_scope: dataScope,
                permissions,
              })
            }
            onDelete={
              selected.is_system
                ? undefined
                : () => {
                    if (window.confirm(`حذف نقش «${selected.title}»؟`)) removeRole.mutate(selected.code);
                  }
            }
          />
        )}
      </Stack>

      <CreateRoleDialog
        open={createOpen}
        existingCodes={(roles.data ?? []).map((r) => r.code)}
        onClose={() => setCreateOpen(false)}
        onError={setError}
        onCreated={(code) => {
          setCreateOpen(false);
          setSelectedCode(code);
          queryClient.invalidateQueries({ queryKey: ["rbac-roles"] });
        }}
      />
    </Stack>
  );
}

function PermissionMatrix({
  role,
  sections,
  saving,
  onSave,
  onDelete,
}: {
  role: { code: string; title: string; data_scope: string; permissions: string[]; is_system: boolean };
  sections: { section: string; permissions: { code: string; title: string }[] }[];
  saving: boolean;
  onSave: (dataScope: string, permissions: string[]) => void;
  onDelete?: () => void;
}) {
  const [checked, setChecked] = useState<Set<string>>(new Set(role.permissions));
  const [scope, setScope] = useState<string>(role.data_scope);
  const scopeMeta = DATA_SCOPE_OPTIONS.find((o) => o.value === scope);

  const toggle = (code: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const toggleSection = (codes: string[], on: boolean) => {
    setChecked((prev) => {
      const next = new Set(prev);
      codes.forEach((c) => (on ? next.add(c) : next.delete(c)));
      return next;
    });
  };

  return (
    <Paper variant="outlined" sx={{ flex: 1, minWidth: 0 }}>
      <Box sx={{ p: 1.5, borderBottom: 1, borderColor: "divider", display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap" }}>
        <Typography variant="subtitle1" fontWeight={700}>
          {role.title}
        </Typography>
        <Chip label={role.code} size="small" variant="outlined" />
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>سطح دسترسی روی داده</InputLabel>
          <Select value={scope} label="سطح دسترسی روی داده" onChange={(e) => setScope(e.target.value)}>
            {DATA_SCOPE_OPTIONS.map((o) => (
              <MenuItem key={o.value} value={o.value}>
                {o.title}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Box sx={{ flex: 1 }} />
        {onDelete && <Button color="error" onClick={onDelete}>حذف نقش</Button>}
        <Button variant="contained" disabled={saving} onClick={() => onSave(scope, Array.from(checked))}>
          {saving ? "در حال ذخیره…" : "ذخیرهٔ ماتریس"}
        </Button>
      </Box>

      {scopeMeta && (
        <Alert severity="info" sx={{ mx: 1.5, mt: 1.5 }}>
          سطح داده: {scopeMeta.title} — {scopeMeta.hint}
        </Alert>
      )}

      <TableContainer sx={{ maxHeight: "60vh" }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell sx={{ width: 220 }}>بخش</TableCell>
              {sections[0]?.permissions.map((_, i) => (
                <TableCell key={i} align="center">
                  <Typography variant="caption" sx={{ fontSize: 11 }}>
                    {i === 0 ? "مجوزها" : ""}
                  </Typography>
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {sections.map((sec) => {
              const allOn = sec.permissions.every((p) => checked.has(p.code));
              const someOn = sec.permissions.some((p) => checked.has(p.code));
              return (
                <TableRow key={sec.section} hover>
                  <TableCell>
                    <Stack direction="row" alignItems="center" spacing={1}>
                      <Checkbox
                        size="small"
                        checked={allOn}
                        indeterminate={!allOn && someOn}
                        onChange={(e) => toggleSection(sec.permissions.map((p) => p.code), e.target.checked)}
                        title="انتخاب/لغو کل بخش"
                      />
                      <Typography variant="body2" fontWeight={600}>
                        {sec.section}
                      </Typography>
                    </Stack>
                  </TableCell>
                  {sec.permissions.map((p) => (
                    <TableCell key={p.code} align="center">
                      <Tooltip title={p.title} arrow>
                        <Checkbox size="small" checked={checked.has(p.code)} onChange={() => toggle(p.code)} />
                      </Tooltip>
                    </TableCell>
                  ))}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      <Box sx={{ p: 1.5 }}>
        <Typography variant="caption" color="text.secondary">
          هر ستون یک دسترسی است (عنوان با نگه‌داشتن نشانگر نمایش داده می‌شود)؛ تیک سرِ بخش = انتخاب همهٔ دسترسی‌های آن بخش.
          {role.is_system ? " — نقش سیستمی قابل حذف نیست ولی ماتریسش قابل ویرایش است." : ""}
        </Typography>
      </Box>
    </Paper>
  );
}

function CreateRoleDialog({
  open,
  existingCodes,
  onClose,
  onError,
  onCreated,
}: {
  open: boolean;
  existingCodes: string[];
  onClose: () => void;
  onError: (msg: string) => void;
  onCreated: (code: string) => void;
}) {
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [scope, setScope] = useState("assigned");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async () => {
    setFormError(null);
    setBusy(true);
    try {
      await createRole(code.trim().toUpperCase(), {
        title: title.trim(),
        data_scope: scope,
        permissions: [],
      });
      onCreated(code.trim().toUpperCase());
      setCode("");
      setTitle("");
      setScope("assigned");
    } catch (e) {
      setFormError(errDetail(e));
      onError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const duplicate = existingCodes.includes(code.trim().toUpperCase());
  const codeValid = /^[A-Z][A-Z0-9_]{2,49}$/.test(code.trim().toUpperCase());

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>ساخت نقش جدید</DialogTitle>
      <DialogContent>
        {formError && <Alert severity="error" sx={{ mb: 2, mt: 1 }}>{formError}</Alert>}
        <Stack spacing={2} mt={1}>
          <TextField
            label="کد نقش (لاتین، مثل HR_MANAGER)"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            error={code.length > 0 && (!codeValid || duplicate)}
            helperText={
              code.length > 0 && duplicate
                ? "این کد قبلاً ثبت شده است"
                : "۳ تا ۵۰ نویسه؛ حروف بزرگ/عدد/زیرخط"
            }
          />
          <TextField label="عنوان نقش (فارسی)" value={title} onChange={(e) => setTitle(e.target.value)} />
          <FormControl size="small">
            <InputLabel>سطح دسترسی روی داده</InputLabel>
            <Select value={scope} label="سطح دسترسی روی داده" onChange={(e) => setScope(e.target.value)}>
              {DATA_SCOPE_OPTIONS.map((o) => (
                <MenuItem key={o.value} value={o.value}>
                  {o.title}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Alert severity="info">
            پس از ساخت، ماتریس دسترسی نقش را در همین صفحه تیک بزنید و ذخیره کنید؛ سپس نقش را از صفحهٔ «مدیریت حساب‌ها» به کاربران اختصاص دهید.
          </Alert>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" onClick={submit} disabled={busy || !codeValid || duplicate || !title.trim()}>
          {busy ? "در حال ساخت…" : "ساخت نقش"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
