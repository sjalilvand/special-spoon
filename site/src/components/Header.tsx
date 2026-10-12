import { AppBar, Box, Button, Stack, Toolbar, Typography } from "@mui/material";
import { SUGGESTED } from "../content/assets";
import { texts } from "../content/texts";

export default function Header() {
  return (
    <AppBar
      position="sticky"
      elevation={0}
      sx={{ bgcolor: "rgba(255,255,255,0.94)", backdropFilter: "blur(8px)" }}
    >
      <Toolbar sx={{ gap: 1 }}>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ flexGrow: 1 }}>
          {SUGGESTED.logo ? (
            <Box component="img" src={SUGGESTED.logo} alt={texts.brand} sx={{ height: 46 }} />
          ) : (
            <Typography variant="h6" fontWeight={800} color="primary">
              {texts.brand}
            </Typography>
          )}
          <Typography variant="caption" color="text.secondary" sx={{ display: { xs: "none", md: "block" } }}>
            {texts.brandSub}
          </Typography>
        </Stack>
        {texts.nav.map((n) => (
          <Button
            key={n.id}
            href={`#${n.id}`}
            sx={{ color: "text.primary", display: { xs: "none", md: "inline-flex" } }}
          >
            {n.label}
          </Button>
        ))}
        {/* ناوبری سخت — پنل اپ جداگانه است و RouterLink نباید استفاده شود */}
        <Button
          href="/panel"
          variant="outlined"
          size="small"
          sx={{ display: { xs: "none", md: "inline-flex" } }}
        >
          ورود به سامانه
        </Button>
        <Button href="#consult" variant="contained" size="small">
          درخواست مشاوره
        </Button>
      </Toolbar>
    </AppBar>
  );
}
