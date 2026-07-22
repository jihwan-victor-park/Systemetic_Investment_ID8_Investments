import FundOnePagerClient from './FundOnePagerClient';

export const metadata = {
  title: 'Growth Opportunities Fund I',
  description: 'Confidential LP one-pager for ID8 Growth Opportunities Fund I.',
};

// Deliberately nested under /investors/research -- auth.config.js's
// `authorized` callback hard-redirects an approved 'investor'-role user away
// from anything outside that path prefix, so this had to live inside it to
// actually be reachable by them (not just by 'internal' accounts). This path
// is also carved out of middleware.js's matcher, so it's the one page under
// /investors/research that's reachable with no session at all.
//
// Deliberately NOT inside the app/(hub) route group -- every other page gets
// the hub's own Navbar/Footer from (hub)/layout.jsx, but this one is a
// verbatim LP one-pager export with its own header and footer, so it opts
// out entirely and gets only the bare root layout.jsx.
// See FundOnePagerClient for why the content renders via Shadow DOM.
export default function FundOnePagerPage() {
  return <FundOnePagerClient />;
}
