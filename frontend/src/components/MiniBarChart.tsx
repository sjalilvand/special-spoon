import { Box, Paper, Stack, Tooltip, Typography } from "@mui/material";
import { jalaliShort } from "../utils/jalali";

// فاز ۲۶ - B24: نمودار ستونی سبک SVG (بدون وابستگی جدید)
export default function MiniBarChart({
  title, data, height = 140, color = "#5b4b8a", emptyText = "داده‌ای در این بازه نیست",
}: {
  title: string;
  data: { date: string; count: number }[];
  height?: number;
  color?: string;
  emptyText?: string;
}) {
  const max = Math.max(...data.map((d) => d.count), 1);
  const nonEmpty = data.some((d) => d.count > 0);

  return (
    <Paper variant="outlined" sx={{ p: 2 }} role="img" aria-label={`${title}: نمودار ستونی ${data.length} روز`}>
      <Typography variant="subtitle2" fontWeight={700} mb={1}>{title}</Typography>
      {!nonEmpty ? (
        <Typography variant="body2" color="text.secondary" py={3} textAlign="center">
          {emptyText}
        </Typography>
      ) : (
        <Box sx={{ display: "flex", alignItems: "flex-end", gap: "2px", height, px: 0.5, direction: "ltr" }}>
          {data.map((d, i) => {
            const h = d.count > 0 ? Math.max(4, (d.count / max) * 100) : 1;
            return (
              <Tooltip key={d.date + i} title={`${jalaliShort(d.date)}: ${d.count.toLocaleString("fa-IR")}`} arrow>
                <Box
                  sx={{
                    flex: 1, minWidth: 2,
                    height: `${h}%`,
                    bgcolor: d.count > 0 ? color : "#ede7f6",
                    borderRadius: "3px 3px 0 0",
                    transition: "height .3s",
                  }}
                />
              </Tooltip>
            );
          })}
        </Box>
      )}
      <Stack direction="row" justifyContent="space-between" mt={0.5}>
        <Typography variant="caption" color="text.secondary">{jalaliShort(data[0]?.date)}</Typography>
        <Typography variant="caption" color="text.secondary">{jalaliShort(data[data.length - 1]?.date)}</Typography>
      </Stack>
    </Paper>
  );
}
