import { createTheme } from "@mui/material/styles";

// پالت رزی — هماهنگ با سایت عمومی (فاز ۱۶)
const theme = createTheme({
  direction: "rtl",
  typography: { fontFamily: '"Vazirmatn", Tahoma, sans-serif' },
  palette: {
    primary: { main: "#b04a5a" },
    secondary: { main: "#7a5c8a" },
    background: { default: "#fffafb", paper: "#ffffff" },
  },
  shape: { borderRadius: 10 },
  components: {
    MuiButton: { styleOverrides: { root: { borderRadius: 99, fontWeight: 700 } } },
    MuiAppBar: { styleOverrides: { root: { background: "linear-gradient(135deg,#b04a5a 0%,#8a3342 100%)" } } },
  },
});

export default theme;
