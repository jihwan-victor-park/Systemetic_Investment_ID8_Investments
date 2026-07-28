import './globals.css';

export const metadata = {
  title: { default: 'ID8 AI Intelligence', template: '%s · ID8 AI Intelligence' },
  description: 'Ambitious ideas, made legible.',
  icons: { icon: '/img/favicon.png' },
};

// Deliberately bare -- the hub's own chrome (Navbar, Footer, JobsTray) lives
// in (hub)/layout.jsx instead, so the Growth Opportunities Fund I one-pager
// (the one route not inside that group) can render with none of it: just its
// own header/footer from the LP one-pager export, full-bleed.
export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
