"""Screen a PitchBook export through Stage 1 — Perplexity only, no Attio needed.

Drop in a PitchBook .xlsx search export, get every deal scored against the ID8
rubric, company pages + .docx written to the hub, and an email-ready HTML block
printed. This is the standalone path for when you have a file rather than live
Qualified deals in Attio (the Attio path is `python -m deal_intelligence.pipeline`).

    python -m deal_intelligence.screen_pitchbook /path/to/export.xlsx
    python -m deal_intelligence.screen_pitchbook export.xlsx --no-publish   # don't write hub pages
    python -m deal_intelligence.screen_pitchbook export.xlsx --email out.html

Requires PERPLEXITY_API_KEY (in deal_intelligence/.env or the environment).
"""
import argparse
import asyncio
import os
import re
import sys

import pandas as pd
import openpyxl

from . import config, pipeline, email_format
from .schemas import DealInput


def _extract_websites(path, header_row_0idx):
    """Company Website is a =HYPERLINK() formula → NaN via pandas; pull the
    display text via openpyxl. Returns {row_position: domain}."""
    wb = openpyxl.load_workbook(path, data_only=False)
    ws = wb.active
    xl_header_row = header_row_0idx + 1
    col_idx = next((c.column for c in ws[xl_header_row] if c.value == "Company Website"), None)
    if not col_idx:
        return {}
    out = {}
    for xl_row in range(xl_header_row + 1, ws.max_row + 1):
        val = ws.cell(row=xl_row, column=col_idx).value
        if isinstance(val, str) and val.upper().startswith("=HYPERLINK("):
            m = re.search(r'=HYPERLINK\s*\(\s*"[^"]*"\s*,\s*"([^"]*)"\s*\)', val, re.I)
            if m:
                out[xl_row - xl_header_row - 1] = m.group(1)
        elif val:
            out[xl_row - xl_header_row - 1] = str(val)
    return out


def load_deals(path):
    """Parse a PitchBook export into DealInputs (skips the metadata preamble)."""
    raw = pd.read_excel(path, header=None)
    header_row = next((i for i, row in raw.iterrows() if "Companies" in row.values), None)
    if header_row is None:
        sys.exit("ERROR: could not find the 'Companies' header row — is this a PitchBook export?")
    df = pd.read_excel(path, header=header_row).dropna(subset=["Companies"])
    websites = _extract_websites(path, header_row)

    deals = []
    for i, (_, row) in enumerate(df.iterrows()):
        def g(col):
            v = row.get(col)
            return str(v).strip() if pd.notna(v) and str(v).strip() else None
        deals.append(DealInput(
            record_id=f"pb-{i}",
            name=str(row["Companies"]).strip(),
            domain=websites.get(i),
            round=g("Series"),
            hq=g("HQ Location"),
            lead_investors=g("Lead/Sole Investors"),
        ))
    return deals


async def _run(path, publish, email_path):
    if not config.PERPLEXITY_API_KEY:
        sys.exit("ERROR: PERPLEXITY_API_KEY not set (deal_intelligence/.env or environment).")
    deals = load_deals(path)
    print(f"Loaded {len(deals)} deal(s) from {os.path.basename(path)}:")
    for d in deals:
        print(f"  - {d.name}  [{d.round or '?'} · {d.hq or '?'} · lead {d.lead_investors or '?'}]")
    print("\nScoring against the ID8 rubric (Perplexity)…\n")

    # dry_run=True: no Attio (this path has no record_ids); publish writes hub pages.
    result = await pipeline.screen(deals, dry_run=True, publish=publish)

    badge = {"strong_go": "STRONG", "go_ic": "GO-IC ", "more_diligence": "DILIG ",
             "pass": "PASS  ", "watch_list": "WATCH "}
    for d in result["stage1"]:
        b = "AUTO-P" if d.get("hard_auto_pass") else badge.get(d["tier"], "—     ")
        print(f"  {d['fit_score']:>4.1f} / 4.0  (raw {d.get('raw_score', 0):.1f})  [{b:<6}]  {d['name']}")

    if publish:
        print()
        for d in result["stage1"]:
            print(f"  hub page: {config.HUB_COMPANIES_DIR}/…  ·  {d['hub_url']}")

    if email_path:
        with open(email_path, "w", encoding="utf-8") as fh:
            fh.write(result["email_html"])
        print(f"\nEmail HTML written to {email_path}")

    print(f"\nDone. {result['screened']} screened, {result['gated']} cleared the gate, "
          f"{result['more_diligence']} more diligence, {result['watch_list']} watch list.")


def main():
    ap = argparse.ArgumentParser(description="Screen a PitchBook export through Stage 1.")
    ap.add_argument("export", help="path to a PitchBook .xlsx search export")
    ap.add_argument("--no-publish", action="store_true", help="don't write company pages to the hub")
    ap.add_argument("--email", metavar="PATH", help="also write the email HTML to this file")
    args = ap.parse_args()
    asyncio.run(_run(args.export, publish=not args.no_publish, email_path=args.email))


if __name__ == "__main__":
    main()
