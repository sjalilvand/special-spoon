import { Box, Container, Paper, Stack, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { SERVICE_ICONS } from "../content/assets";
import { texts } from "../content/texts";
import SectionTitle from "./SectionTitle";

const LINKS: Record<string, string> = {
  "روان‌درمانی": "/services/psychotherapy",
};

export default function Services() {
  return (
    <Box sx={{
      position: "relative",
      py: 9,
      background: "radial-gradient(900px 340px at 88% 4%, rgba(253,231,236,.55) 0%, transparent 60%), radial-gradient(700px 300px at 6% 90%, rgba(240,230,246,.5) 0%, transparent 60%)",
      overflow: "hidden",
    }}>
      <Container id="services" sx={{ position: "relative" }}>
        <SectionTitle label="خدمات" title={texts.servicesTitle} sub={texts.servicesSub} />
        <Box display="grid" gridTemplateColumns={{ xs: "1fr", md: "1fr 1fr" }} gap={3}>
          {texts.services.map((s, idx) => {
            const icon = SERVICE_ICONS[idx] ?? null;
            const link = LINKS[s.title];
            const card = (
              <Paper
                className="hover-lift"
                elevation={3}
                sx={{
                  p: 3, borderRadius: 4, height: "100%",
                  background: "linear-gradient(150deg,#fdeef1 0%,#ffffff 75%)",
                  border: "1px solid #f6e3e8",
                }}
              >
                <Stack direction="row" spacing={2.5} alignItems="flex-start">
                  <Box sx={{
                    width: 74, height: 74, borderRadius: "50%", bgcolor: "#fff", flexShrink: 0,
                    border: "2px solid rgba(176,74,90,.22)",
                    boxShadow: "0 8px 20px rgba(176,74,90,.2)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    {icon ? (
                      <Box component="img" src={icon} alt={s.title} sx={{ height: 46 }} />
                    ) : (
                      <Box sx={{ fontSize: 32 }}>{s.emoji}</Box>
                    )}
                  </Box>
                  <Box>
                    <Typography variant="h6" fontWeight={800} color="primary.dark">{s.title}</Typography>
                    <Typography variant="body2" color="text.secondary" mt={0.5} sx={{ lineHeight: 1.9 }}>
                      {s.desc}
                    </Typography>
                    {link && (
                      <Typography variant="caption" color="primary" sx={{ mt: 1, display: "inline-block", fontWeight: 700 }}>
                        اطلاعات بیشتر ←
                      </Typography>
                    )}
                  </Box>
                </Stack>
              </Paper>
            );
            return link ? (
              <RouterLink key={s.title} to={link} style={{ textDecoration: "none" }}>{card}</RouterLink>
            ) : (
              <Box key={s.title}>{card}</Box>
            );
          })}
        </Box>
      </Container>
    </Box>
  );
}
