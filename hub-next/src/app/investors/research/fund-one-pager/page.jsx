import FundOnePagerClient from './FundOnePagerClient';

export const metadata = {
  title: 'Growth Opportunities Fund I',
  description: 'Confidential LP one-pager for ID8 Growth Opportunities Fund I.',
};

// Deliberately nested under /investors/research -- auth.config.js's
// `authorized` callback hard-redirects an approved 'investor'-role user away
// from anything outside that path prefix, so this had to live inside it to
// actually be reachable by them (not just by 'internal' accounts). Unlike
// /investors itself, nothing under here is excluded from the sign-in gate.
// See FundOnePagerClient for why the content renders via Shadow DOM.
export default function FundOnePagerPage() {
  return <FundOnePagerClient />;
}
