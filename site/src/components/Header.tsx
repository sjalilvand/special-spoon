import { AppBar, Box, Button, Stack, Toolbar, Typography } from "@mui/material";
import { SUGGESTED } from "../content/assets";
import { texts } from "../content/texts";

export default function Header() {
  return (
    <AppBar
      position="sticky"
      elevation={0}
      sx={{ bgcolor: "rgba(255,255,255,0.96)", backdropFilter: "blur(8px)", borderBottom: "1px solid #f6e3e8" }}
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
            sx={{ color: "text.primary", display: { xs: "none", md: "inline-flex" }, fontWeight: 600 }}
          >
            {n.label}
          </Button>
        ))}
        <Button
          href="/booking"
          variant="outlined"
          size="small"
          sx={{ borderColor: "primary.main", color: "primary.main", fontWeight: 700 }}
        >
          رزرو نوبت
        </Button>
        <Button
          href="/panel/"
          variant="outlined"
          size="small"
          sx={{ display: { xs: "none", md: "inline-flex" }, borderColor: "secondary.main", color: "secondary.main", fontWeight: 700 }}
        >
          ورود به سامانه
        </Button>
        <Button
          href="#consult"
          size="small"
          sx={{
            background: "linear-gradient(135deg,#b04a5a 0%,#8a3342 100%)",
            color: "#fff",
            fontWeight: 700,
            "&:hover": { background: "linear-gradient(135deg,#a03e4e 0%,#7a2c3a 100%)" },
          }}
        >
          درخواست مشاوره
        </Button>
      </Toolbar>
    </AppBar>
  );
}