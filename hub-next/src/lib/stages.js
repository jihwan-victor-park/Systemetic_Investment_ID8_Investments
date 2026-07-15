// Shared by both server code (lib/companies.js validation) and client
// components (StageSelect's dropdown) -- deliberately has no 'server-only'
// import and no Firestore dependency, so it's safe in either bundle.
export const STAGES = ['watchlist', 'pipeline', 'qualified'];

export const STAGE_LABELS = {
  watchlist: 'Watchlist',
  pipeline: 'Pipeline',
  qualified: 'Qualified Deals',
};
