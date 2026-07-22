import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import JobsTray from '@/components/JobsTray';
import { JobsProvider } from '@/context/JobsContext';
import { auth } from '@/auth';

// Every route except the Growth Opportunities Fund I overview lives inside
// this group -- that page renders its own header/footer from the LP fund
// overview export and deliberately opts out of the hub's chrome entirely
// (see the sibling, non-grouped investors/materials/fund-overview route and
// the bare root layout.jsx).
export default async function HubLayout({ children }) {
  // Only internal users trigger/see screening jobs -- fetched here (a Server
  // Component) rather than via a client useSession() hook, since this app
  // has no SessionProvider mounted anywhere and every other page already
  // gets its session this way.
  const session = await auth();
  const isInternal = session?.user?.role === 'internal';

  return (
    <JobsProvider enabled={isInternal}>
      <Navbar isSignedIn={!!session?.user} />
      {children}
      <Footer />
      <JobsTray />
    </JobsProvider>
  );
}
