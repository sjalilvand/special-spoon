import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Badge, Box, Chip, IconButton, List, ListItemButton, ListItemText,
  Popover, Tooltip, Typography,
} from "@mui/material";
import NotificationsIcon from "@mui/icons-material/Notifications";
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

/** زنگ اعلان - B12 سند: شمارنده خوانده‌نشده با polling 60 ثانیه */
export default function NotificationBell() {
  const [count, setCount] = useState(0);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const navigate = useNavigate();
  const timer = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetchNotifications(false, 8);
      setItems(res.items);
      setCount(res.unread);
    } catch {
      /* بی‌صدا - اعلان هرگز جریان اصلی را نمی‌شکند */
    }
  }, []);

  useEffect(() => {
    refresh();
    timer.current = window.setInterval(refresh, 60_000);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [refresh]);

  const openItem = async (n: NotificationItem) => {
    setAnchorEl(null);
    if (!n.read_at) {
      try {
        await markNotificationRead(n.id);
        refresh();
      } catch { /* ignore */ }
    }
    if (n.entity_type === "assessment" && n.entity_id) navigate(`/assessments/${n.entity_id}`);
    else if (n.entity_type === "case" && n.entity_id) navigate(`/cases/${n.entity_id}`);
    else navigate("/notifications");
  };

  return (
    <>
      <Tooltip title="اعلان‌ها">
        <IconButton
          color="inherit"
          onClick={(e) => { setAnchorEl(e.currentTarget); refresh(); }}
          aria-label={`اعلان‌ها${count > 0 ? ` - ${count} خوانده‌نشده` : ""}`}
          size="small"
        >
          <Badge badgeContent={count} color="error" max={99}>
            <NotificationsIcon />
          </Badge>
        </IconButton>
      </Tooltip>
      <Popover
        open={Boolean(anchorEl)}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
        transformOrigin={{ vertical: "top", horizontal: "left" }}
        slotProps={{ paper: { sx: { width: 360, maxHeight: 420 } } }}
      >
        <Box sx={{ px: 2, py: 1, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Typography variant="subtitle2">اعلان‌های اخیر</Typography>
          <Box>
            {count > 0 && (
              <Chip
                size="small" label="خواندن همه" clickable
                onClick={async () => { await markAllNotificationsRead(); refresh(); }}
                sx={{ ml: 1 }}
              />
            )}
            <Chip size="small" label="همه اعلان‌ها" clickable onClick={() => { setAnchorEl(null); navigate("/notifications"); }} />
          </Box>
        </Box>
        {items.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ px: 2, py: 3, textAlign: "center" }}>
            اعلانی وجود ندارد
          </Typography>
        ) : (
          <List dense disablePadding>
            {items.map((n) => (
              <ListItemButton key={n.id} onClick={() => openItem(n)} sx={{ alignItems: "flex-start" }}>
                <ListItemText
                  primary={
                    <Box sx={{ display: "flex", gap: 0.5, alignItems: "center" }}>
                      {!n.read_at && <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: "error.main", flexShrink: 0 }} />}
                      <Typography variant="body2" fontWeight={n.read_at ? 400 : 700} noWrap>
                        {n.title}
                      </Typography>
                    </Box>
                  }
                  secondary={CATEGORY_LABEL[n.category] ?? n.category}
                />
                <Chip size="small" color={severityColor[n.severity]} variant="outlined" label="" sx={{ minWidth: 14, height: 14 }} />
              </ListItemButton>
            ))}
          </List>
        )}
      </Popover>
    </>
  );
}
