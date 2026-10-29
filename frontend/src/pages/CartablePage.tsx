// فاز ۵۹ - کارتابل شخصی هر حساب: نقش‌ها، سطح دسترسی روی داده، دسترسی‌های
// مؤثر گروه‌بندی‌شده، کارهای در جریان و فعالیت‌های اخیر.
// مدیر سامانه از صفحهٔ کاربران با مسیر /cartable/:userId کارتابل هر شخص را
// از نقطهٔ نظر خودِ آن شخص می‌بیند (فقط مشاهده).
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Chip, CircularProgress,
  Divider, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Typography,
} from "@mui/material";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import BadgeRoundedIcon from "@mui/icons-material/BadgeRounded";
import ShieldRoundedIcon from "@mui/icons-material/ShieldRounded";
import AssignmentRoundedIcon from "@mui/icons-material/AssignmentRounded";
import HistoryRoundedIcon from "@mui/icons-material/HistoryRounded";
import { useParams } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { errDetail } from "../api/client";
import { fetchMyCartable, fetchUserCartable, type CartableData } from "../api/cartable";
import { formatJalaliDateTime } from "../utils/jalali";

const STATUS_META: Record<string, { label: string; color: "success" | "warning" | "default" }> = {
  active: { label: "فعال", color: "success" },
  pending_activation: { label: "در انتظار فعال‌سازی", color: "warning" },
  disabled: { label: "غیرفعال", color: "default" },
};

const SUBJECT_TYPES: Record<string, string> = {
  consultation_request: "درخواست مشاوره",
  case: "پرونده",
  applicant: "متقاضی",
  manual: "موضوع دستی",
};

const WORK_STATUS: Record<string, { label: string; color: "info" | "warning" | "success" | "default" }> = {
  running: { label: "در جریان", color: "info" },
  suspended: { label: "معلق", color: "warning" },
  completed: { label: "تکمیل‌شده", color: "success" },
  cancelled: { label: "لغوشده", color: "default" },
};

export default function CartablePage() {
  const { userId } = useParams();
  const isManagedView = !!userId;

  const cartable = useQuery({
    queryKey: ["cartable", userId ?? "me"],
    queryFn: () => (isManagedView ? fetchUserCartable(userId!) : fetchMyCartable()),
  });

  if (cartable.isLoading) {
    return <Paper sx={{ p: 4, textAlign: "center" }}><CircularProgress /></Paper>;
  }
  if (cartable.isError) {
    return <Alert severity="error">{errDetail(cartable.error)}</Alert>;
  }
  const data = cartable.data!;

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="h5" fontWeight={800}>
          کارتابل {isManagedView ? "کاربر" : "من"} — {data.user.display_name}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          {isManagedView
            ? "نمای مدیریتی: این کارتابل دقیقاً همان چیزی است که کاربر با نقش و دسترسی‌های خودش می‌بیند (فقط مشاهده)."
            : "نقش‌ها، سطح دسترسی، کارهای در جریان و فعالیت‌های اخیر شما در سامانه."}
        </Typography>
      </Box>

      <ProfileCard data={data} />
      <RolesCard data={data} />
      <PermissionsCard data={data} />
      <OpenWorkCard data={data} />
      <ActivityCard data={data} />
    </Stack>
  );
}

/* ------------------------------ پروفایل ------------------------------ */
function ProfileCard({ data }: { data: CartableData }) {
  const meta = STATUS_META[data.user.status] ?? { label: data.user.status, color: "default" as const };
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
        <BadgeRoundedIcon color="primary" />
        <Typography fontWeight={800}>{data.user.display_name}</Typography>
        <Chip size="small" label={meta.label} color={meta.color} />
        <Typography variant="body2" color="text.secondary" dir="ltr">@{data.user.username}</Typography>
        <Box flexGrow={1} />
        <Typography variant="caption" color="text.secondary">
          آخرین ورود: {data.user.last_login_at ? formatJalaliDateTime(data.user.last_login_at) : "—"}
          {" · "}عضویت: {data.user.created_at ? formatJalaliDateTime(data.user.created_at) : "—"}
        </Typography>
      </Stack>
    </Paper>
  );
}

/* ------------------------------ نقش‌ها و سطح دسترسی روی داده ------------------------------ */
function RolesCard({ data }: { data: CartableData }) {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1} alignItems="center" mb={1.5}>
        <ShieldRoundedIcon fontSize="small" color="primary" />
        <Typography variant="subtitle1" fontWeight={800}>نقش‌ها و سطح دسترسی روی داده</Typography>
      </Stack>
      {data.roles.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          این حساب هیچ نقشی ندارد — دسترسی مؤثری نیز نخواهد داشت.
        </Typography>
      )}
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        {data.roles.map((r) => (
          <Paper key={r.code} variant="outlined" sx={{ p: 1.25, minWidth: 210 }}>
            <Typography variant="body2" fontWeight={700}>{r.title}</Typography>
            <Typography variant="caption" color="text.secondary" dir="ltr" display="block">{r.code}</Typography>
            <Chip
              size="small" sx={{ mt: 0.75 }}
              color={r.data_scope === "all" ? "success" : r.data_scope === "assigned" ? "warning" : "info"}
              label={`سطح داده: ${r.data_scope_title}`}
            />
          </Paper>
        ))}
      </Stack>
    </Paper>
  );
}

/* ------------------------------ دسترسی‌های مؤثر ------------------------------ */
function PermissionsCard({ data }: { data: CartableData }) {
  const p = data.permissions;
  // فاز ۵۹: باز/بسته‌شدن دسته‌جمعی بخش‌های دسترسی
  const [openMap, setOpenMap] = useState<Record<string, boolean>>({});
  const allOpen = p.sections.length > 0 && p.sections.every((s) => openMap[s.section]);
  const toggleAll = () => {
    const next: Record<string, boolean> = {};
    for (const s of p.sections) next[s.section] = !allOpen;
    setOpenMap(next);
  };
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap mb={1}>
        <ShieldRoundedIcon fontSize="small" color="primary" />
        <Typography variant="subtitle1" fontWeight={800}>دسترسی‌های مؤثر</Typography>
        <Chip
          size="small" color={p.wildcard ? "success" : "primary"}
          label={p.wildcard ? "همهٔ دسترسی‌ها (مدیر سامانه)" : `${p.total.toLocaleString("fa-IR")} دسترسی`}
        />
        <Box flexGrow={1} />
        {!p.wildcard && p.sections.length > 0 && (
          <Chip
            size="small" variant="outlined" clickable
            onClick={toggleAll}
            label={allOpen ? "بستن همه" : "بازکردن همه"}
          />
        )}
      </Stack>
      {p.wildcard && (
        <Alert severity="success" sx={{ mb: 1 }}>
          این حساب نقش «مدیر سامانه» دارد و به همهٔ بخش‌ها و داده‌ها دسترسی کامل دارد.
        </Alert>
      )}
      {!p.wildcard && p.sections.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          دسترسی مؤثری یافت نشد — نقش‌های این حساب هیچ دسترسی‌ای نگاشت نکرده‌اند.
        </Typography>
      )}
      {p.sections.map((s, idx) => (
        <Accordion
          key={s.section}
          expanded={p.wildcard ? true : !!openMap[s.section]}
          onChange={p.wildcard ? undefined : (_, ex) => setOpenMap((m) => ({ ...m, [s.section]: ex }))}
          sx={{ mt: idx === 0 ? 0.5 : 0 }}
        >
          <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="body2" fontWeight={700}>{s.section}</Typography>
              <Chip size="small" variant="outlined" label={s.count.toLocaleString("fa-IR")} />
            </Stack>
          </AccordionSummary>
          <AccordionDetails>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ width: 260 }}>کد دسترسی</TableCell>
                    <TableCell>عنوان</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {s.permissions.map((perm) => (
                    <TableRow key={perm.code}>
                      <TableCell dir="ltr" sx={{ fontSize: 12, textAlign: "right" }}>{perm.code}</TableCell>
                      <TableCell>{perm.title}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </AccordionDetails>
        </Accordion>
      ))}
    </Paper>
  );
}

/* ------------------------------ کارهای در جریان ------------------------------ */
function OpenWorkCard({ data }: { data: CartableData }) {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1} alignItems="center" mb={1.5}>
        <AssignmentRoundedIcon fontSize="small" color="primary" />
        <Typography variant="subtitle1" fontWeight={800}>
          کارهای در جریان ({data.open_work.length.toLocaleString("fa-IR")})
        </Typography>
        <Typography variant="caption" color="text.secondary">
          نمونه‌های فرایند که آخرین گامشان را این کاربر ثبت کرده یا فرایند را او شروع کرده است
        </Typography>
      </Stack>
      {data.open_work.length === 0 && (
        <Typography variant="body2" color="text.secondary">کار در جریانی وجود ندارد.</Typography>
      )}
      {data.open_work.length > 0 && (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>فرایند</TableCell>
                <TableCell>موضوع</TableCell>
                <TableCell>گام فعلی</TableCell>
                <TableCell>وضعیت</TableCell>
                <TableCell>آخرین تغییر</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.open_work.map((w) => {
                const st = WORK_STATUS[w.status] ?? { label: w.status, color: "default" as const };
                return (
                  <TableRow key={w.id}>
                    <TableCell>
                      <Typography variant="body2" fontWeight={700}>{w.definition_title ?? "—"}</Typography>
                      <Typography variant="caption" color="text.secondary" dir="ltr">{w.definition_code}</Typography>
                    </TableCell>
                    <TableCell>
                      {w.subject_label ?? w.id.slice(0, 8)}
                      <Typography variant="caption" color="text.secondary" display="block">
                        {SUBJECT_TYPES[w.subject_type] ?? w.subject_type}
                      </Typography>
                    </TableCell>
                    <TableCell>{w.current_element_name ?? "—"}</TableCell>
                    <TableCell><Chip size="small" color={st.color} label={st.label} /></TableCell>
                    <TableCell>{w.updated_at ? formatJalaliDateTime(w.updated_at) : "—"}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Paper>
  );
}

/* ------------------------------ فعالیت‌های اخیر ------------------------------ */
function ActivityCard({ data }: { data: CartableData }) {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1} alignItems="center" mb={1.5}>
        <HistoryRoundedIcon fontSize="small" color="primary" />
        <Typography variant="subtitle1" fontWeight={800}>فعالیت‌های اخیر</Typography>
        <Typography variant="caption" color="text.secondary">
          {data.stats.audit_events.toLocaleString("fa-IR")} رخداد ثبت‌شده — ۱۵ مورد اخیر
        </Typography>
      </Stack>
      {data.recent_activity.length === 0 && (
        <Typography variant="body2" color="text.secondary">فعالیتی ثبت نشده است.</Typography>
      )}
      <Stack divider={<Divider flexItem />} spacing={0.75}>
        {data.recent_activity.map((a) => (
          <Stack key={a.id} direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
            <Typography variant="body2" fontWeight={700}>{a.action_label}</Typography>
            {a.entity_type && (
              <Typography variant="caption" color="text.secondary" dir="ltr">
                {a.entity_type}#{(a.entity_id ?? "").slice(0, 8)}
              </Typography>
            )}
            {a.result !== "success" && <Chip size="small" color="error" label={a.result} />}
            <Box flexGrow={1} />
            <Typography variant="caption" color="text.secondary">
              {a.created_at ? formatJalaliDateTime(a.created_at) : ""}
            </Typography>
          </Stack>
        ))}
      </Stack>
    </Paper>
  );
}
