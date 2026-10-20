// فاز ۴۷ - بازسازماندهی منوها: گروه‌بندی ۲۵ آیتم در ۷ منوی پایه‌ای با آیکون و توضیح
// هدف: رفع شلوغی/نامفهومی نوار بالا — نام گروه‌ها کوتاه، کدهای B در توضیح آیتم‌ها
import { ReactNode, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  AppBar, Box, Button, Chip, Container, Divider, IconButton, ListItemIcon,
  ListItemText, Menu, MenuItem, Stack, Toolbar, Tooltip, Typography,
} from "@mui/material";
import ArrowDropDownIcon from "@mui/icons-material/ArrowDropDown";
import DashboardRoundedIcon from "@mui/icons-material/DashboardRounded";
import FolderSharedRoundedIcon from "@mui/icons-material/FolderSharedRounded";
import PeopleAltRoundedIcon from "@mui/icons-material/PeopleAltRounded";
import SchoolRoundedIcon from "@mui/icons-material/SchoolRounded";
import AccountBalanceWalletRoundedIcon from "@mui/icons-material/AccountBalanceWalletRounded";
import CorporateFareRoundedIcon from "@mui/icons-material/CorporateFareRounded";
import SettingsSuggestRoundedIcon from "@mui/icons-material/SettingsSuggestRounded";
import NotificationsNoneRoundedIcon from "@mui/icons-material/NotificationsNoneRounded";
import LockResetRoundedIcon from "@mui/icons-material/LockResetRounded";
import LogoutRoundedIcon from "@mui/icons-material/LogoutRounded";
import PublicRoundedIcon from "@mui/icons-material/PublicRounded";
import PersonPanelRoundedIcon from "@mui/icons-material/PersonRounded";
import {
  Badge, Dashboard as DashboardIcon, Description, Diversity3, EventNote,
  Folder, Forum, Gavel, GroupAdd, HealthAndSafety, HistoryEdu,
  Inbox, Insights, Map, MenuBook, Paid, PersonSearch, Psychology, QueryStats,
  Receipt, RequestQuote, Rule, SupportAgent, UploadFile, Warning,
  Wallet, Web, VerifiedUser,
} from "@mui/icons-material";

// آیکون ویرایشگر تخصصی: VerifiedUser بدون ایمپورت وسط فایل
const VerifiedUserIconSafe = VerifiedUser;
const BrandIcon = Psychology;
import { useAuth } from "../auth/AuthContext";
import NotificationBell from "./NotificationBell";

type Roles = string[];

interface NavItem {
  label: string;
  code?: string;
  path: string;
  roles: Roles;
  icon: ReactNode;
  danger?: boolean;
}

interface NavGroup {
  label: string;
  icon: ReactNode;
  items: NavItem[];
}

const ALL_STAFF: Roles = ["ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "SYSTEM_ADMIN"];

/** نقشه منو — نقش‌ها عیناً از نسخه قبلی حفظ شده‌اند؛ فقط گروه‌بندی و برچسب تمیز شد */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "میز کار",
    icon: <DashboardRoundedIcon />,
    items: [
      { label: "داشبورد عملیاتی", path: "/dashboard", roles: ALL_STAFF, icon: <DashboardIcon /> },
      { label: "داشبورد مدیر", code: "B24", path: "/admin-dashboard", roles: ["ORG_MANAGER", "SYSTEM_ADMIN"], icon: <QueryStats /> },
      { label: "گزارش انطباق DPO", path: "/dpo-report", roles: ["ORG_MANAGER", "SYSTEM_ADMIN", "DPO"], icon: <Gavel /> },
    ],
  },
  {
    label: "پرونده و درمان",
    icon: <FolderSharedRoundedIcon />,
    items: [
      { label: "پرونده‌ها", path: "/cases", roles: ["ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR"], icon: <Folder /> },
      { label: "درخواست‌های مشاوره", path: "/consultation-requests", roles: ["ORG_MANAGER", "RECEPTION", "SYSTEM_ADMIN", "COUNSELOR"], icon: <Inbox /> },
      { label: "کارتابل مشاور", path: "/worklist", roles: ["COUNSELOR"], icon: <EventNote /> },
      { label: "ارزیابی‌های من", path: "/my-assessments", roles: ["COUNSELOR"], icon: <HistoryEdu /> },
      { label: "بررسی‌های فنی", path: "/reviews", roles: ["TECHNICAL_SUPERVISOR"], icon: <Rule /> },
      { label: "هشدارهای سطح ۳", path: "/level3-alerts", roles: ["TECHNICAL_SUPERVISOR"], icon: <Warning />, danger: true },
      { label: "پرونده‌های تحت نظارت", path: "/supervised-cases", roles: ["TECHNICAL_SUPERVISOR"], icon: <HealthAndSafety /> },
    ],
  },
  {
    label: "پذیرش و مشتریان",
    icon: <PeopleAltRoundedIcon />,
    items: [
      { label: "متقاضیان", path: "/applicants", roles: ["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION"], icon: <PersonSearch /> },
      { label: "ورود اکسل", path: "/imports", roles: ["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION"], icon: <UploadFile /> },
    ],
  },
  {
    label: "محتوا و آموزش",
    icon: <SchoolRoundedIcon />,
    items: [
      { label: "دسته‌بندی موضوعی", code: "B32", path: "/topics", roles: ALL_STAFF, icon: <Badge /> },
      { label: "محتوا و دوره‌ها", code: "B33–B36", path: "/learning", roles: ALL_STAFF, icon: <MenuBook /> },
      { label: "مرکز آزمون روان‌شناسی", code: "B37", path: "/psych-tests", roles: ["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "COUNSELOR", "RECEPTION", "APPLICANT"], icon: <Psychology /> },
    ],
  },
  {
    label: "مالی",
    icon: <AccountBalanceWalletRoundedIcon />,
    items: [
      { label: "سفارش و پرداخت", code: "B10", path: "/orders", roles: ["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION"], icon: <Paid /> },
      { label: "کیف پول", code: "B18", path: "/wallet", roles: ["*"], icon: <Wallet /> },
      { label: "حسابداری", code: "B22", path: "/accounting", roles: ["SYSTEM_ADMIN", "ORG_MANAGER"], icon: <Receipt /> },
      { label: "خدمات و تعرفه‌ها", path: "/services", roles: ALL_STAFF, icon: <RequestQuote /> },
    ],
  },
  {
    label: "سازمان و منابع",
    icon: <CorporateFareRoundedIcon />,
    items: [
      { label: "سازمان‌ها", code: "B21", path: "/organizations", roles: ["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR"], icon: <CorporateFareRoundedIcon /> },
      { label: "مشاوران", path: "/counselors", roles: ["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR"], icon: <Diversity3 /> },
      { label: "بازبینی صلاحیت", path: "/verification-reviews", roles: ["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR"], icon: <VerifiedUserIconSafe /> },
      { label: "شعب", code: "B31", path: "/branches", roles: ["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR"], icon: <Map /> },
    ],
  },
  {
    label: "سامانه و پشتیبانی",
    icon: <SettingsSuggestRoundedIcon />,
    items: [
      { label: "فرایندها (BPMN)", path: "/processes", roles: ALL_STAFF, icon: <Insights /> },
      { label: "پشتیبانی", code: "B23", path: "/support", roles: [...ALL_STAFF, "APPLICANT"], icon: <SupportAgent /> },
      { label: "دستیار هوشمند", path: "/assistant", roles: [...ALL_STAFF, "APPLICANT"], icon: <Forum /> },
      { label: "یکپارچه‌سازی‌ها", code: "B28", path: "/integrations", roles: ["SYSTEM_ADMIN", "ORG_MANAGER"], icon: <Web /> },
      { label: "کاربران", path: "/users", roles: ["SYSTEM_ADMIN"], icon: <GroupAdd /> },
      { label: "رخدادهای امنیتی", path: "/audit-events", roles: ["SYSTEM_ADMIN"], icon: <Description /> },
    ],
  },
];

function useNavVisibility(has: (rs: Roles) => boolean) {
  const visibleGroups = NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((it) => it.roles.includes("*") || has(it.roles)),
  })).filter((g) => g.items.length > 0);
  return visibleGroups;
}

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const roles = user?.roles ?? [];
  const has = (rs: Roles) => rs.some((r) => roles.includes(r));
  const visibleGroups = useNavVisibility(has);
  const isApplicant = has(["APPLICANT"]);

  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const openMenu = (e: React.MouseEvent<HTMLElement>, label: string) => {
    setAnchorEl(e.currentTarget);
    setOpenGroup(label);
  };
  const closeMenu = () => {
    setAnchorEl(null);
    setOpenGroup(null);
  };
  const go = (path: string) => {
    closeMenu();
    navigate(path);
  };

  const groupActive = (g: NavGroup) =>
    g.items.some((it) => location.pathname === it.path || location.pathname.startsWith(it.path + "/"));

  return (
    <Box minHeight="100vh" bgcolor="#fffafb">
      <AppBar position="static" elevation={1}>
        <Toolbar
          disableGutters
          sx={{
            gap: 0.5, px: { xs: 1.5, md: 2.5 },
            flexWrap: "nowrap", overflowX: "auto",
            "::-webkit-scrollbar": { display: "none" }, scrollbarWidth: "none",
            minHeight: { xs: 56, md: 62 }, alignItems: "center",
          }}
        >
          <Stack direction="row" alignItems="center" spacing={1} sx={{ flexShrink: 0, cursor: "pointer" }}
            onClick={() => navigate("/")}>
            <BrandIcon sx={{ display: { xs: "none", md: "block" } }} />
            <Typography variant="h6" sx={{ fontWeight: 800, whiteSpace: "nowrap" }}>Rosepsy</Typography>
          </Stack>
          <Tooltip title="مشاهده سایت عمومی">
            <IconButton color="inherit" size="small" href="/" sx={{ flexShrink: 0 }}>
              <PublicRoundedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Divider orientation="vertical" flexItem sx={{ borderColor: "rgba(255,255,255,.25)", mx: 0.5, flexShrink: 0 }} />

          {isApplicant && (
            <Button color="inherit" startIcon={<PersonPanelRoundedIcon />} sx={{ flexShrink: 0 }}
              onClick={() => navigate("/me")}>پنل من</Button>
          )}

          {visibleGroups.map((g) => {
            const active = groupActive(g);
            return (
              <Button
                key={g.label}
                color="inherit"
                disableElevation
                endIcon={<ArrowDropDownIcon />}
                onClick={(e) => openMenu(e, g.label)}
                sx={{
                  flexShrink: 0, whiteSpace: "nowrap", px: { xs: 1, md: 1.5 }, minWidth: 0,
                  bgcolor: active ? "rgba(255,255,255,.16)" : "transparent",
                  "&:hover": { bgcolor: "rgba(255,255,255,.12)" },
                }}
              >
                <Stack direction="row" spacing={0.75} alignItems="center">
                  <Box component="span" sx={{ display: { xs: "none", md: "inline-flex" }, lineHeight: 0 }}>
                    {g.icon}
                  </Box>
                  <span>{g.label}</span>
                </Stack>
              </Button>
            );
          })}

          <Box flexGrow={1} minWidth={8} />

          <NotificationBell />
          <Tooltip title="اعلان‌ها">
            <IconButton color="inherit" size="small" onClick={() => navigate("/notifications")}>
              <NotificationsNoneRoundedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="تغییر رمز عبور">
            <IconButton color="inherit" size="small" onClick={() => navigate("/change-password")}>
              <LockResetRoundedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          {user && (
            <Chip
              size="small"
              sx={{ bgcolor: "rgba(255,255,255,.22)", color: "#fff", fontWeight: 700, flexShrink: 0 }}
              label={user.display_name}
            />
          )}
          <Tooltip title="خروج از حساب">
            <IconButton color="inherit" size="small"
              onClick={async () => { await logout(); navigate("/login"); }}>
              <LogoutRoundedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>

      {/* منوی پایه‌ای گروه‌ها */}
      <Menu
        anchorEl={anchorEl}
        open={openGroup !== null}
        onClose={closeMenu}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{ paper: { sx: { minWidth: 260, maxHeight: "72vh", mt: 0.75 } } }}
      >
        {openGroup &&
          visibleGroups
            .find((g) => g.label === openGroup)!
            .items.map((it, idx) => (
              <span key={it.path}>
                {idx > 0 && <Divider sx={{ my: 0.25 }} />}
                <MenuItem
                  onClick={() => go(it.path)}
                  selected={location.pathname === it.path}
                  sx={{ py: 1 }}
                >
                  <ListItemIcon sx={{ minWidth: 38, color: it.danger ? "error.main" : "primary.main" }}>
                    {it.icon}
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Stack direction="row" spacing={1} alignItems="center">
                        <Typography variant="body2" fontWeight={700}>{it.label}</Typography>
                        {it.code && (
                          <Chip size="small" variant="outlined" sx={{ height: 18, fontSize: 10 }} label={it.code} />
                        )}
                      </Stack>
                    }
                  />
                </MenuItem>
              </span>
            ))}
      </Menu>

      <Container maxWidth="lg" sx={{ mt: 4, pb: 6 }}>
        {children}
      </Container>
    </Box>
  );
}
