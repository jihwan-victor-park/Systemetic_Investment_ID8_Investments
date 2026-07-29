"""Radar's syndicate/access scoring (RADAR_SIGNAL_ENGINE.md §7's
access_multiplier), kept as a SEPARATE gate from the timing hazard --
Oscar, 2026-07-29: blending timing and access into one number reintroduces
the exact ambiguity radar_hazard.py's kernel model was built to escape. A
company can score high on timing because it's actually about to raise; a
company can score high on access because ID8 has a real route in. Those
are different questions with different failure modes, and conflating them
is the same mistake the original flat additive score made. "Hot Radar" is
the INTERSECTION of both (radar_state.py's hot = heatPoints >= threshold
AND access.accessPass), not a weighted sum of either.

Two tiers this pass, both from data already resolved elsewhere in this
pipeline -- no new investor-name text parsing, which would be a fragile
way to reach the same answer for what free-text "Lead Investors" fields
already give more reliably via portfolio-membership matching:
  - "co-invest": one of ID8's own tracked Partner VCs (hub-next's
    `partnerVCs` collection -- an active relationship, the doc's strongest
    tier, "a firm we co-invest alongside") is already on this company's
    cap table.
  - "institutional": a Top 10 VC is on the cap table -- radar_mandate.py's
    own S3 resolution (`tier1Firms`/`top10VCFlag`), REUSED here, not
    recomputed.
  - "none": neither. Rare in practice -- the mandate's S3 gate already
    requires some Tier 1/Top10VC presence to reach Radar at all, so this
    mostly only fires for a top10VC-flag-only pass with zero portfolio-
    index name matches on either list.

The doc's third tier ("a warm contact in Attio") isn't built this pass --
that needs Attio contact-level resolution this pipeline doesn't do yet.
"""


def build_partner_index(partner_vcs):
    """Mirrors radar_mandate.build_tier1_index()'s shape exactly, off
    hub-next's `partnerVCs` collection instead of `topVCs` -- each doc
    {name, portfolio: [{company, ...}], ...} (note: `portfolio`, not
    `deals` -- partnerVCs' own field name, see hub-next's lib/
    partnerVCs.js). Returns {company_name.lower().strip(): [firm_name,
    ...]}. Built once per run (backfill/daily scan job/bulk Attio import),
    not per company -- same O(1)-lookup reasoning as build_tier1_index."""
    index = {}
    for firm in partner_vcs or []:
        firm_name = firm.get("name")
        if not firm_name:
            continue
        seen = set()
        for entry in firm.get("portfolio") or []:
            name_lc = (entry.get("company") or "").strip().lower()
            if not name_lc or name_lc in seen:
                continue
            seen.add(name_lc)
            index.setdefault(name_lc, []).append(firm_name)
    return index


def resolve_access(company_name, tier1_firms, top10_vc_flag, partner_index):
    """company_name/tier1_firms/top10_vc_flag: reuses radar_mandate.
    screen()'s own S3 resolution (mandate['tier1Firms']/
    mandate['top10VCFlag']) rather than re-deriving it. `partner_index`:
    build_partner_index()'s output.

    Returns {"level": "co-invest"|"institutional"|"none",
    "coInvestFirms": [...], "tier1Firms": [...], "accessPass": bool} --
    radar.access's shape."""
    name_lc = (company_name or "").strip().lower()
    co_invest_firms = list(partner_index.get(name_lc, [])) if name_lc else []
    if co_invest_firms:
        level = "co-invest"
    elif tier1_firms or top10_vc_flag:
        level = "institutional"
    else:
        level = "none"
    return {
        "level": level,
        "coInvestFirms": co_invest_firms,
        "tier1Firms": list(tier1_firms or []),
        "accessPass": level != "none",
    }
