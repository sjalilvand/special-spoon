import {
  Avatar, Box, Card, CardContent, Chip, CircularProgress, Container, Stack, Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { fetchPublicCounselors } from "../api";
import type { PublicCounselor } from "../api";
import { texts } from "../content/texts";
import SectionTitle from "./SectionTitle";

export default function Counselors() {
  const [items, setItems] = useState<PublicCounselor[] | null>(null);

  useEffect(() => {
    fetchPublicCounselors()
      .then((d) => setItems(d))
      .catch(() => setItems([]));
  }, []);

  return (
    <Box sx={{ py: 9 }}>
      <Container id="counselors">
        <SectionTitle label="تیم ما" title={texts.counselorsTitle} sub={texts.counselorsSub} />

        {items === null && (
          <Stack alignItems="center" py={4}>
            <CircularProgress />
          </Stack>
        )}

        {items !== null && items.length === 0 && (
          <Typography textAlign="center" color="text.secondary">
            به‌زودی پروفایل مشاوران در این بخش نمایش داده می‌شود.
          </Typography>
        )}

        <Box display="grid" gridTemplateColumns={{ xs: "1fr", sm: "1fr 1fr", md: "1fr 1fr 1fr" }} gap={3}>
          {items?.map((c) => (
            <Card key={c.id} className="hover-lift" elevation={2} sx={{ borderRadius: 4, border: "1px solid #f6e3e8" }}>
              <CardContent sx={{ textAlign: "center", p: 3 }}>
                {c.photo_url ? (
                  <Box
                    component="img"
                    src={c.photo_url}
                    alt={c.name}
                    sx={{ width: 110, height: 110, borderRadius: "50%", objectFit: "cover", mx: "auto", mb: 1.5, border: "3px solid", borderColor: "primary.light" }}
                  />
                ) : (
                  <Avatar sx={{ width: 110, height: 110, mx: "auto", mb: 1.5, fontSize: 40, bgcolor: "primary.light" }}>
                    {c.name.charAt(0)}
                  </Avatar>
                )}
                <Typography variant="h6" fontWeight={700}>{c.name}</Typography>
                {c.professional_title && (
                  <Typography variant="body2" color="text.secondary">{c.professional_title}</Typography>
                )}
                {c.specialty && (
                  <Chip size="small" label={c.specialty} color="primary" variant="outlined" sx={{ mt: 1 }} />
                )}
              </CardContent>
            </Card>
          ))}
        </Box>
      </Container>
    </Box>
  );
}
