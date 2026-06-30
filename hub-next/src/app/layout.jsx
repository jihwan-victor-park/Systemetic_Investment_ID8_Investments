import "./globals.css";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

export const metadata = {
  title: { default: "ID8 AI Intelligence", template: "%s · ID8 AI Intelligence" },
  description: "Ambitious ideas, made legible.",
  icons: { icon: "/img/logo_charcoal.png" },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        {children}
        <Footer />
      </body>
    </html>
  );
}
