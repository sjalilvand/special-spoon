import { Alert, Box, Button, Chip, CircularProgress, Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { errDetail } from "../api/client";
import { FileItem, downloadFileWithTicket, fetchCaseFiles, uploadCaseFile } from "../api/files";
import { formatJalali } from "../utils/jalali";

const SCAN_META: Record<string, { label: string; color: "success" | "warning" | "error" | "info" }> = {
  clean: { label: "سالم (اسکن شد)", color: "success" },
  pending: { label: "در انتظار اسکن", color: "info" },
  quarantined: { label: "قرنطینه", color: "error" },
  failed: { label: "اسکن ناموفق", color: "warning" },
};

const CONTEXT_LABEL: Record<string, string> = {
  case_document: "سند پرونده",
  consent: "رضایت‌نامه",
  intake: "پذیرش",
  report: "گزارش",
};

function fmtSize(n: number): string {
  if (n < 1024) return `${n} بایت`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} کیلوبایت`;
  return `${(n / 1024 / 1024).toFixed(1)} مگابایت`;
}

/** بخش فایل‌های پرونده - B39 سند: آپلود امن + وضعیت اسکن + دانلود با بلیت کوتاه‌مدت */
export default function CaseFiles({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["case-files", caseId],
    queryFn: () => fetchCaseFiles(caseId),
  });

  const uploadMut = useMutation({
    mutationFn: (f: File) => uploadCaseFile(caseId, f),
    onSuccess: () => { setErr(null); qc.invalidateQueries({ queryKey: ["case-files", caseId] }); },
    onError: (e) => setErr(errDetail(e)),
  });

  const onPick = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    uploadMut.mutate(files[0]);
    if (inputRef.current) inputRef.current.value = "";
  };

  const items: FileItem[] = data ?? [];

  return (
    <Paper sx={{ p: 2 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 1, flexWrap: "wrap" }}>
        <Typography variant="subtitle1" fontWeight={700}>فایل‌های پرونده</Typography>
        <Box flexGrow={1} />
        <input
          ref={inputRef} type="file" hidden
          accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.xlsx,.pptx,.txt,.csv"
          onChange={(e) => onPick(e.target.files)}
        />
        <Button
          size="small" variant="contained" disabled={uploadMut.isPending}
          onClick={() => inputRef.current?.click()}
        >
          {uploadMut.isPending ? <CircularProgress size={16} color="inherit" /> : "بارگذاری فایل"}
        </Button>
      </Box>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
        سقف حجم ۱۰ مگابایت — انواع مجاز: PDF، تصویر، Word، Excel، PowerPoint، متن — فایل مشکوک قرنطینه می‌شود (B39)
      </Typography>

      {err && <Alert severity="error" sx={{ mb: 1 }}>{err}</Alert>}

      {isLoading ? (
        <Box sx={{ p: 3, textAlign: "center" }}><CircularProgress size={22} /></Box>
      ) : items.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: "center" }}>
          فایلی بارگذاری نشده است
        </Typography>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>نام فایل</TableCell>
              <TableCell>زمینه</TableCell>
              <TableCell>حجم</TableCell>
              <TableCell>اسکن</TableCell>
              <TableCell>تاریخ</TableCell>
              <TableCell align="left">دانلود</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((f) => {
              const scan = SCAN_META[f.scan_status] ?? { label: f.scan_status, color: "info" as const };
              const quarantined = f.scan_status === "quarantined";
              return (
                <TableRow key={f.id}>
                  <TableCell>
                    <Typography variant="body2">{f.original_name}</Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ direction: "ltr", display: "inline-block" }}>
                      sha256: {f.sha256.slice(0, 12)}…
                    </Typography>
                  </TableCell>
                  <TableCell>{CONTEXT_LABEL[f.context] ?? f.context}</TableCell>
                  <TableCell sx={{ whiteSpace: "nowrap" }}>{fmtSize(f.size_bytes)}</TableCell>
                  <TableCell>
                    <Chip size="small" color={scan.color} label={scan.label} variant={quarantined ? "filled" : "outlined"} />
                  </TableCell>
                  <TableCell sx={{ whiteSpace: "nowrap" }}>
                    {f.created_at ? formatJalali(f.created_at) : "—"}
                  </TableCell>
                  <TableCell align="left">
                    <Button
                      size="small" disabled={quarantined}
                      onClick={() => downloadFileWithTicket(f.id).catch((e) => setErr(errDetail(e)))}
                    >
                      دانلود
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </Paper>
  );
}
