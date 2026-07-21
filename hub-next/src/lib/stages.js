// Shared by both server code (lib/companies.js validation) and client
// components (StageSelect's dropdown) -- deliberately has no 'server-only'
// import and no Firestore dependency, so it's safe in either bundle.
//
// 'radar' is a real stage, not a derived filter -- Attio tags Series
// A-or-earlier deals sourced from a Top 10 VC with its own "Radar" stage,
// and deal_intelligence/config.py's ATTIO_STAGE_MAP forwards that onto this
// bucket directly when the data pipelines run. Same for 'invested' (an
// Attio deal explicitly marked Invested maps straight here too).
//
// 'new' is NOT a real pipeline stage -- it's the internal holding bucket for
// companies the bulk Attio import couldn't map to any of the above (no Attio
// stage recorded at all). It has no public tab (there used to be a "New
// Deals" tab; it was dropped because most of what landed there turned out to
// already have a real Attio stage and was just mis-bucketed by an older
// version of push_company_from_attio -- see
// deal_intelligence.firestore_push.backfill_attio_stages). What's left after
// that backfill is genuinely untriaged and surfaces in the Admin page's
// "Needs Triage" table instead, where StageSelect assigns it a real stage by
// hand. It stays in STAGES (so existing 'new' docs still validate/read
// correctly) but is excluded from PUBLIC_STAGES, so no user-facing dropdown
// (StageSelect's other rows, TrackNewRoundForm, HubSearchPanel's stage
// filter, PortfolioTable's "Add to pipeline") ever offers it as a
// destination -- moving a company into 'new' only ever happens via the Attio
// import path, never by hand.
export const STAGES = ['new', 'watchlist', 'pipeline', 'qualified', 'radar', 'invested'];

// The stages a user can actively pick as a destination. Excludes 'new' --
// see the STAGES comment above.
export const PUBLIC_STAGES = STAGES.filter((s) => s !== 'new');

export const STAGE_LABELS = {
  new: 'Needs Triage',
  watchlist: 'Watchlist',
  pipeline: 'Deal Pipeline',
  qualified: 'Qualified Deals',
  radar: 'Radar',
  invested: 'Invested',
};

// Where a company's own screen/report page lives, by its current stage --
// shared by Hot Deals and any other view that links out to "the real
// company page" rather than a VC-portfolio-only drill-in. 'new' still
// resolves to a real (unlisted) route -- see the STAGES comment -- so a
// Needs-Triage company's "View screen" link keeps working from Admin.
export const STAGE_BASEPATH = {
  new: '/docs/new-deals',
  watchlist: '/docs/watchlist',
  pipeline: '/docs/pipeline',
  qualified: '/docs/qualified-deals',
  radar: '/docs/radar',
  invested: '/docs/invested',
};
