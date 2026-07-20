// Shared by both server code (lib/companies.js validation) and client
// components (StageSelect's dropdown) -- deliberately has no 'server-only'
// import and no Firestore dependency, so it's safe in either bundle.
export const STAGES = ['new', 'watchlist', 'pipeline', 'qualified'];

export const STAGE_LABELS = {
  new: 'New Deals',
  watchlist: 'Watchlist',
  pipeline: 'Pipeline',
  qualified: 'Qualified Deals',
};

// Where a company's own screen/report page lives, by its current stage --
// shared by Hot Deals and any other view that links out to "the real
// company page" rather than a VC-portfolio-only drill-in.
export const STAGE_BASEPATH = {
  new: '/docs/new-deals',
  watchlist: '/docs/watchlist',
  pipeline: '/docs/pipeline',
  qualified: '/docs/qualified-deals',
};
