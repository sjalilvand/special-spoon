import { Box } from "@mui/material";
import About from "../components/About";
import Academy from "../components/Academy";
import Articles from "../components/Articles";
import BookingSteps from "../components/BookingSteps";
import ConsultForm from "../components/ConsultForm";
import Counselors from "../components/Counselors";
import CtaBand from "../components/CtaBand";
import Faq from "../components/Faq";
import Features from "../components/Features";
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
      <Features />
      <Stats />
      <BookingSteps />
      <Counselors />
      <Academy />
      <About />
      <Articles />
      <Testimonials />
      <Faq />
      <CtaBand />
      <ConsultForm />
      <Footer />
    </Box>
  );
}
