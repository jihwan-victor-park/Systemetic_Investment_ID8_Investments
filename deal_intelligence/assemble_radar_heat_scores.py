"""Combines build_radar_research_input.py's precomputed signals
(raiseProbability, tier1InvestorCount, momEmployeeGrowth, jobPostingVelocity
-- given, never per-agent judgment, see that module's own docstring) with
the Haiku batches' web-researched signals (the other 10 -- see
docs/RADAR_HEAT_SCORE_RULES.md / RADAR_HEAT_SCORE_RUN.md) into one
Firestore-ready entry per company, in the exact shape
radar_apply_heat_scores.py expects.

All aggregation math (contribution/score/normalizedScore/pointsAvailable)
is computed HERE, once, deterministically -- not trusted to each research
agent, which is the other half of the 2026-08-14 consistency fix (see
build_radar_research_input.py's own docstring for the first half, the
predictedWindowOpen divergence bug).

Usage:
    python3 -m deal_intelligence.assemble_radar_heat_scores
        [--input deal_intelligence/data/radar-companies-research-input.json]
        [--batches-dir deal_intelligence/data/radar_batches_out]
        [--out deal_intelligence/data/radar-heat-scores-2026-08-14.json]
        [--as-of 2026-08-14]
"""
import argparse
import glob
import json
from datetime import date

from . import radar_market_heat

DEFAULT_INPUT = "deal_intelligence/data/radar-companies-research-input.json"
DEFAULT_BATCHES_DIR = "deal_intelligence/data/radar_batches_out"
DEFAULT_OUT = "deal_intelligence/data/radar-heat-scores-2026-08-14.json"

# The 4 "given" signal keys come from precomputedSignals; these 10 are what
# the Haiku batches actually researched. Any signal outside this union is a
# sign a batch drifted from the requested schema.
RESEARCHED_KEYS = {
    "industryGrowth", "newsVolume", "googleTrendsSearchInterest", "stepUp",
    "yoyRevenueGrowth", "websiteVisitsGrowth", "redditActivity",
    "crunchbaseGrowthScore", "crunchbaseHeatScore", "crunchbaseSurgeScore",
}
GIVEN_KEYS = {"raiseProbability", "tier1InvestorCount", "momEmployeeGrowth", "jobPostingVelocity"}
ALL_KEYS = RESEARCHED_KEYS | GIVEN_KEYS


def _load_researched(batches_dir):
    """{company_id: {signal_key: {computed, raw, evidence, source, ...}}}
    from every batch_*.json in batches_dir. Raises if a batch is missing,
    since a silent gap here means some companies never got researched at
    all -- caller needs to know, not get a partial file quietly."""
    by_id = {}
    for path in sorted(glob.glob(f"{batches_dir}/batch_*.json")):
        with open(path) as f:
            batch = json.load(f)
        for entry in batch:
            by_id[entry["id"]] = entry["signals"]
    return by_id


def _merged_signals(precomputed, researched):
    """14-key signals dict, weight attached from radar_market_heat.WEIGHTS
    (the single canonical weight table -- neither the precomputed nor
    researched halves are trusted to carry their own weight through
    correctly)."""
    signals = {}
    for key, entry in precomputed.items():
        signals[key] = {**entry, "weight": radar_market_heat.WEIGHTS[key]}
    for key, entry in (researched or {}).items():
        if key not in RESEARCHED_KEYS:
            continue  # a batch produced an unexpected key -- ignore rather than silently trust it
        signals[key] = {**entry, "weight": radar_market_heat.WEIGHTS[key]}
    missing = ALL_KEYS - signals.keys()
    for key in missing:
        signals[key] = {"computed": False, "raw": None, "weight": radar_market_heat.WEIGHTS[key], "evidence": "not returned by research batch"}
    return signals


def _score_signals(signals):
    """Exact math from RADAR_HEAT_SCORE_RULES.md's 'Scoring math' section."""
    points_available = 0.0
    contribution_total = 0.0
    not_computed = []
    for key, entry in signals.items():
        if entry.get("computed"):
            weight = entry["weight"]
            contribution = round(entry["raw"] / 10 * weight, 2)
            entry["contribution"] = contribution
            points_available += weight
            contribution_total += contribution
        else:
            entry["contribution"] = None
            not_computed.append(key)
    score = round(min(contribution_total, 100), 1)
    normalized_score = round(min(contribution_total / points_available * 100, 100), 1) if points_available > 0 else None
    return score, normalized_score, round(points_available, 1), sorted(not_computed)


def assemble(input_entries, researched_by_id, as_of):
    out, skipped = [], []
    for e in input_entries:
        researched = researched_by_id.get(e["id"])
        if researched is None:
            skipped.append(e["id"])
            continue
        signals = _merged_signals(e["precomputedSignals"], researched)
        score, normalized_score, points_available, not_computed = _score_signals(signals)
        market_heat = {
            "roundAnnouncedFlag": False,
            "timingUrgencyMultiplier": 1.0,
            "monthsUntilWindow": e["monthsUntilWindow"],
            "score": score,
            "signals": signals,
            "normalizedScore": normalized_score,
            "pointsAvailable": points_available,
            "notComputed": not_computed,
            "predictedWindowOpen": e["predictedWindowOpen"],
            "source": f"manual-web-research-{as_of.isoformat()}",
            "computedAt": as_of.isoformat(),
            "windowBasis": e["windowBasis"],
        }
        out.append({
            "id": e["id"],
            "name": e["name"],
            "clock": e.get("newClock"),
            "schedule": e.get("newSchedule"),
            "marketHeat": market_heat,
        })
    return out, skipped


def run(input_path=DEFAULT_INPUT, batches_dir=DEFAULT_BATCHES_DIR, out_path=DEFAULT_OUT, as_of=None):
    as_of = as_of or date.today()
    with open(input_path) as f:
        input_entries = json.load(f)
    researched_by_id = _load_researched(batches_dir)

    out, skipped = assemble(input_entries, researched_by_id, as_of)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    scores = sorted((e["marketHeat"]["normalizedScore"] or 0, e["name"]) for e in out)
    print(f"{len(out)}/{len(input_entries)} companies assembled -> {out_path}")
    if skipped:
        print(f"MISSING from batches (not yet researched): {skipped}")
    if scores:
        print(f"normalizedScore range: {scores[0][1]}={scores[0][0]} .. {scores[-1][1]}={scores[-1][0]}")
    heavy_unknown = [e["name"] for e in out if len(e["marketHeat"]["notComputed"]) >= 10]
    if heavy_unknown:
        print(f"{len(heavy_unknown)} companies came back almost entirely computed:false: {heavy_unknown}")
    return out, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", default=DEFAULT_INPUT)
    ap.add_argument("--batches-dir", default=DEFAULT_BATCHES_DIR)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--as-of", default=None, help="ISO date, defaults to today")
    args = ap.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    run(input_path=args.input, batches_dir=args.batches_dir, out_path=args.out, as_of=as_of)


if __name__ == "__main__":
    main()
