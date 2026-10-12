import { Box, Container, Paper, Stack, Typography } from "@mui/material";
import { useState } from "react";
import { SERVICE_ICONS } from "../content/assets";
import { texts } from "../content/texts";
import SectionTitle from "./SectionTitle";

const TINTS = [
  "linear-gradient(150deg,#fdeef1 0%,#ffffff 75%)",
  "linear-gradient(150deg,#f3eef8 0%,#ffffff 75%)",
  "linear-gradient(150deg,#eef6f5 0%,#ffffff 75%)",
  "linear-gradient(150deg,#fef3e7 0%,#ffffff 75%)",
];

function ServiceCard({ title, desc, emoji, icon, tint }: {
  title: string; desc: string; emoji: string; icon: string | null; tint: string;
}) {
  const [imgOk, setImgOk] = useState(true);
  const showImg = Boolean(icon) && imgOk;

  return (
    <Paper
      className="hover-lift"
      elevation={2}
      sx={{ p: 3, borderRadius: 4, height: "100%", background: tint, border: "1px solid #f6e3e8" }}
    >
      <Stack direction="row" spacing={2.5} alignItems="flex-start">
        <Box sx={{
          width: 72, height: 72, borderRadius: "50%", bgcolor: "#fff", flexShrink: 0,
          boxShadow: "0 6px 18px rgba(176,74,90,.16)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          {showImg && icon ? (
            <Box component="img" src={icon} alt={title} sx={{ height: 44 }} onError={() => setImgOk(false)} />
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
    <Container id="services" sx={{ py: 9 }}>
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
          />
        ))}
      </Box>
    </Container>
  );
}
