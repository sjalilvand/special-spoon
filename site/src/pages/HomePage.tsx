import { Box } from "@mui/material";
import About from "../components/About";
import ConsultForm from "../components/ConsultForm";
import Counselors from "../components/Counselors";
import Footer from "../components/Footer";
import Header from "../components/Header";
import Hero from "../components/Hero";
import Services from "../components/Services";

export default function HomePage() {
  return (
    <Box>
      <Header />
      <Hero />
      <Services />
      <Counselors />
      <About />
      <ConsultForm />
      <Footer />
    </Box>
  );
}
