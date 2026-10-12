import { Box, Container, Paper, Stack, Typography } from "@mui/material";
import { useState } from "react";
import { SUGGESTED } from "../content/assets";
import { texts } from "../content/texts";

export default function About() {
  const [imgOk, setImgOk] = useState(true);
  const img = SUGGESTED.about;

  return (
    <Container id="about" sx={{ py: 8 }}>
      <Typography variant="h4" fontWeight={800} color="primary.main" mb={4} textAlign="center">
        {texts.aboutTitle}
      </Typography>
      <Stack direction={{ xs: "column", md: "row" }} spacing={4} alignItems="center">
        {img && imgOk && (
          <Box
            component="img"
            src={img}
            alt={texts.aboutTitle}
            onError={() => setImgOk(false)}
            sx={{ width: { xs: "100%", md: 380 }, borderRadius: 4, boxShadow: 3 }}
          />
        )}
        <Stack spacing={2}>
          {texts.about.map((p, i) => (
            <Typography key={i} variant="body1" color="text.primary">
              {p}
            </Typography>
          ))}
          <Stack direction="row" spacing={2} mt={2} flexWrap="wrap" useFlexGap>
            {texts.stats.map((s) => (
              <Paper key={s.label} elevation={1} sx={{ p: 2, minWidth: 130, textAlign: "center" }}>
                <Typography variant="h5" fontWeight={800} color="primary.main">
                  {s.n}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {s.label}
                </Typography>
              </Paper>
            ))}
          </Stack>
        </Stack>
      </Stack>
    </Container>
  );
}
