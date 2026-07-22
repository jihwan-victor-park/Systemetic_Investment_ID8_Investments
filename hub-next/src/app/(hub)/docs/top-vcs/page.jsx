import { redirect } from 'next/navigation';

// The Top 10 VCs tab was folded into the merged VCs tab (Partner VCs + Tier
// 1 VCs). Keeping this route alive as a redirect so old bookmarks/links
// still land somewhere real.
export default function TopVCsPage() {
  redirect('/docs/vcs');
}
