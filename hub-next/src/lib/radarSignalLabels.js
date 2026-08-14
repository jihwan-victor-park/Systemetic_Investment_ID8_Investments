// Human-readable labels for radar_market_heat.py's WEIGHTS keys -- the
// Firestore doc only has the camelCase key + weight/raw/contribution per
// signal (see that module's _entry()), so the display name lives here,
// not duplicated from Python. Matches the original Heat Score Signal
// Framework spreadsheet's own row names. Shared by RadarHeatBreakdown.jsx
// (the full company-page breakdown) and RadarHeatPopover.jsx (the Radar
// table's click-to-open card) so both render the same signal names.
export const SIGNAL_LABELS = {
  raiseProbability: 'Raise Probability',
  industryGrowth: 'Industry Growth',
  momEmployeeGrowth: 'MoM Employee Growth',
  jobPostingVelocity: 'Job Posting Velocity',
  crunchbaseGrowthScore: 'Growth Momentum',
  stepUp: 'Step-Up',
  yoyRevenueGrowth: 'YoY Revenue/ARR Growth',
  newsVolume: 'News Volume',
  websiteVisitsGrowth: 'Website Visits Growth',
  googleTrendsSearchInterest: 'Google Trends Search Interest',
  redditActivity: 'Reddit Activity',
  crunchbaseHeatScore: 'Public Attention & Heat',
  crunchbaseSurgeScore: 'Momentum Surge',
  tier1InvestorCount: 'Tier 1 Investor Count',
};
