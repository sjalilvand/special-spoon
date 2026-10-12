import { Box } from "@mui/material";
import About from "../components/About";
import ConsultForm from "../components/ConsultForm";
import Counselors from "../components/Counselors";
import CtaBand from "../components/CtaBand";
import Footer from "../components/Footer";
import Header from "../components/Header";
import Hero from "../components/Hero";
import Services from "../components/Services";
import Stats from "../components/Stats";
import Testimonials from "../components/Testimonials";

export default function HomePage() {
  return (
    <Box>
      <Header />
      <Hero />
      <Services />
      <Stats />
      <Counselors />
      <About />
      <Testimonials />
      <CtaBand />
      <ConsultForm />
      <Footer />
    </Box>
  );
}
