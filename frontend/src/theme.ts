import { createTheme } from "@mui/material/styles";

// پالت رزی — هماهنگ با سایت عمومی (فاز ۱۶) — فاز ۴۷: عمق‌بخشی UI فرم‌ها
const theme = createTheme({
  direction: "rtl",
  typography: {
    fontFamily: '"Vazirmatn", Tahoma, sans-serif',
    button: { textTransform: "none" },
    h6: { fontWeight: 800 },
  },
  palette: {
    primary: { main: "#b04a5a" },
    secondary: { main: "#7a5c8a" },
    background: { default: "#fffafb", paper: "#ffffff" },
    success: { main: "#2e7d32" },
    info: { main: "#1565c0" },
  },
  shape: { borderRadius: 10 },
  components: {
    MuiButton: {
      styleOverrides: { root: { borderRadius: 99, fontWeight: 700 } },
    },
    MuiAppBar: {
      styleOverrides: { root: { background: "linear-gradient(135deg,#b04a5a 0%,#8a3342 100%)" } },
    },
    // فاز ۴۷ - فرم‌ها: فیلدهای هم‌اندازه، پس‌زمینه روشن و فوکوس واضح
    MuiTextField: {
      defaultProps: { size: "small" },
      styleOverrides: {
        root: {
          "& .MuiOutlinedInput-root": {
            backgroundColor: "#fff",
            "& fieldset": { borderColor: "#e3d5d8" },
            "&:hover fieldset": { borderColor: "#c39aa2" },
            "&.Mui-focused fieldset": { borderWidth: 1.5 },
          },
        },
      },
    },
    MuiInputLabel: {
      styleOverrides: { root: { fontSize: 14 } },
    },
    MuiFormHelperText: {
      styleOverrides: { root: { fontSize: 12, mx: 0 } },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: "none" },
        outlined: { borderColor: "#ece2e4" },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 800, fontSize: 13,
          backgroundColor: "#faf3f4", color: "#5d3a41",
          whiteSpace: "nowrap",
        },
        root: { fontSize: 13 },
      },
    },
    MuiDialogTitle: {
      styleOverrides: {
        root: {
          fontWeight: 800, fontSize: 17,
          borderBottom: "1px solid #f0e4e6", pb: 1.5,
        },
      },
    },
    MuiDialogActions: {
      styleOverrides: { root: { borderTop: "1px solid #f0e4e6", py: 1.5 } },
    },
    MuiTooltip: {
      defaultProps: { arrow: true },
    },
    MuiChip: {
      styleOverrides: { root: { fontWeight: 600 } },
    },
    MuiAlert: {
      styleOverrides: { root: { fontSize: 13.5, borderRadius: 10 } },
    },
  },
});

export default theme;
