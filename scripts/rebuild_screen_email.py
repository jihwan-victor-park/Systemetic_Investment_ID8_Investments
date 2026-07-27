#!/usr/bin/env python3
"""Rebuild the Stage 1 screening email from screens ALREADY committed to the hub.

Why this exists: `/process` renders `email_html` in memory and returns it in the
HTTP response. If that response is lost (see project_pipeline_self_deploy_loop --
a deploy draining the container mid-request), the screening work itself is fine
and fully persisted as hub markdown, but the email is gone and the only way to
get it back used to be re-running the screen -- which costs real Perplexity
credits for research that was already paid for once.

This reparses the committed `hub/docs/research/companies/*.md` pages back into
DealFit objects and re-renders them through the same
deal_intelligence.email_format.email_html() the pipeline uses, so the output is
byte-identical in style to a normal run. Zero API calls, zero credits.

Usage:
    python scripts/rebuild_screen_email.py --date 2026-07-27 -o email.html
    python scripts/rebuild_screen_email.py --slugs atoms,cusp,glow -o email.html

By default it skips screens whose scoring failed and obviously-bad company
names (see _is_junk_name) -- pass --include-failed / --include-junk to keep them.
"""
import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from deal_intelligence import rubric
from deal_intelligence.email_format import TIER_LABEL, email_html, email_text
from deal_intelligence.schemas import DealFit, ParamScore

# Reverse of email_format's own maps, so a verdict string rendered into the hub
# page parses back to the exact tier/label it came from.
LABEL_TO_KEY = {p["label"].lower(): p["key"] for p in rubric.PARAMS}
TEXT_TO_TIER = {v.lower(): k for k, v in TIER_LABEL.items()}

# Heading is "## Screen — 2026-07-27", optionally with the round appended as
# "## Screen — 2026-07-27 · Series B" -- both forms appear in the hub pages.
_SCREEN_RE = re.compile(r"^## Screen — (\d{4}-\d{2}-\d{2})(?:\s*·\s*(.+?))?\s*$", re.MULTILINE)
_FIT_RE = re.compile(
    r"\*\*Fit score:\s*([\d.]+)\s*/\s*4\.0\*\*\s*(?:\(raw\s*([\d.]+)\))?\s*—\s*(.+?)\s*$",
    re.MULTILINE)
_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([\d.]+)\s*/\s*4\s*\|\s*(.*?)\s*\|\s*$", re.MULTILINE)
_RATIONALE_RE = re.compile(r"\*\*Rationale\*\*\s*\n+(.+?)(?=\n\n\*Confidence|\n\n\*\*|\Z)", re.DOTALL)
_CONFIDENCE_RE = re.compile(r"\*Confidence:\s*(\w+)\*")
_TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)


def _is_junk_name(name: str) -> bool:
    """A company name that's clearly a data artifact rather than a real company.
    'nan' is a pandas NaN that survived str() conversion somewhere upstream in
    the PitchBook ingest and got screened as if it were a company."""
    return name.strip().lower() in {"nan", "none", "null", "", "n/a"}


def _parse_verdict(verdict: str) -> tuple:
    """The hub page renders the verdict as a lowercased human string
    ('clears gate · go / ic review', 'pass — hard auto-pass'). Map it back to
    (quality_tier, gate, hard_auto_pass, hard_auto_pass_reason)."""
    v = verdict.strip().lower()
    gate = v.startswith("clears gate")
    hard = "hard auto-pass" in v

    # Strip the gate prefix and any trailing reason clause to isolate the tier.
    core = re.sub(r"^clears gate\s*·\s*", "", v)
    reason = ""
    if "—" in core:
        core, _, reason = (p.strip() for p in core.partition("—"))
    if hard and reason == "hard auto-pass":
        reason = ""

    tier = TEXT_TO_TIER.get(core.strip())
    if tier is None:
        # "scoring failed — not screened" collapses to the error tier; anything
        # else unrecognized is left as-is rather than silently coerced to a
        # real verdict, so a parse miss is visible in the email, not hidden.
        tier = "error" if "scoring failed" in v else core.strip().replace(" ", "_")
    return tier, gate, hard, reason


def parse_screen(md: str, slug: str, want_date: str = None):
    """Parse the most recent screen (or the one matching want_date) out of one
    hub company page. Returns a DealFit, or None if there's no usable screen."""
    name_m = _TITLE_RE.search(md)
    name = name_m.group(1).strip() if name_m else slug

    dates = [(m.group(1), m.end()) for m in _SCREEN_RE.finditer(md)]
    if not dates:
        return None
    if want_date:
        dates = [d for d in dates if d[0] == want_date]
        if not dates:
            return None
    # Pages list screens newest-first; take the first matching block, bounded by
    # the next screen heading so a company with history doesn't bleed together.
    screen_date, start = dates[0]
    nxt = _SCREEN_RE.search(md, start)
    block = md[start:nxt.start()] if nxt else md[start:]

    fit_m = _FIT_RE.search(block)
    if not fit_m:
        return None
    fit_score = float(fit_m.group(1))
    raw_score = float(fit_m.group(2) or fit_m.group(1))
    tier, gate, hard, reason = _parse_verdict(fit_m.group(3))

    params = []
    weight = round(100.0 / len(rubric.PARAMS), 2) if rubric.PARAMS else 0.0
    for label, score, evidence in _ROW_RE.findall(block):
        key = LABEL_TO_KEY.get(label.strip().lower())
        if key is None:
            continue  # table header row, or a label that isn't a rubric dimension
        params.append(ParamScore(key=key, score=float(score), weight=weight,
                                 evidence=evidence.strip()))

    rationale_m = _RATIONALE_RE.search(block)
    conf_m = _CONFIDENCE_RE.search(block)

    return DealFit(
        record_id=slug, name=name, fit_score=fit_score, raw_score=raw_score,
        params=params,
        rationale=(rationale_m.group(1).strip() if rationale_m else ""),
        confidence=(conf_m.group(1) if conf_m else "medium"),
        gate=gate, quality_tier=tier,
        hard_auto_pass=hard, hard_auto_pass_reason=reason,
    ), screen_date


def _read(path: str, git_ref: str = None) -> str:
    """Read a hub page either from the working tree or from a git ref -- the
    screens usually land on `main` while you're working on another branch, so
    reading straight from `id8/main` avoids needing to check anything out."""
    if git_ref:
        r = subprocess.run(["git", "show", f"{git_ref}:{path}"],
                           capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else ""
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _list_slugs(git_ref: str, hub_dir: str) -> list:
    if git_ref:
        r = subprocess.run(["git", "ls-tree", "--name-only", f"{git_ref}:{hub_dir}"],
                           capture_output=True, text=True)
        names = r.stdout.split() if r.returncode == 0 else []
    else:
        names = os.listdir(hub_dir) if os.path.isdir(hub_dir) else []
    return sorted(n[:-3] for n in names if n.endswith(".md"))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="only screens with this date (YYYY-MM-DD)")
    ap.add_argument("--slugs", help="comma-separated company slugs (default: all)")
    ap.add_argument("--git-ref", default="id8/main",
                    help="read hub pages from this git ref instead of the working "
                         "tree; pass '' to use the working tree (default: id8/main)")
    ap.add_argument("--hub-dir", default="hub/docs/research/companies")
    ap.add_argument("--hub-base", default="",
                    help="base URL for 'Full research →' links, e.g. https://hub.id8.vc")
    ap.add_argument("--include-failed", action="store_true",
                    help="include screens whose scoring failed (excluded by default)")
    ap.add_argument("--include-junk", action="store_true",
                    help="include obviously-bad company names like 'nan'")
    ap.add_argument("--title", default="Deal Intelligence — Stage 1 Screen")
    ap.add_argument("-o", "--out", default="screen_email.html")
    args = ap.parse_args()

    git_ref = args.git_ref or None
    slugs = ([s.strip() for s in args.slugs.split(",") if s.strip()]
             if args.slugs else _list_slugs(git_ref, args.hub_dir))

    fits, skipped = [], []
    for slug in slugs:
        md = _read(f"{args.hub_dir}/{slug}.md", git_ref)
        if not md:
            continue
        parsed = parse_screen(md, slug, args.date)
        if not parsed:
            continue
        fit, screen_date = parsed
        if _is_junk_name(fit.name) and not args.include_junk:
            skipped.append(f"{slug} (junk name {fit.name!r})")
            continue
        if fit.quality_tier == "error" and not args.include_failed:
            skipped.append(f"{slug} (scoring failed — score is not real)")
            continue
        fits.append(fit)
        print(f"  ✓ {fit.name:<28} {fit.fit_score:.1f}  {fit.quality_tier}  ({screen_date})")

    if not fits:
        print("No usable screens found.", file=sys.stderr)
        return 1

    hub_urls = ({f.record_id: f"{args.hub_base.rstrip('/')}/research/companies/{f.record_id}"
                 for f in fits} if args.hub_base else None)

    html = email_html(fits, title=args.title, hub_urls=hub_urls)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    txt_path = os.path.splitext(args.out)[0] + ".txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(email_text(fits))

    print(f"\n{len(fits)} deal(s) -> {args.out} and {txt_path}")
    for s in skipped:
        print(f"  skipped: {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
