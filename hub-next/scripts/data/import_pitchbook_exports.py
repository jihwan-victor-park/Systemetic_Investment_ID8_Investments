#!/usr/bin/env python3
"""
Parses PitchBook "Deals (Portfolio)" .xlsx exports (one per partner VC, dropped into
./pitchbook_exports/) and merges them into partner-vcs-seed.json.

Each row in a PitchBook export is one DEAL, not one company -- a company where the
investor did multiple rounds shows up multiple times. This script groups by
Portfolio Company ID, picks the highest deal-number row as that investor's most
recent participation, and writes one merged portfolio entry per company.

Known limitation: an investor's export only lists deals THAT INVESTOR participated
in. If a portfolio company raised a later round without this VC, this script's
latestRound/latestRoundDate will reflect the VC's own latest participation, not
necessarily the company's true latest financing. roundInvested is reliable;
latestRound should be treated as best-effort unless it's the only round on file.

Usage:
    python3 import_pitchbook_exports.py [--dry-run]
"""
import argparse
import difflib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import openpyxl

SCRIPT_DIR = Path(__file__).resolve().parent
SEED_PATH = SCRIPT_DIR / "partner-vcs-seed.json"
EXPORTS_DIR = SCRIPT_DIR / "pitchbook_exports"

HEADER_ROW = 7
DATA_START_ROW = 8

SUFFIX_WORDS = {
    "capital", "ventures", "venture", "partners", "partner", "group", "fund",
    "funds", "management", "llc", "inc", "lp", "llp", "co", "collective", "vc",
    "company", "corp", "corporation",
}

# PitchBook exports a firm's own legal/registered name, which sometimes differs
# from the shorter name it's tracked under in the seed. Add pairs here as they
# turn up in the "NO MATCH" report -- keyed by the raw investor name PitchBook
# uses, valued by the seed firm's exact "name" field.
NAME_ALIASES = {
    "alleycorp": "Alley",
    "autopilot management company": "AutoPilot",
    "blue scorpion investments": "bluescorpioninv",
}


def normalize_name(name):
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name)  # strip trailing "(City, State)"
    name = re.sub(r"[^a-z0-9]+", " ", name.lower())
    words = [w for w in name.split() if w not in SUFFIX_WORDS]
    return " ".join(words) or name


def is_real_series_letter(deal_type_2):
    if not deal_type_2:
        return False
    return bool(re.match(r"^Series [A-Z]+\d*$", deal_type_2.strip()))


def ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def format_round(deal_type_1, deal_type_2, deal_no):
    if is_real_series_letter(deal_type_2):
        return deal_type_2.strip()
    base = (deal_type_1 or "").strip() or "Unknown"
    if deal_no:
        return f"{base} ({ordinal(deal_no)} Round)"
    return base


def fmt_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value).strip() or None


def fmt_hq(city, state, country):
    city = (city or "").strip()
    state = (state or "").strip()
    country = (country or "").strip()
    if city and state:
        return f"{city}, {state}"
    if city and country:
        return f"{city}, {country}"
    return city or state or country or ""


def parse_export(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Data"]

    investor_name = None
    for r in range(1, HEADER_ROW):
        label = ws.cell(row=r, column=1).value
        if label and "Data pulled from" in str(label):
            investor_name = ws.cell(row=r, column=2).value
            break
    if not investor_name:
        raise ValueError(f"Could not find 'Data pulled from:' investor name in {path.name}")

    headers = [ws.cell(row=HEADER_ROW, column=c).value for c in range(1, ws.max_column + 1)]
    idx = {h: i for i, h in enumerate(headers) if h}

    def get(row, col_name):
        i = idx.get(col_name)
        if i is None:
            return None
        return row[i]

    rows = []
    for r in range(DATA_START_ROW, ws.max_row + 1):
        row = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
        if not row[idx["Portfolio Company ID"]]:
            continue
        rows.append(row)

    companies = defaultdict(list)
    for row in rows:
        companies[get(row, "Portfolio Company ID")].append(row)

    parsed = []
    for pbid, deal_rows in companies.items():
        def deal_no_of(row):
            v = get(row, "Deal No.")
            return v if isinstance(v, (int, float)) else -1

        latest = max(deal_rows, key=deal_no_of)
        earliest_date_row = min(
            (row for row in deal_rows if get(row, "Deal Date")),
            key=lambda row: get(row, "Deal Date"),
            default=latest,
        )

        deal_no = get(latest, "Deal No.")
        round_label = format_round(
            get(latest, "Deal Type 1"), get(latest, "Deal Type 2"), deal_no
        )

        raw_status = (get(latest, "Status") or "").strip()
        investor_status = "Active" if raw_status == "Active Investor" else (raw_status or None)

        entry = {
            "company": get(latest, "Portfolio Company Name"),
            "companyPbid": pbid,
            "pitchbookUrl": get(latest, "PitchBook Link"),
            "description": get(latest, "Description") or None,
            "industry": get(latest, "Company Industry Sector") or None,
            "category": get(latest, "Company Industry Group") or None,
            "vertical": get(latest, "Company Verticals") or None,
            "businessStatus": get(latest, "Company Business Status") or None,
            "hqLocation": fmt_hq(
                get(latest, "Company City"),
                get(latest, "Company State/Province"),
                get(latest, "Company Country/Territory"),
            ),
            "investorStatus": investor_status,
            "investorSince": fmt_date(get(earliest_date_row, "Deal Date")),
            "roundInvested": round_label,
            "latestRound": round_label,
            "latestRoundDate": fmt_date(get(latest, "Deal Date")),
            "source": "pitchbook",
            # Fields PitchBook's deal export carries that the current schema doesn't --
            # kept as a nested block so nothing collides with existing keys.
            "financials": {
                "employees": get(latest, "# of Employees at Company"),
                "revenueUsdThousands": get(latest, "Company Revenue (thousand, USD)"),
                "revenueStatus": get(latest, "Company Revenue Status"),
                "ebitdaUsdThousands": get(latest, "Company EBITDA (thousand, USD)"),
                "netIncomeUsdThousands": get(latest, "Company Net Income (thousand, USD)"),
                "dealSizeUsdMillions": get(latest, "Deal Size (million, USD)"),
                "postValuationUsdMillions": get(latest, "Company Post Valuation (million, USD)"),
                "postValuationStatus": get(latest, "Company Post Valuation Status"),
                "financingStatus": get(latest, "Company Financing Status"),
            },
        }
        parsed.append(entry)

    return investor_name, parsed


def match_firm(investor_name, firms):
    """Exact match on normalized name only. Never auto-merges on a fuzzy guess --
    a wrong merge silently contaminates another firm's portfolio, which is worse
    than just asking. Returns (firm_or_None, suggestion_name_or_None)."""
    target = normalize_name(investor_name)
    for firm in firms:
        if normalize_name(firm["name"]) == target:
            return firm, None
    alias = NAME_ALIASES.get(investor_name.strip().lower())
    if alias:
        for firm in firms:
            if firm["name"] == alias:
                return firm, None
    normalized_names = {normalize_name(firm["name"]): firm["name"] for firm in firms}
    close = difflib.get_close_matches(target, list(normalized_names.keys()), n=1, cutoff=0.6)
    suggestion = normalized_names[close[0]] if close else None
    return None, suggestion


def merge_entry(portfolio, new_entry):
    for existing in portfolio:
        if existing.get("companyPbid") == new_entry["companyPbid"]:
            for key, value in new_entry.items():
                if value not in (None, "", {}):
                    existing[key] = value
            return "updated"
    template = {
        "company": None, "industry": None, "series": "", "investorStatus": None,
        "investorSince": None, "exitType": None, "exitDate": None,
        "exitSizeUsdMillions": None, "companyPbid": None, "pitchbookUrl": None,
        "source": "pitchbook", "description": None, "category": None,
        "vertical": None, "yearFounded": None, "hqLocation": None,
        "businessStatus": None, "latestRound": None, "latestRoundDate": None,
        "roundInvested": None,
    }
    template.update(new_entry)
    portfolio.append(template)
    return "added"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Report without writing the seed file")
    args = parser.parse_args()

    if not EXPORTS_DIR.exists():
        print(f"No exports folder at {EXPORTS_DIR}", file=sys.stderr)
        sys.exit(1)

    xlsx_files = sorted(EXPORTS_DIR.glob("*.xlsx"))
    if not xlsx_files:
        print(f"No .xlsx files found in {EXPORTS_DIR}")
        return

    with open(SEED_PATH) as f:
        firms = json.load(f)

    unmatched = []
    summary = []

    for path in xlsx_files:
        try:
            investor_name, entries = parse_export(path)
        except Exception as e:
            print(f"FAILED  {path.name}: {e}")
            continue

        firm, suggestion = match_firm(investor_name, firms)
        if not firm:
            unmatched.append((path.name, investor_name, suggestion))
            hint = f" (did you mean '{suggestion}'?)" if suggestion else ""
            print(f"NO MATCH  {path.name} -> investor '{investor_name}' not found in seed{hint}")
            continue

        firm.setdefault("portfolio", [])
        added = updated = 0
        for entry in entries:
            result = merge_entry(firm["portfolio"], entry)
            if result == "added":
                added += 1
            else:
                updated += 1

        summary.append((path.name, firm["name"], len(entries), added, updated))
        print(f"OK  {path.name} -> {firm['name']}: {len(entries)} companies ({added} added, {updated} updated)")

    if not args.dry_run:
        with open(SEED_PATH, "w") as f:
            json.dump(firms, f, indent=2)
            f.write("\n")
        print(f"\nWrote {SEED_PATH}")
    else:
        print("\n--dry-run: seed file not written")

    print(f"\n{len(summary)} file(s) merged, {len(unmatched)} unmatched investor name(s)")
    if unmatched:
        print("Unmatched (verify then add these firms manually, or rename the seed entry):")
        for fname, iname, suggestion in unmatched:
            hint = f" -- possible match: '{suggestion}'" if suggestion else ""
            print(f"  {fname}: '{iname}'{hint}")


if __name__ == "__main__":
    main()
