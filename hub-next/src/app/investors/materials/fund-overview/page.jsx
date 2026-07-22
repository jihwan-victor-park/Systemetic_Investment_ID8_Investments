import FundOverviewClient from './FundOverviewClient';

export const metadata = {
  title: 'Growth Opportunities Fund I',
  description: 'Confidential LP fund overview for ID8 Growth Opportunities Fund I.',
};

// Lives under /investors/materials rather than /investors/research -- that
// prefix is carved out of middleware.js's matcher, so it's reachable with no
// session at all. It's ALSO allowlisted (alongside /investors/research) in
// auth.config.js's `authorized` callback, which otherwise hard-redirects an
// approved 'investor'-role user away from anything outside those two path
// prefixes -- so this stays reachable by them even if the middleware
// carve-out is ever removed (not just by 'internal' accounts).
//
// Deliberately NOT inside the app/(hub) route group -- every other page gets
// the hub's own Navbar/Footer from (hub)/layout.jsx, but this one is a
// verbatim LP fund overview export with its own header and footer, so it
// opts out entirely and gets only the bare root layout.jsx.
// See FundOverviewClient for why the content renders via Shadow DOM.
export default function FundOverviewPage() {
  return <FundOverviewClient />;
}
