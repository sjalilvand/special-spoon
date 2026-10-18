import { useCallback, useEffect, useState } from "react";
import {
  Alert, Box, Chip, CircularProgress, Paper, Table, TableBody, TableCell, TableHead, TableRow,
  Tooltip as MuiTooltip, Typography,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import DoneAllIcon from "@mui/icons-material/DoneAll";
import {
  NotificationItem, fetchNotifications, markAllNotificationsRead, markNotificationRead, severityColor,
} from "../api/notifications";

const CATEGORY_LABEL: Record<string, string> = {
  assessment: "فرم",
  case: "پرونده",
  appointment: "نوبت",
  consent: "رضایت",
  system: "سامانه",
};

const SEVERITY_LABEL: Record<string, string> = {
  info: "عادی",
  warning: "هشدار",
  critical: "فوری",
};

/** صفحه اعلان‌ها - B12/B38 سند: صندوق اعلان کاربر با علامت‌گذاری خوانده‌شدن */
export default function NotificationsPage() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchNotifications(unreadOnly, 200);
      setItems(res.items);
      setUnread(res.unread);
    } catch (e) {
      setError("بارگذاری اعلان‌ها ناموفق بود");
    } finally {
      setLoading(false);
    }
  }, [unreadOnly]);

  useEffect(() => { load(); }, [load]);

  const open = async (n: NotificationItem) => {
    if (!n.read_at) {
      try { await markNotificationRead(n.id); load(); } catch { /* ignore */ }
    }
  };

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 2, flexWrap: "wrap" }}>
        <Typography variant="h6" fontWeight={800}>اعلان‌ها</Typography>
        {unread > 0 && <Chip color="error" size="small" label={`${unread} خوانده‌نشده`} />}
        <Chip
          size="small" label={unreadOnly ? "نمایش: خوانده‌نشده" : "نمایش: همه"} clickable
          color={unreadOnly ? "warning" : "default"}
          onClick={() => setUnreadOnly((v) => !v)}
        />
        <Box flexGrow={1} />
        <Chip
          icon={<DoneAllIcon />} size="small" label="خواندن همه" clickable
          disabled={unread === 0}
          onClick={async () => { await markAllNotificationsRead(); load(); }}
        />
        <Chip icon={<RefreshIcon />} size="small" label="به‌روزرسانی" clickable onClick={load} />
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Paper elevation={1}>
        {loading ? (
          <Box sx={{ p: 6, textAlign: "center" }}><CircularProgress /></Box>
        ) : items.length === 0 ? (
          <Box sx={{ p: 6, textAlign: "center" }}>
            <Typography color="text.secondary">اعلانی برای نمایش وجود ندارد</Typography>
          </Box>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>عنوان</TableCell>
                <TableCell>دسته</TableCell>
                <TableCell>فوریت</TableCell>
                <TableCell>زمان</TableCell>
                <TableCell>وضعیت</TableCell>
                <TableCell align="left">عمل</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((n) => (
                <TableRow
                  key={n.id}
                  hover
                  sx={{ bgcolor: n.read_at ? undefined : "action.hover" }}
                  onClick={() => open(n)}
                >
                  <TableCell>
                    <Typography variant="body2" fontWeight={n.read_at ? 400 : 700}>
                      {n.title}
                    </Typography>
                    {n.body && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
                        {n.body}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>{CATEGORY_LABEL[n.category] ?? n.category}</TableCell>
                  <TableCell>
                    <Chip size="small" color={severityColor[n.severity]} label={SEVERITY_LABEL[n.severity] ?? n.severity} variant="outlined" />
                  </TableCell>
                  <TableCell sx={{ whiteSpace: "nowrap" }}>
                    {n.created_at ? new Date(n.created_at).toLocaleString("fa-IR") : "—"}
                  </TableCell>
                  <TableCell>
                    {n.read_at
                      ? <Typography variant="caption" color="text.secondary">خوانده‌شده</Typography>
                      : <Chip size="small" color="error" label="جدید" />}
                  </TableCell>
                  <TableCell align="left">
                    <MuiTooltip title="علامت‌گذاری خوانده‌شده">
                      <Chip
                        size="small" clickable disabled={Boolean(n.read_at)} label="خواندم"
                        onClick={(e) => { e.stopPropagation(); open(n); }}
                      />
                    </MuiTooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>
    </Box>
  );
}
