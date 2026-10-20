// فاز ۴۷ - کیت فرم یکپارچه: بخش‌بندی سربرگ‌دار، حالت خالی و ویرایشگر گزینه‌ها
// هدف: همه فرم‌ها و پرسشنامه‌ها یک قیافه مرتب و قابل‌فهم داشته باشند
import { Box, Button, Chip, IconButton, Paper, Stack, TextField, Typography } from "@mui/material";
import AddCircleOutlineRoundedIcon from "@mui/icons-material/AddCircleOutlineRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import InboxRoundedIcon from "@mui/icons-material/InboxRounded";
import { ReactNode } from "react";

/** بخش فرم: سربرگ شماره‌دار + توضیح یک‌خطی + محتوای گرید */
export function FormSection({
  step, title, subtitle, action, children,
}: {
  step?: string | number;
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Paper variant="outlined" sx={{ overflow: "hidden" }}>
      <Stack
        direction="row"
        alignItems="center"
        spacing={1.25}
        sx={{
          px: 2, py: 1.25,
          bgcolor: "#faf3f4",
          borderBottom: "1px solid #f0e4e6",
        }}
      >
        {step !== undefined && (
          <Box sx={{
            width: 26, height: 26, borderRadius: "50%", flexShrink: 0,
            bgcolor: "primary.main", color: "#fff",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontWeight: 800, fontSize: 13,
          }}>
            {step}
          </Box>
        )}
        <Box flexGrow={1} minWidth={0}>
          <Typography variant="subtitle2" fontWeight={800}>{title}</Typography>
          {subtitle && (
            <Typography variant="caption" color="text.secondary">{subtitle}</Typography>
          )}
        </Box>
        {action}
      </Stack>
      <Box sx={{ p: 2 }}>{children}</Box>
    </Paper>
  );
}

/** نوار دکمه‌های فرم — انتهای دیالوگ/صفحه */
export function FormActions({ children }: { children: ReactNode }) {
  return (
    <Stack direction="row" spacing={1.5} justifyContent="flex-end" flexWrap="wrap" useFlexGap>
      {children}
    </Stack>
  );
}

/** حالت خالی یکدست برای جدول‌ها و لیست‌ها */
export function EmptyState({ title, desc, action }: { title: string; desc?: string; action?: ReactNode }) {
  return (
    <Stack alignItems="center" spacing={1} sx={{ py: 5, textAlign: "center" }}>
      <InboxRoundedIcon sx={{ fontSize: 44, color: "#cbb7bc" }} />
      <Typography variant="subtitle2" fontWeight={700}>{title}</Typography>
      {desc && (
        <Typography variant="caption" color="text.secondary" sx={{ maxWidth: 420 }}>
          {desc}
        </Typography>
      )}
      {action}
    </Stack>
  );
}

export interface OptionRow { label: string; score: number }

/** ویرایشگر گزینه‌های سؤال پرسشنامه — هر گزینه یک ردیف با برچسب + امتیاز (به‌جای متن خام «برچسب: امتیاز») */
export function OptionsEditor({
  options, onChange, scales, error,
}: {
  options: OptionRow[];
  onChange: (rows: OptionRow[]) => void;
  scales?: string[];
  error?: string | null;
}) {
  const update = (i: number, patch: Partial<OptionRow>) =>
    onChange(options.map((o, idx) => (idx === i ? { ...o, ...patch } : o)));

  return (
    <Stack spacing={1}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Typography variant="caption" color="text.secondary" fontWeight={700}>
          گزینه‌ها و امتیاز هر گزینه
        </Typography>
        {scales && scales.length > 0 && (
          <Chip size="small" variant="outlined" sx={{ height: 20, fontSize: 10.5 }}
            label={`مقیاس پیشنهادی: ${scales.join(" / ")}`} />
        )}
      </Stack>
      {options.map((o, i) => (
        <Stack key={i} direction="row" spacing={1} alignItems="center">
          <Box sx={{ width: 26, height: 26, borderRadius: 1, bgcolor: "#faf3f4", color: "primary.main",
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 800, flexShrink: 0 }}>
            {i + 1}
          </Box>
          <TextField
            fullWidth
            size="small"
            placeholder={`متن گزینه ${i + 1}`}
            value={o.label}
            onChange={(e) => update(i, { label: e.target.value })}
          />
          <TextField
            size="small"
            type="number"
            sx={{ width: 96, flexShrink: 0 }}
            label="امتیاز"
            value={String(o.score)}
            onChange={(e) => update(i, { score: Number(e.target.value) || 0 })}
            inputProps={{ min: 0, style: { textAlign: "center" } }}
          />
          <IconButton size="small" color="error"
            disabled={options.length <= 2}
            onClick={() => onChange(options.filter((_, idx) => idx !== i))}>
            <DeleteOutlineRoundedIcon fontSize="small" />
          </IconButton>
        </Stack>
      ))}
      {error && <Typography variant="caption" color="error">{error}</Typography>}
      <Button
        size="small"
        startIcon={<AddCircleOutlineRoundedIcon />}
        onClick={() => onChange([...options, { label: "", score: options.length }])}
        sx={{ alignSelf: "flex-start" }}
      >
        افزودن گزینه
      </Button>
    </Stack>
  );
}
