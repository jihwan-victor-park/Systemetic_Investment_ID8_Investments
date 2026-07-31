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
// filter, PortfolioTable's "Add...") ever offers it as a
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

// Additive tags (2026-07-28) -- independent of `stage`, which stays the one
// field a company's "primary" home resolves from (basePath lookups, the
// default StageMultiSelect value, etc). A company can ALSO carry any of
// these and show up in that tab too, on top of wherever `stage` already has
// it -- e.g. a company sitting in Pipeline as its real working stage that
// also clears the Stage 1 gate shows up on Qualified Deals too, or a Series
// B company being watched for its next round shows up on Radar (hot/cold,
// see radar_state.py) while its real stage stays wherever it actually is.
//
// Originally scoped to just ['qualified', 'radar'] (2026-07-28); widened to
// every PUBLIC_STAGES value (Oscar, 2026-07-30: "make sure the stage column
// is a multiselect, so that a deal can be in more than one stage") so
// StageMultiSelect can represent full multi-stage membership through this
// same additive mechanism rather than a separate data model -- see that
// component's own docstring for how it reconciles `stage` (still singular)
// with this array into one checked set. `qualified`/`radar` stay the only
// two that get auto-added server-side; the rest (watchlist/pipeline/
// invested) are hand-only, same as `stage` itself always was.
export const TAGS = PUBLIC_STAGES;

export const TAG_LABELS = STAGE_LABELS;
