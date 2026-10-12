import { Box, Container, Paper, Stack, Typography } from "@mui/material";
import { useState } from "react";
import { SUGGESTED } from "../content/assets";
import { texts } from "../content/texts";
import SectionTitle from "./SectionTitle";

export default function About() {
  const [imgOk, setImgOk] = useState(true);
  const img = SUGGESTED.about;

  return (
    <Container id="about" sx={{ py: 9 }}>
      <SectionTitle label="ما که هستیم" title={texts.aboutTitle} />
      <Stack direction={{ xs: "column", md: "row" }} spacing={4} alignItems="center">
        {img && imgOk && (
          <Box
            component="img"
            src={img}
            alt={texts.aboutTitle}
            onError={() => setImgOk(false)}
            sx={{ width: { xs: "100%", md: 360 }, borderRadius: 4, boxShadow: "0 14px 34px rgba(176,74,90,.16)", border: "1px solid #f6e3e8" }}
          />
        )}
        <Stack spacing={2}>
          {texts.about.map((p, i) => (
            <Typography key={i} variant="body1" color="text.primary" sx={{ lineHeight: 2 }}>
              {p}
            </Typography>
          ))}
          <Stack direction="row" spacing={2} mt={2} flexWrap="wrap" useFlexGap>
            {texts.stats.map((s) => (
              <Paper key={s.label} elevation={1} sx={{ p: 2, minWidth: 130, textAlign: "center", borderRadius: 3 }}>
                <Typography variant="h5" fontWeight={800} color="primary.main">{s.n}</Typography>
                <Typography variant="caption" color="text.secondary">{s.label}</Typography>
              </Paper>
            ))}
          </Stack>
        </Stack>
      </Stack>
    </Container>
  );
}
