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

from . import config, attio_io, stage1_fit, stage2_research, rubric, fit_note, email_format, hub_push, firestore_push


async def screen(deals: list, dry_run: bool = False, publish: bool = False) -> dict:
    """Score a given list of DealInputs through Stage 1 and produce all outputs:
    Attio write-back (fit score, gate, rationale, hub link), optional hub pages,
    and the email-ready render. This is the shared core — both the Attio-pull
    pipeline and the /screen batch endpoint call it.
    """
    rubric.validate()
    fits = await stage1_fit.run(deals)
    fits.sort(key=lambda f: f.fit_score, reverse=True)
    deal_by_id = {d.record_id: d for d in deals}

    hub_urls = {}
    for f in fits:
        d = deal_by_id.get(f.record_id)
        if d:
            hub_urls[f.record_id] = fit_note.hub_url(d)

    if not dry_run:
        for f in fits:
            attio_io.write_fit(f, hub_url=hub_urls.get(f.record_id))

    # Publish a company page + downloadable .docx per screened deal (hub Research).
    if publish:
        gh_token = os.getenv("GH_TOKEN")
        for f in fits:
            d = deal_by_id.get(f.record_id)
            if not d:
                continue
            slug = fit_note.company_id(d)
            md_path   = f"{config.HUB_COMPANIES_DIR}/{slug}.md"
            docx_path = f"{config.HUB_DOCX_DIR}/{slug}.docx"
            docx_bytes = fit_note.build_docx_bytes(f, d)
            if gh_token:
                # Cloud Run: build content in memory, push via GitHub API.
                screen_out = fit_note._build_screen_content(f, d, slug, docx_path)
                try:
                    hub_push.push_company_screen(
                        slug=slug,
                        md_content=screen_out,
                        docx_bytes=docx_bytes,
                        md_path=md_path,
                        docx_path=docx_path,
                    )
                except Exception as exc:
                    print(f"[hub_push] {slug}: {exc}")
            else:
                # Local / CI: write directly to disk and commit via git.
                fit_note.write_company_screen(f, d, config.HUB_COMPANIES_DIR, config.HUB_DOCX_DIR)
            # hub-next (Firestore + Cloud Storage) -- independent of the old
            # hub's git-commit path above; dynamic, no rebuild required.
            try:
                firestore_push.push_company_screen_firestore(f, d, slug, docx_bytes, source="attio")
            except Exception as exc:
                print(f"[firestore_push] {slug}: {exc}")

    return {
        "screened": len(fits),
        "gated": sum(1 for f in fits if f.gate),
        "more_diligence": sum(1 for f in fits if f.quality_tier == "more_diligence"),
        "watch_list": sum(1 for f in fits if f.quality_tier == "watch_list"),
        "hard_auto_pass": sum(1 for f in fits if f.hard_auto_pass),
        "errors": sum(1 for f in fits if f.quality_tier == "error"),
        "stage1": [{"name": f.name, "fit_score": f.fit_score, "raw_score": f.raw_score, "gate": f.gate,
                    "tier": f.quality_tier, "hard_auto_pass": f.hard_auto_pass,
                    "hub_url": hub_urls.get(f.record_id)} for f in fits],
        "fits": fits,  # in-process callers use this; the HTTP layer drops it
        "email_html": email_format.email_html(fits, hub_urls=hub_urls),
        "email_text": email_format.email_text(fits),
    }


async def run(dry_run: bool = False, stage1_only: bool = False, publish: bool = True) -> dict:
    deals = attio_io.get_qualified_deals()
    result = await screen(deals, dry_run=dry_run, publish=publish)
    fits = result.pop("fits")
    summary = {"qualified": len(deals), "memos": [], **result}

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
