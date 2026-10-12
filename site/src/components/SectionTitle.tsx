import { Stack, Typography } from "@mui/material";

export default function SectionTitle({
  label, title, sub, light = false,
}: {
  label: string;
  title: string;
  sub?: string;
  light?: boolean;
}) {
  return (
    <Stack spacing={1} alignItems="center" mb={5}>
      <Typography
        variant="caption"
        sx={{
          bgcolor: light ? "rgba(255,255,255,0.18)" : "#fde7ec",
          color: light ? "#fff" : "primary.main",
          px: 2, py: 0.5, borderRadius: 99, fontWeight: 700,
        }}
      >
        {label}
      </Typography>
      <Typography variant="h4" fontWeight={800} color={light ? "#fff" : "primary.main"} textAlign="center">
        {title}
      </Typography>
      {sub && (
        <Typography
          variant="body1"
          sx={{ maxWidth: 620, textAlign: "center", color: light ? "rgba(255,255,255,0.88)" : "text.secondary" }}
        >
          {sub}
        </Typography>
      )}
    </Stack>
  );
}
