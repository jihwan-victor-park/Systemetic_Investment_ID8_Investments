// Shared by both server code (lib/companies.js validation) and client
// components (StageSelect's dropdown) -- deliberately has no 'server-only'
// import and no Firestore dependency, so it's safe in either bundle.
//
// 'radar' is a real stage, not a derived filter -- Attio tags Series
// A-or-earlier deals sourced from a Top 10 VC with its own "Radar" stage,
// and deal_intelligence/config.py's ATTIO_STAGE_MAP forwards that onto this
// bucket directly when the data pipelines run. Until then, it's also just
// another option on every StageSelect dropdown -- an internal user can move
// a company here by hand exactly like any other stage.
export const STAGES = ['new', 'watchlist', 'pipeline', 'qualified', 'radar'];

export const STAGE_LABELS = {
  new: 'New Deals',
  watchlist: 'Watchlist',
  pipeline: 'Pipeline',
  qualified: 'Qualified Deals',
  radar: 'Radar',
};

// Where a company's own screen/report page lives, by its current stage --
// shared by Hot Deals and any other view that links out to "the real
// company page" rather than a VC-portfolio-only drill-in.
export const STAGE_BASEPATH = {
  new: '/docs/new-deals',
  watchlist: '/docs/watchlist',
  pipeline: '/docs/pipeline',
  qualified: '/docs/qualified-deals',
  radar: '/docs/radar',
};
