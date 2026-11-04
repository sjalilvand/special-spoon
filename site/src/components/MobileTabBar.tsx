import {
  Box, Button, Drawer, List, ListItem, Paper, Stack, Typography,
} from "@mui/material";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

// فاز ۸۰ - رویداد نصب PWA (اندروید/کروم). تایپ استاندارد هنوز در lib.dom نیست.
type InstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

// ---------------------------------------------------------------------------
// فاز ۷۹ - نوار ناوبری اپیِ موبایل (تجربهٔ PWA)
// روی نمایشگرهای کوچک‌تر از lg، نوار ثابت پایین صفحه مثل یک اپ واقعی عمل می‌کند:
//   خانه | خدمات | [رزرو نوبت] | کلینیک‌ها | بیشتر
// «بیشتر» کشوی کامل منو را باز می‌کند (ورود به سامانه، صفحات داخلی، دانلود اپ).
// آیکون‌ها SVG داخلی‌اند تا وابستگی @mui/icons-material اضافه نشود.
// ---------------------------------------------------------------------------

function Svg({ children }: { children: ReactNode }) {
  return (
    <svg
      width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
    >
      {children}
    </svg>
  );
}

const IconHome = () => (
  <Svg>
    <path d="M3.5 10.5 12 3.5l8.5 7" />
    <path d="M6 9.3V20.5h12V9.3" />
  </Svg>
);

const IconServices = () => (
  <Svg>
    <rect x="4" y="4" width="7" height="7" rx="2" />
    <rect x="13" y="4" width="7" height="7" rx="2" />
    <rect x="4" y="13" width="7" height="7" rx="2" />
    <rect x="13" y="13" width="7" height="7" rx="2" />
  </Svg>
);

const IconCalendar = () => (
  <Svg>
    <rect x="4" y="5.5" width="16" height="15" rx="3" />
    <path d="M8 3.5v4M16 3.5v4M4 10.5h16" />
    <path d="M12 13.5v4M10 15.5h4" />
  </Svg>
);

const IconClinics = () => (
  <Svg>
    <path d="M12 21s-7-5.6-7-11a7 7 0 0 1 14 0c0 5.4-7 11-7 11z" />
    <circle cx="12" cy="10" r="2.6" />
  </Svg>
);

const IconMore = () => (
  <Svg>
    <circle cx="5" cy="12" r="1.7" fill="currentColor" stroke="none" />
    <circle cx="12" cy="12" r="1.7" fill="currentColor" stroke="none" />
    <circle cx="19" cy="12" r="1.7" fill="currentColor" stroke="none" />
  </Svg>
);

const MORE_ITEMS = [
  { label: "ورود به سامانه (پنل)", to: "/panel/" },
  { label: "مشاوره آنلاین و تلفنی", to: "/services/psychotherapy" },
  { label: "مسیر دریافت نوبت", to: "/#steps" },
  { label: "مشاوران", to: "/#counselors" },
  { label: "قوانین پرداخت و استرداد وجه", to: "/payment-rules" },
  { label: "سوالات پرتکرار", to: "/#faq" },
  { label: "تماس با ما", to: "/#contact" },
];

export default function MobileTabBar() {
  const { pathname, hash } = useLocation();
  const [more, setMore] = useState(false);
  const [installEvt, setInstallEvt] = useState<InstallPromptEvent | null>(null);

  // فاز ۸۰ - گرفتن رویداد نصب PWA: اگر مرورگر اجازهٔ نصب بدهد، دکمهٔ «نصب روی گوشی»
  // در کشوی «بیشتر» ظاهر می‌شود؛ اگر اپ از قبل نصب باشد (standalone) دیده نمی‌شود.
  useEffect(() => {
    const isStandalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      (window.navigator as Navigator & { standalone?: boolean }).standalone === true;
    if (isStandalone) return;
    const onBip = (e: Event) => {
      e.preventDefault();
      setInstallEvt(e as InstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onBip);
    return () => window.removeEventListener("beforeinstallprompt", onBip);
  }, []);

  const doInstall = () => {
    const evt = installEvt;
    setMore(false);
    setInstallEvt(null);
    evt?.prompt().catch(() => {});
  };

  const tabSx = (active: boolean) => ({
    flex: 1,
    alignItems: "center",
    gap: 0.4,
    textDecoration: "none",
    color: active ? "primary.main" : "text.secondary",
    py: 0.4,
  });

  const labelSx = (active: boolean) => ({
    fontSize: 10.5,
    fontWeight: active ? 800 : 600,
    lineHeight: 1.3,
  });

  return (
    <>
      <Paper
        elevation={0}
        sx={{
          position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 1300,
          display: { xs: "block", lg: "none" },
          borderRadius: "20px 20px 0 0",
          borderTop: "1px solid #f3dce2",
          bgcolor: "rgba(255,255,255,0.97)",
          backdropFilter: "blur(14px)",
          boxShadow: "0 -8px 30px rgba(124,39,64,.10)",
          px: 0.5, pt: 1,
          pb: "calc(8px + env(safe-area-inset-bottom))",
        }}
      >
        <Stack direction="row" justifyContent="space-around" alignItems="flex-end">
          <Stack component={Link} to="/" sx={tabSx(pathname === "/")}>
            <IconHome />
            <Typography sx={labelSx(pathname === "/")}>خانه</Typography>
          </Stack>

          <Stack component={Link} to="/#services" sx={tabSx(hash === "#services")}>
            <IconServices />
            <Typography sx={labelSx(hash === "#services")}>خدمات</Typography>
          </Stack>

          {/* CTA وسط — برجسته */}
          <Stack component={Link} to="/booking" sx={{ ...tabSx(pathname === "/booking"), mt: "-26px" }}>
            <Box
              sx={{
                width: 54, height: 54, borderRadius: "50%",
                bgcolor: "primary.main", color: "#fff",
                display: "flex", alignItems: "center", justifyContent: "center",
                border: "4px solid #fff",
                boxShadow: "0 10px 24px rgba(168,58,84,.40)",
              }}
            >
              <IconCalendar />
            </Box>
            <Typography sx={labelSx(pathname === "/booking")}>رزرو نوبت</Typography>
          </Stack>

          <Stack component={Link} to="/clinics" sx={tabSx(pathname.startsWith("/clinics"))}>
            <IconClinics />
            <Typography sx={labelSx(pathname.startsWith("/clinics"))}>کلینیک‌ها</Typography>
          </Stack>

          <Stack
            component="button"
            onClick={() => setMore(true)}
            sx={{
              ...tabSx(false),
              bgcolor: "transparent", border: "none", cursor: "pointer",
              font: "inherit", p: 0.4,
            }}
          >
            <IconMore />
            <Typography sx={labelSx(false)}>بیشتر</Typography>
          </Stack>
        </Stack>
      </Paper>

      <Drawer
        anchor="bottom"
        open={more}
        onClose={() => setMore(false)}
        sx={{ zIndex: 1500 }} /* بالاتر از تب‌بار (1300) تا کشو روی آن بنشیند */
        PaperProps={{
          sx: {
            borderTopLeftRadius: 20, borderTopRightRadius: 20,
            p: 2, pb: "calc(20px + env(safe-area-inset-bottom))",
          },
        }}
      >
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1.5}>
          <Typography variant="h6" fontWeight={800} color="primary">منوی رزپسی</Typography>
          <Button size="small" onClick={() => setMore(false)} sx={{ minWidth: 0 }}>بستن</Button>
        </Stack>
        <List disablePadding>
          {MORE_ITEMS.map((m) => (
            <ListItem
              key={m.label}
              component={Link}
              to={m.to}
              onClick={() => setMore(false)}
              sx={{ borderRadius: 2, color: "text.primary", fontWeight: 600, mb: 0.5, "&:hover": { bgcolor: "#faf0f3" } }}
            >
              {m.label}
            </ListItem>
          ))}
          {/* فاز ۸۰ - نصب مستقیم PWA (وقتی مرورگر اجازه دهد) */}
          {installEvt && (
            <ListItem
              component="button"
              onClick={doInstall}
              sx={{
                borderRadius: 2, color: "#fff", fontWeight: 800, mt: 1,
                bgcolor: "primary.main", width: "100%", textAlign: "right",
                border: "none", cursor: "pointer", font: "inherit",
                "&:hover": { bgcolor: "#6a2137" },
              }}
            >
              ⬇️ نصب اپ روی گوشی (PWA)
            </ListItem>
          )}
          <ListItem
            component="a"
            href="/app/rosepsy-1.0.0.apk"
            onClick={() => setMore(false)}
            sx={{ borderRadius: 2, color: "primary.main", fontWeight: 800, mt: 1, bgcolor: "#faf0f3", "&:hover": { bgcolor: "#f3dce2" } }}
          >
            📲 دانلود اپ اندروید (APK)
          </ListItem>
          <Typography sx={{ fontSize: 11.5, color: "text.secondary", px: 1, mt: 1, lineHeight: 1.9 }}>
            راهنما: در کروم منوی سه‌نقطه ← «Add to Home screen» و در آیفون دکمهٔ اشتراک ← «Add to Home Screen» — رزپسی مثل اپ واقعی تمام‌صفحه باز می‌شود.
          </Typography>
        </List>
      </Drawer>
    </>
  );
}
