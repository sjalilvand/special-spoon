import { createTheme } from "@mui/material/styles";

// پالت رزی الهام‌گرفته از قالب کلینیک — RTL فارسی
const theme = createTheme({
  direction: "rtl",
  typography: { fontFamily: '"Vazirmatn", Tahoma, sans-serif' },
  palette: {
    primary: { main: "#b04a5a" },
    secondary: { main: "#7a5c8a" },
    background: { default: "#fffafb", paper: "#ffffff" },
  },
  shape: { borderRadius: 12 },
  components: {
    MuiButton: { styleOverrides: { root: { borderRadius: 99, fontWeight: 700 } } },
  },
});

export default theme;
