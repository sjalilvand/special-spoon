import { Box, Container, Paper, Stack, Typography } from "@mui/material";
import { useState } from "react";
import { SERVICE_ICONS } from "../content/assets";
import { texts } from "../content/texts";
import SectionTitle from "./SectionTitle";

const TINTS = [
  "linear-gradient(150deg,#fbd9e2 0%,#fff7f9 85%)",
  "linear-gradient(150deg,#e6d9f4 0%,#faf7fd 85%)",
  "linear-gradient(150deg,#d3ece8 0%,#f4fbfa 85%)",
  "linear-gradient(150deg,#fce5c8 0%,#fffaf2 85%)",
];

const RINGS = [
  "2px solid rgba(176,74,90,.22)",
  "2px solid rgba(122,92,138,.22)",
  "2px solid rgba(15,118,110,.2)",
  "2px solid rgba(194,120,3,.22)",
];

function ServiceCard({ title, desc, emoji, icon, tint, ring }: {
  title: string; desc: string; emoji: string; icon: string | null; tint: string; ring: string;
}) {
  const [imgOk, setImgOk] = useState(true);
  const showImg = Boolean(icon) && imgOk;

  return (
    <Paper
      className="hover-lift"
      elevation={3}
      sx={{ p: 3, borderRadius: 4, height: "100%", background: tint, border: "1px solid #f3dde4" }}
    >
      <Stack direction="row" spacing={2.5} alignItems="flex-start">
        <Box sx={{
          width: 74, height: 74, borderRadius: "50%", bgcolor: "#fff", flexShrink: 0,
          border: ring,
          boxShadow: "0 8px 20px rgba(176,74,90,.2)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          {showImg && icon ? (
            <Box component="img" src={icon} alt={title} sx={{ height: 46 }} onError={() => setImgOk(false)} />
          ) : (
            <Box sx={{ fontSize: 32 }}>{emoji}</Box>
          )}
        </Box>
        <Box>
          <Typography variant="h6" fontWeight={800} color="primary.dark">{title}</Typography>
          <Typography variant="body2" color="text.secondary" mt={0.5} sx={{ lineHeight: 1.9 }}>
            {desc}
          </Typography>
        </Box>
      </Stack>
    </Paper>
  );
}

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
          {texts.services.map((s, idx) => (
            <ServiceCard
              key={s.title}
              title={s.title}
              desc={s.desc}
              emoji={s.emoji}
              icon={SERVICE_ICONS[idx] ?? null}
              tint={TINTS[idx % TINTS.length]}
              ring={RINGS[idx % RINGS.length]}
            />
          ))}
        </Box>
      </Container>
    </Box>
  );
}
