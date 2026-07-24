// Stage 0 Portfolio Fit decision tiers (deal_intelligence/rubric_portfolio.py
// DECISION_TIERS) -- shared between the VC-portfolio drill-in page and the
// real company profile page (CompanyDetailPage), which both need to render
// the same "here's the Stage 0 read" summary when there's no live Stage 1
// screen yet. TIER_BADGE_CLASS maps onto the pre-existing house
// `badge--gate/borderline/below` classes (globals.css) -- no bespoke colors.
export const TIER_LABEL = {
  track_priority: 'Track — priority', track: 'Track', monitor: 'Monitor',
  too_early: 'Too early', drop: 'Drop', error: 'Scoring error',
};

export const TIER_BADGE_CLASS = {
  track_priority: 'badge--gate', track: 'badge--gate',
  monitor: 'badge--borderline', too_early: 'badge--borderline',
  drop: 'badge--below',
};
