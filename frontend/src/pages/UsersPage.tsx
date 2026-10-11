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
  FormControlLabel,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { errDetail } from "../api/client";
import {
  ROLE_OPTIONS,
  createActivationToken,
  createUser,
  fetchUsers,
  roleTitle,
  updateUserStatus,
} from "../api/auth";
import type { UserRow } from "../api/auth";

const STATUS_META: Record<string, { label: string; color: "success" | "warning" | "default" }> = {
  active: { label: "فعال", color: "success" },
  pending_activation: { label: "در انتظار فعال‌سازی", color: "warning" },
  disabled: { label: "غیرفعال", color: "default" },
};

export default function UsersPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [tokenInfo, setTokenInfo] = useState<{ username: string; token: string; expires_at: string } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["users", page, search],
    queryFn: () => fetchUsers({ page: page + 1, page_size: 10, search: search || undefined }),
  });

  const toggleStatus = useMutation({
    mutationFn: (row: UserRow) =>
      updateUserStatus(row.id, row.status === "disabled" ? "active" : "disabled"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
    onError: (e) => setError(errDetail(e)),
  });

  const makeToken = useMutation({
    mutationFn: (row: UserRow) => createActivationToken(row.id),
    onSuccess: (res, row) =>
      setTokenInfo({ username: row.username, token: res.token, expires_at: res.expires_at }),
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Stack spacing={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center" gap={2}>
        <Typography variant="h6" fontWeight={700}>
          مدیریت حساب‌ها و نقش‌ها
        </Typography>
        <TextField
          size="small"
          label="جست‌وجو (نام کاربری یا نام نمایشی)"
          value={search}
          onChange={(e) => {
            setPage(0);
            setSearch(e.target.value);
          }}
          sx={{ width: 320 }}
        />
        <Button variant="contained" onClick={() => setCreateOpen(true)}>
          حساب جدید
        </Button>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>نام کاربری</TableCell>
              <TableCell>نام نمایشی</TableCell>
              <TableCell>نقش‌ها</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>آخرین ورود</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <CircularProgress size={24} />
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((row) => {
              const meta = STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
              return (
                <TableRow key={row.id}>
                  <TableCell>{row.username}</TableCell>
                  <TableCell>{row.display_name}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                      {row.roles.length === 0 && <Typography variant="caption">—</Typography>}
                      {row.roles.map((r) => (
                        <Chip key={r} label={roleTitle(r)} size="small" variant="outlined" />
                      ))}
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Chip label={meta.label} color={meta.color} size="small" />
                  </TableCell>
                  <TableCell>
                    {row.last_login_at ? new Date(row.last_login_at).toLocaleString("fa-IR") : "—"}
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={1}>
                      <Button
                        size="small"
                        onClick={() => {
                          if (window.confirm("تغییر وضعیت این حساب؟")) toggleStatus.mutate(row);
                        }}
                      >
                        {row.status === "disabled" ? "فعال‌سازی" : "غیرفعال"}
                      </Button>
                      <Button size="small" onClick={() => makeToken.mutate(row)}>
                        توکن فعال‌سازی
                      </Button>
                    </Stack>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <TablePagination
          component="div"
          count={data?.total ?? 0}
          page={page}
          onPageChange={(_, p) => setPage(p)}
          rowsPerPage={10}
          rowsPerPageOptions={[10]}
          labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`}
        />
      </TableContainer>

      <CreateUserDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onError={setError}
      />

      <Dialog open={tokenInfo !== null} onClose={() => setTokenInfo(null)} maxWidth="sm" fullWidth>
        <DialogTitle>توکن فعال‌سازی — {tokenInfo?.username}</DialogTitle>
        <DialogContent>
          <Alert severity="info" sx={{ mb: 2 }}>
            این توکن فقط یک بار نمایش داده می‌شود. آن را به روش مورد تأیید سازمان برای کاربر ارسال کنید.
            انقضا: {tokenInfo ? new Date(tokenInfo.expires_at).toLocaleString("fa-IR") : ""}
          </Alert>
          <TextField
            fullWidth
            multiline
            value={tokenInfo?.token ?? ""}
            InputProps={{ readOnly: true }}
          />
          <Button
            sx={{ mt: 1 }}
            onClick={() => tokenInfo && navigator.clipboard.writeText(tokenInfo.token)}
          >
            کپی توکن
          </Button>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTokenInfo(null)}>بستن</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

function CreateUserDialog({
  open,
  onClose,
  onError,
}: {
  open: boolean;
  onClose: () => void;
  onError: (msg: string) => void;
}) {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [roles, setRoles] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await createUser({
        username: username.trim(),
        display_name: displayName.trim(),
        email: email.trim() || undefined,
        mobile: mobile.trim() || undefined,
        roles,
      });
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      setUsername("");
      setDisplayName("");
      setEmail("");
      setMobile("");
      setRoles([]);
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
        <DialogTitle>ایجاد حساب جدید</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            حساب جدید «در انتظار فعال‌سازی» ایجاد می‌شود؛ رمز عبور در این مرحله تعیین نمی‌شود.
          </Typography>
          {formError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {formError}
            </Alert>
          )}
          <Stack spacing={2} mt={1}>
            <TextField label="نام کاربری" value={username} onChange={(e) => setUsername(e.target.value)} required />
            <TextField label="نام نمایشی" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
            <TextField label="ایمیل (اختیاری)" value={email} onChange={(e) => setEmail(e.target.value)} />
            <TextField label="موبایل (اختیاری)" value={mobile} onChange={(e) => setMobile(e.target.value)} />
            <Box>
              <Typography variant="body2" sx={{ mb: 1 }}>
                نقش‌ها:
              </Typography>
              {ROLE_OPTIONS.map((r) => (
                <FormControlLabel
                  key={r.code}
                  control={
                    <Checkbox
                      checked={roles.includes(r.code)}
                      onChange={(e) =>
                        setRoles((prev) =>
                          e.target.checked ? [...prev, r.code] : prev.filter((c) => c !== r.code)
                        )
                      }
                    />
                  }
                  label={r.title}
                />
              ))}
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>
            {busy ? "در حال ثبت…" : "ایجاد"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
