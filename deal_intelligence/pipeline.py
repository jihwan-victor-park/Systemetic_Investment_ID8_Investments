"""Orchestration. Pull qualified deals, score them all (stage 1), then deep
research and memo only the ones that clear the gate (stage 2).

n8n triggers this over HTTP via the /screen-deals endpoint, or run it directly:

    python -m deal_intelligence.pipeline            # full run
    python -m deal_intelligence.pipeline --dry-run  # no Attio write-back
    python -m deal_intelligence.pipeline --stage1   # stage 1 only
"""
import argparse
import asyncio
import json
import os

from . import config, attio_io, stage1_fit, stage2_research, rubric, fit_note, email_format


async def run(dry_run: bool = False, stage1_only: bool = False, publish: bool = True) -> dict:
    rubric.validate()
    deals = attio_io.get_qualified_deals()

    fits = await stage1_fit.run(deals)
    fits.sort(key=lambda f: f.fit_score, reverse=True)
    deal_by_id = {d.record_id: d for d in deals}
    if not dry_run:
        for f in fits:
            attio_io.write_fit(f)

    # Publish a company page + downloadable .docx per screened deal (hub Research)
    if publish:
        for f in fits:
            d = deal_by_id.get(f.record_id)
            if d:
                fit_note.write_company_screen(f, d, config.HUB_COMPANIES_DIR, config.HUB_DOCX_DIR)

    summary = {"qualified": len(deals),
               "stage1": [{"name": f.name, "fit_score": f.fit_score, "gate": f.gate} for f in fits],
               "memos": [],
               # email-ready render for n8n's Gmail node
               "email_html": email_format.email_html(fits),
               "email_text": email_format.email_text(fits)}

    if stage1_only:
        return summary

    # gate: only target deals get deep research + a memo
    targets = [f for f in fits if f.gate]
    target_deals = [d for d in deals if any(t.record_id == d.record_id for t in targets)]
    memos = await stage2_research.run(target_deals)
    if not dry_run:
        for m in memos:
            attio_io.write_memo(m)
    summary["memos"] = [{"name": m.name, "final_score": m.final_score, "path": m.markdown_path} for m in memos]
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="do not write back to Attio")
    ap.add_argument("--stage1", action="store_true", help="stage 1 only, no deep research")
    ap.add_argument("--no-publish", action="store_true", help="skip writing company pages to the hub")
    args = ap.parse_args()
    result = asyncio.run(run(dry_run=args.dry_run, stage1_only=args.stage1, publish=not args.no_publish))
    # email_html/email_text are long; print everything else
    print(json.dumps({k: v for k, v in result.items() if k not in ("email_html", "email_text")}, indent=2))


if __name__ == "__main__":
    main()
