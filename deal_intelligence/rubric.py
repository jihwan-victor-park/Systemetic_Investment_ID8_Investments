"""The scoring rubric (v4, July 2026).

All six dimensions -- Lead / Round Dynamics, Founder / Team Quality, AI
Score, Terms, Fundamentals, Return Potential -- sit at exact parity (weight
100/6 each, ~16.7%). Terms is a normal scored dimension now: it used to be
gate_only (weight 0, excluded from the average, and its own bottom anchor
was a hard-auto-pass trigger) but that special status is gone. A bad Terms
score now just drags the average like every other dimension.

Every dimension is broken into a FIXED, standardized set of subcategories
(see SUBCATEGORIES below) -- the same items, same titles, for every deal.
Each subcategory carries its own 1-4 anchor rubric. A dimension's score is
not an independent LLM judgment call; it is computed as the mean of its
subcategories' scores (see dimension_score()). This is the single source of
truth for that structure -- prompts/rubric.md's per-dimension "Subcategory
checklist" sections are rendered from SUBCATEGORIES at rubric_text() time
(look for the `<!-- SUBCATEGORIES: <key> -->` markers), so the anchor text
never has to be hand-duplicated between the prompt and the code.

Hard-auto-pass vs. soft-pass logic (e.g. undisclosed revenue capping
Fundamentals at 2 rather than 1, or "no AI component" auto-failing a deal)
lives entirely in the prompt text (prompts/rubric.md, prompts/stage1_fit.md),
not here -- the model reports hard_auto_pass explicitly rather than code
inferring it from raw scores, so a single mis-scored dimension can't silently
auto-kill an otherwise strong deal. Terms no longer contributes any
hard-auto-pass trigger of its own.
"""
import os
import re

_PROMPTS = os.path.join(os.path.dirname(__file__), "prompts")

# Each dimension: key, label, and its fixed subcategory list. Each
# subcategory: key, label (Oscar's exact standardized title -- identical
# across every deal), and anchors (the fixed 1-4 rubric for that item).
PARAMS = [
    {
        "key": "lead_round_dynamics",
        "label": "Lead / Round Dynamics",
        "subcategories": [
            {"key": "lead_tier", "label": "Lead tier", "anchors": {
                1: "No credible institutional lead -- insider bridge, anonymous SPV, or a CVC/regional fund with no strategic relevance.",
                2: "Non-Tier-1 VC leading the round.",
                3: "Tier 1 VC (per the Tier 1 list) or a qualifying Domain-Strategic lead -- genuine category asymmetry, not a generic corporate CVC.",
                4: "Tier 1+ VC (per the Tier 1+ list) leading the round.",
            }},
            {"key": "new_vs_reup", "label": "New vs re-up", "anchors": {
                1: "Re-up claim taken at face value with no cap-table or prior-round corroboration -- unverifiable, treated as unconfirmed.",
                2: "Confirmed re-up -- an existing investor increasing its position, not new money.",
                3: "Re-up verified via cap table/prior-round disclosure, from a Tier 1+ firm, with strong stated conviction.",
                4: "Verified new money -- the lead is on the cap table for the first time, ID8's strongest backtested predictor of returns.",
            }},
            {"key": "stage_fit", "label": "Stage fit", "anchors": {
                1: "Pre-seed or Seed -- well outside mandate, no near-term path to Series B+.",
                2: "Series A -- out of mandate for now but on a plausible path to Series B; file to Watch List.",
                3: "Series B/C/D but the round has mixed characteristics (bridge-to-B, extension round) vs. a clean primary.",
                4: "Clean primary round at Series B, C, or D -- squarely in mandate.",
            }},
            {"key": "domain_strategic", "label": "Domain-strategic", "anchors": {
                1: "Lead claims domain relevance but is a generic corporate CVC or regional fund with no genuine category asymmetry.",
                2: "Lead is a traditional financial VC -- domain-strategic signal not applicable to this deal.",
                3: "Lead has adjacent domain relevance but the asymmetry is partial (e.g. a fintech-adjacent bank, not a direct incumbent).",
                4: "Lead is a large institutional player whose core business IS the company's market (NYSE/ICE-Polymarket precedent) -- genuine, direct asymmetry.",
            }},
            {"key": "lead_conviction", "label": "Lead conviction", "anchors": {
                1: "Deal sourced/led by a junior associate or scout check with no partner-level sponsorship visible.",
                2: "A named partner is involved but with no visible personal track record or reputational stake disclosed.",
                3: "The leading GP has a credible prior-fund track record and is the named partner driving the deal.",
                4: "The leading GP is personally/reputationally committed -- strong prior-fund performance, personal co-invest, or a bio establishing direct conviction.",
            }},
            {"key": "institutional_momentum", "label": "Institutional momentum", "anchors": {
                1: "Existing investors from prior rounds are confirmed NOT participating -- a negative signal, insiders passing.",
                2: "No visible signal either way on prior-round investor participation in this round.",
                3: "Some prior-round investors are following on, but participation is partial or unconfirmed beyond a press mention.",
                4: "Existing Tier-1 investors from prior rounds are confirmed following on alongside the new lead -- a distinct, corroborating signal.",
            }},
            {"key": "existing_tier_1", "label": "Existing Tier 1", "anchors": {
                1: "No Tier 1 or Tier 1+ investors anywhere on the pre-round cap table.",
                2: "Cap table history is unclear/unverifiable, or only lower-tier/angel investors are confirmed.",
                3: "At least one Tier 1 firm is confirmed on the pre-round cap table.",
                4: "Multiple Tier 1/Tier 1+ firms are confirmed on the pre-round cap table -- a strong pre-existing pedigree signal.",
            }},
            {"key": "timing_motivation", "label": "Timing/motivation", "anchors": {
                1: "Defensive raise -- runway extension, down-round pressure, or limited alternatives visible.",
                2: "Motivation is unclear or undisclosed; no evidence either of opportunistic strength or defensive need.",
                3: "Opportunistic raise with at least one credible alternative term sheet or investor reported.",
                4: "Clearly opportunistic -- positive inflection point, multiple credible term sheet options, company controlling the process.",
            }},
        ],
    },
    {
        "key": "founder_team_quality",
        "label": "Founder / Team Quality",
        "subcategories": [
            {"key": "prior_exit", "label": "Prior exit", "anchors": {
                1: "First-time founder(s) with no prior scaling or exit track record at all.",
                2: "Some operating experience but nothing scaled meaningfully (no $100M+ ARR company, no exit).",
                3: "First-time founder with elite pedigree (FAANG, top-tier academic, relevant domain leadership) but no exit yet.",
                4: "Serial founder with a meaningful prior exit or a company scaled to $100M+ ARR.",
            }},
            {"key": "domain_authority", "label": "Domain authority", "anchors": {
                1: "No prior experience in this market -- founders are entering a domain they've never operated in.",
                2: "Adjacent but not direct domain experience (a related market, not this exact one).",
                3: "Meaningful prior operating time in this exact market, though not in a senior/executive capacity.",
                4: "Deep domain authority -- years as a practitioner, executive, or technical lead in this exact market before founding.",
            }},
            {"key": "team_complement", "label": "Team complement", "anchors": {
                1: "Solo founder or a founding team with duplicated skillsets and no coverage of a critical function.",
                2: "Founding team has partial coverage but a visible, material gap (e.g. no technical co-founder for a deep-tech company).",
                3: "Founding team covers the critical functions with reasonable but not ideal complementarity.",
                4: "Clean technical/GTM/operational complementarity with no material coverage gap.",
            }},
            {"key": "recruiting_power", "label": "Recruiting power (as in team growth)", "anchors": {
                1: "Headcount flat or shrinking; visible attrition among early/senior hires.",
                2: "Headcount growth is slow or unverifiable from LinkedIn/public signal.",
                3: "Steady headcount growth with some credible senior hires.",
                4: "Strong LinkedIn headcount growth trend with notable senior hires and retention of early employees.",
            }},
            {"key": "public_presence", "label": "Public presence", "anchors": {
                1: "No public footprint at all for the founders -- cannot assess reputation.",
                2: "Minimal public presence; thin press, no conference/technical presence found.",
                3: "Regular press mentions or some conference/technical writing presence.",
                4: "Strong, consistent public presence -- press, conference talks, technical writing, or open-source contributions hard to fabricate.",
            }},
            {"key": "integrity", "label": "Integrity", "anchors": {
                1: "Verified negative history -- litigation, fraud allegations, regulatory action, or confirmed toxic-culture signals.",
                2: "Background is genuinely unverifiable after real search effort -- flag [unverified], a gap, not a red flag.",
                3: "Background verified with no red flags found, though the search surface was limited.",
                4: "Background thoroughly verified across multiple independent sources with no red flags found.",
            }},
        ],
    },
    {
        "key": "ai_score",
        "label": "AI Score",
        "subcategories": [
            {"key": "ownership_of_models", "label": "Ownership of models", "anchors": {
                1: "No proprietary model or fine-tune of any kind -- a thin wrapper calling a third-party foundation-model API with no differentiation.",
                2: "Some fine-tuning or prompt/pipeline engineering on top of a third-party model, but no owned architecture.",
                3: "A meaningfully customized or fine-tuned model with real engineering investment, though not a from-scratch architecture.",
                4: "Proprietary architecture, training pipeline, or deeply fine-tuned model that is defensible and hard to replicate with a foundation-model update.",
            }},
            {"key": "data_flywheel", "label": "Data flywheel / Recurssion", "anchors": {
                1: "No evidence usage data feeds back into the product at all.",
                2: "A plausible data flywheel is claimed but with no concrete evidence (no stated improvement cadence or proprietary dataset).",
                3: "Some concrete evidence of a data flywheel (a proprietary dataset or a stated retraining cycle), though the compounding effect isn't yet demonstrated.",
                4: "Strong, evidenced data flywheel -- usage data demonstrably compounds product quality over time via a proprietary dataset and an active retraining cycle.",
            }},
        ],
    },
    {
        "key": "terms",
        "label": "Terms",
        "subcategories": [
            {"key": "assume_good_absent_evidence", "label": "Just assume they are good (unless there's something public)", "anchors": {
                1: "Confirmed bad terms -- a recurring annual management fee (any amount), or carry >15% with an upfront fee >2%, or carry >20% regardless of fee.",
                2: "Some public evidence of elevated but not disqualifying terms -- carry 10-15%, upfront access fee at or below 2% (the Polymarket standard), or limited information rights/multi-layer SPV.",
                3: "Standard 0/0/10 terms confirmed, or no public evidence either way -- assume standard/good absent any adverse public signal.",
                4: "Better than standard -- carry below 10% with pro-rata confirmed, full information rights, clean single-layer SPV or direct co-invest, no upfront fee.",
            }},
        ],
    },
    {
        "key": "fundamentals",
        "label": "Fundamentals",
        "subcategories": [
            {"key": "revenue_growth", "label": "Revenue/growth", "anchors": {
                1: "Confirmed sub-$5M ARR and sub-40% YoY growth -- a real, disclosed weak number, not a data gap.",
                2: "No disclosed revenue/growth and no usable [ESTIMATED] triangulation exists, or an [ESTIMATED] figure lands below the $25M ARR / 70% growth bar.",
                3: "$25M+ ARR with >70% YoY growth, confirmed or [ESTIMATED] via triangulation.",
                4: "$50M+ ARR with 100%+ YoY growth, confirmed or [ESTIMATED] via triangulation.",
            }},
            {"key": "ndr", "label": "NDR", "anchors": {
                1: "Confirmed NDR below 100% -- shrinking accounts.",
                2: "NDR not disclosed and no usable estimate exists.",
                3: "NDR above 110%, confirmed or credibly estimated from comparable-stage peers.",
                4: "NDR above 130%, confirmed or credibly estimated from comparable-stage peers.",
            }},
            {"key": "margins_unit_econ", "label": "Margins/unit econ", "anchors": {
                1: "Confirmed LTV/CAC below 2x -- growth is value-destroying.",
                2: "Gross margin/unit economics not disclosed and no usable estimate exists.",
                3: "LTV/CAC above 3x with reasonable gross margin -- growth is value-creating.",
                4: "LTV/CAC above 5x with strong gross and contribution margin.",
            }},
            {"key": "burn_runway", "label": "Burn/runway", "anchors": {
                1: "Confirmed burn above 100% of revenue -- burning faster than it earns with no offsetting signal.",
                2: "Burn/runway not disclosed and no usable estimate exists.",
                3: "Burn below 50% of revenue with a credible runway at current spend.",
                4: "Burn below 20% of revenue -- strong capital discipline relative to revenue.",
            }},
            {"key": "customer_concentration", "label": "Customer concentration", "anchors": {
                1: "Confirmed whale-contract risk -- a single customer or a small handful account for the clear majority of revenue.",
                2: "Customer concentration not disclosed and cannot be estimated.",
                3: "Some concentration in the top customers, but diversified enough that no single loss would be existential.",
                4: "Broad, diversified customer base with no material single-customer or top-N concentration risk.",
            }},
            {"key": "pref_stack", "label": "Pref stack", "anchors": {
                1: "Confirmed stacked, senior-heavy liquidation preference structure ahead of this round.",
                2: "Cap table/pref stack structure not disclosed and cannot be estimated.",
                3: "Preferred stack is reasonably lean, with no material senior-preference overhang identified.",
                4: "Lean preferred stack confirmed -- clean capital structure that protects downside and signals capital discipline.",
            }},
            {"key": "moat_durability", "label": "Moat durability", "anchors": {
                1: "Moat is purely narrative (\"great team,\" \"we move fast\") with no structural defensibility identified.",
                2: "Some structural elements claimed but not clearly evidenced (e.g. asserted network effects with no usage data).",
                3: "Real but moderate structural moat -- some combination of switching costs, early network effects, or a regulatory edge.",
                4: "Strong structural moat -- durable network effects, a genuine regulatory barrier, or high switching costs, clearly evidenced.",
            }},
            {"key": "market_tam", "label": "Market/TAM", "anchors": {
                1: "Current market is not venture-scale and no credible adjacent expansion path exists.",
                2: "Market size or expansion path is unclear/undisclosed and cannot be credibly estimated.",
                3: "Current market alone is venture-scale, though the adjacent expansion path is more aspirational than in-motion.",
                4: "Current market is venture-scale and a credible, already-in-motion adjacent expansion path is evidenced.",
            }},
            {"key": "valuation_vs_comps", "label": "Valuation vs comps", "anchors": {
                1: "Entry valuation is confirmed materially rich vs. growth-adjusted public/private comps.",
                2: "No public revenue multiple available and no usable [ESTIMATED]/comp-set triangulation exists -- write [NOT PUBLIC].",
                3: "Entry multiple is defensible vs. public/private comps on a growth-adjusted (Rule-of-40-style) basis, confirmed or [ESTIMATED].",
                4: "Entry multiple is favorable vs. growth-adjusted comps -- priced at a discount to what the growth/margin profile would justify.",
            }},
            {"key": "sector_risk", "label": "Sector risk", "anchors": {
                1: "Confirmed acute disruption risk -- foundational-model capability creep, pending regulatory action, or macro cyclicality that could impair the business within the hold period.",
                2: "Sector risk is unclear or unassessed from available evidence.",
                3: "Some sector exposure identified but manageable -- not an acute, near-term threat.",
                4: "Sector is not at acute disruption risk -- durable position against foundational-model creep, regulatory shifts, and macro cyclicality.",
            }},
        ],
    },
    {
        "key": "return_potential",
        "label": "Return Potential",
        "subcategories": [
            {"key": "entry_multiple", "label": "Entry multiple", "anchors": {
                1: "Entry multiple is not justified even after accounting for growth and margin trajectory.",
                2: "Entry multiple cannot be assessed -- insufficient data on growth/margin trajectory to judge.",
                3: "Entry multiple is justified once growth and margin trajectory are factored in, though not favorable.",
                4: "Entry multiple is well justified -- growth-adjusted pricing is attractive relative to trajectory.",
            }},
            {"key": "base_case_moic", "label": "Base-case MOIC", "anchors": {
                1: "Below 2x MOIC / below 10% IRR as the realistic base case.",
                2: "2-3x MOIC / 10-20% IRR -- below venture scale in the base case.",
                3: "3-6x MOIC / 20-30% IRR as a realistic base case, with some execution risk.",
                4: "6x+ MOIC / 30%+ IRR as the base case (not the bull case), with a credible path shown.",
            }},
            {"key": "exit_path", "label": "Exit path", "anchors": {
                1: "No credible exit path identified -- no IPO readiness signal, no M&A appetite, no comparable precedent exits.",
                2: "Exit path is unclear or speculative, with only weak precedent.",
                3: "A reasonable exit path exists (IPO readiness or active M&A appetite in the sector) with some precedent support.",
                4: "Clear exit path -- strong IPO readiness or active M&A appetite in the sector, with genuinely comparable precedent exits.",
            }},
            {"key": "dilution", "label": "Dilution", "anchors": {
                1: "Dilution modeling was not attempted, or the deal isn't viable even under a favorable dilution assumption.",
                2: "Dilution is modeled loosely or with unsupported assumptions.",
                3: "At least two future financing rounds (~20-25% each) are explicitly modeled before exit, with a viable resulting MOIC.",
                4: "Dilution is rigorously modeled across multiple future rounds and the return case holds up well even under conservative assumptions.",
            }},
            {"key": "time_to_liquidity", "label": "Time to liquidity", "anchors": {
                1: "Time to liquidity is long with no offsetting IRR -- the modeled MOIC only works over an unrealistically extended hold.",
                2: "Time to liquidity is unclear or unmodeled.",
                3: "A reasonable time-to-liquidity estimate exists and the resulting IRR is acceptable, even if not exceptional.",
                4: "Time to liquidity is modeled explicitly and the resulting IRR is strong -- the same MOIC compressed into a shorter, credible hold.",
            }},
            {"key": "downside_protection", "label": "Downside protection", "anchors": {
                1: "No meaningful downside protection -- weak or absent liquidation preference, pro-rata, or seniority; for secondaries, a premium paid vs. last priced round.",
                2: "Downside protection terms are undisclosed or unclear.",
                3: "Standard downside protection in place -- reasonable liquidation preference, pro-rata rights, and seniority.",
                4: "Strong downside protection -- favorable liquidation preference/seniority, or for secondaries, a confirmed discount vs. last priced round.",
            }},
            {"key": "exit_multiples", "label": "Exit multiples", "anchors": {
                1: "Exit-multiple assumptions rely on aspirational comps from a different category or a cycle peak, not a genuinely comparable precedent set.",
                2: "No genuinely comparable exit precedent set could be identified.",
                3: "Exit-multiple assumptions are anchored to a reasonably comparable precedent set.",
                4: "Exit-multiple assumptions are anchored to a genuinely comparable, well-evidenced precedent set.",
            }},
            {"key": "secondary_demand", "label": "Secondary demand", "anchors": {
                1: "No secondary market signal found, or the company is reported as actively avoided/discounted in secondary trading.",
                2: "Secondary market activity/demand could not be assessed from available sources.",
                3: "Some secondary market interest signal exists but not on a named tracked list (Setter 30) or major marketplace.",
                4: "Company appears on the Setter Capital \"Setter 30\" or is reported as actively traded by Forge/Caplight/EquityZen or similar -- external corroboration of the exit thesis.",
            }},
        ],
    },
]


def _subcategories_markdown(dim: dict) -> str:
    """Render one dimension's fixed subcategory list as numbered anchor
    tables -- the exact block that replaces that dimension's
    `<!-- SUBCATEGORIES: <key> -->` marker in prompts/rubric.md."""
    lines = []
    for i, sub in enumerate(dim["subcategories"], 1):
        lines.append(f"{i}. **{sub['label']}**")
        lines.append("")
        lines.append("| Score | Anchor |")
        lines.append("| --- | --- |")
        for score in (1, 2, 3, 4):
            lines.append(f"| {score} | {sub['anchors'][score]} |")
        lines.append("")
    return "\n".join(lines).rstrip()


def rubric_text() -> str:
    """The full human-readable rubric, injected into the agent prompts.
    prompts/rubric.md carries the hand-written narrative (thesis, tier
    lists, backtest/calibration tables, hard-auto-pass discussion); each
    dimension's fixed subcategory anchor tables are generated from PARAMS
    above and spliced in at its `<!-- SUBCATEGORIES: <key> -->` marker, so
    the anchor text has exactly one source of truth."""
    path = os.path.join(_PROMPTS, "rubric.md")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    def repl(m):
        key = m.group(1)
        dim = next((p for p in PARAMS if p["key"] == key), None)
        if dim is None:
            raise ValueError(f"prompts/rubric.md references unknown PARAMS key {key!r}")
        return _subcategories_markdown(dim)

    return re.sub(r"<!-- SUBCATEGORIES: (\w+) -->", repl, text)


def validate():
    if not PARAMS:
        raise ValueError("PARAMS is empty")
    for p in PARAMS:
        if not p.get("subcategories"):
            raise ValueError(f"dimension {p['key']!r} has no subcategories")
    return True


def dimension_score(subcategory_scores: list) -> float:
    """subcategory_scores: list of 1-4 scores for one dimension's
    subcategories (whatever the model actually returned -- a subcategory
    the model dropped is simply absent from this list, not defaulted to 0,
    so a partial response doesn't unfairly tank the dimension). Returns the
    mean, 1 decimal."""
    scores = [s for s in subcategory_scores if s]
    return round(sum(scores) / len(scores), 1) if scores else 0.0


def weighted_score(param_scores: dict) -> float:
    """param_scores: {key: computed 1-4 dimension score}. All six
    dimensions are weighted equally (~16.7% each) as of rubric v4 -- Terms
    included, no longer excluded as gate_only. Because every dimension
    carries the same weight, this is mathematically a plain mean over all
    six; kept as its own function (rather than inlining raw_score
    everywhere) so a future reweighting doesn't need a schema change."""
    keys = [p["key"] for p in PARAMS]
    scores = [param_scores.get(k, 0) or 0 for k in keys]
    return round(sum(scores) / len(scores), 1) if scores else 0.0


def raw_score(param_scores: dict) -> float:
    """Identical computation to weighted_score at this rubric version (see
    above) -- kept as a separate field/function for the same
    forward-compatibility reason weighted_score is."""
    return weighted_score(param_scores)
