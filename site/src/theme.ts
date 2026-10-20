import { createTheme } from "@mui/material/styles";

// پالت «رز» — بازطراحی ۱۴۰۴: رز عمیق + آلوی گرم + کرم مایل به گلبهی (RTL فارسی)
const theme = createTheme({
  direction: "rtl",
  typography: {
    fontFamily: '"Vazirmatn", Tahoma, sans-serif',
    h2: { fontWeight: 800, lineHeight: 1.35 },
    h3: { fontWeight: 800, lineHeight: 1.4 },
    button: { textTransform: "none" as const },
  },
  palette: {
    primary: { main: "#a83a54", dark: "#7c2740", light: "#d06b80" },
    secondary: { main: "#5c4a6e", light: "#8a76a0" },
    background: { default: "#fbf7f4", paper: "#ffffff" },
    text: { primary: "#2e2228", secondary: "#7a6a72" },
  },
  shape: { borderRadius: 16 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 99, fontWeight: 700, boxShadow: "none" },
        containedPrimary: {
          background: "linear-gradient(135deg,#b34460 0%,#8a2f47 100%)",
          "&:hover": { background: "linear-gradient(135deg,#a83a54 0%,#7c2740 100%)", boxShadow: "0 10px 24px rgba(168,58,84,.28)" },
        },
      },
    },
    MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
    MuiCard: { styleOverrides: { root: { borderRadius: 18 } } },
  },
});

export default theme;
