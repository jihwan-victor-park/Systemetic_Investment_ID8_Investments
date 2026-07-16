import './globals.css';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import JobsTray from '@/components/JobsTray';
import { JobsProvider } from '@/context/JobsContext';
import { auth } from '@/auth';

export const metadata = {
  title: { default: 'ID8 AI Intelligence', template: '%s · ID8 AI Intelligence' },
  description: 'Ambitious ideas, made legible.',
  icons: { icon: '/img/favicon.png' },
};

export default async function RootLayout({ children }) {
  // Only internal users trigger/see screening jobs -- fetched here (a Server
  // Component) rather than via a client useSession() hook, since this app
  // has no SessionProvider mounted anywhere and every other page already
  // gets its session this way.
  const session = await auth();
  const isInternal = session?.user?.role === 'internal';

  return (
    <html lang="en">
      <body>
        <JobsProvider enabled={isInternal}>
          <Navbar />
          {children}
          <Footer />
          <JobsTray />
        </JobsProvider>
      </body>
    </html>
  );
}
