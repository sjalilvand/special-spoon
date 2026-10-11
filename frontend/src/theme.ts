import { createTheme } from "@mui/material/styles";

// طراحی فارسی، راست‌به‌چپ و واکنش‌گرا (بند ۱۰ سند)
const theme = createTheme({
  direction: "rtl",
  typography: {
    fontFamily: '"Vazirmatn", Tahoma, Arial, sans-serif',
  },
  palette: {
    primary: { main: "#5b4b8a" },
    secondary: { main: "#0f766e" },
  },
});

export default theme;
