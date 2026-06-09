import pandas as pd
import re
import sys
import os
from datetime import datetime

# ── 33 Tier 1 firms ──────────────────────────────────────────────────────────
TIER1_FIRMS = [
    "Sequoia Capital", "General Catalyst", "Accel", "Khosla Ventures",
    "Founders Fund", "Benchmark Capital Holdings", "Index Ventures",
    "Thrive Capital", "ICONIQ Capital", "Union Square Ventures",
    "Bessemer Venture Partners", "Lightspeed Venture Partners",
    "Bain Capital Ventures", "Andreessen Horowitz", "Kleiner Perkins",
    "Insight Partners", "IVP", "TCV", "Ribbit Capital", "Notable Capital",
    "New Enterprise Associates", "Dragoneer Investment Group",
    "Battery Ventures", "Valor Equity Partners", "Addition", "BOND Capital",
    "Oak HC/FT", "Coatue Management", "Lux Capital", "8VC", "Menlo Ventures",
    "Greenoaks Capital Partners", "DST Global",
]

# Cleaned lowercase versions for matching
TIER1_CLEAN = {re.sub(r'\s*\([^)]*\)', '', f).strip().lower(): f for f in TIER1_FIRMS}

def strip_parens(text):
    """Remove (partner name) / (location) from investor names."""
    return re.sub(r'\s*\([^)]*\)', '', str(text)).strip()

def parse_investors(cell):
    """Split investor cell into list of clean firm names."""
    if pd.isna(cell) or str(cell).strip() == '':
        return []
    parts = str(cell).split(',')
    return [strip_parens(p.strip()) for p in parts if p.strip()]

def find_tier1(lead_cell, new_cell):
    """Return the canonical Tier 1 firm name found in lead or new investors."""
    all_investors = parse_investors(lead_cell) + parse_investors(new_cell)
    for inv in all_investors:
        inv_lower = inv.lower()
        # Exact match
        if inv_lower in TIER1_CLEAN:
            return TIER1_CLEAN[inv_lower]
        # Substring match (handles "Andreessen Horowitz" matching "a16z" etc.)
        for clean_key, canonical in TIER1_CLEAN.items():
            if clean_key in inv_lower or inv_lower in clean_key:
                return canonical
    return ""

def format_date(val):
    """Convert any date format to YYYY-MM-DD for Attio."""
    if pd.isna(val):
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    try:
        return pd.to_datetime(str(val)).strftime("%Y-%m-%d")
    except:
        return str(val)

def clean_number(val):
    """Strip commas/currency symbols, return plain number string."""
    if pd.isna(val):
        return ""
    cleaned = str(val).replace(',', '').replace('$', '').strip()
    try:
        num = float(cleaned)
        return str(int(num)) if num == int(num) else str(num)
    except:
        return cleaned

def transform(input_path, output_path):
    print(f"Reading: {input_path}")

    # ── Read Excel, skip PitchBook's 7-row metadata header ───────────────────
    xl = pd.read_excel(input_path, header=None)

    # Find the real header row (contains 'Companies')
    header_row = None
    for i, row in xl.iterrows():
        if 'Companies' in row.values:
            header_row = i
            break

    if header_row is None:
        print("ERROR: Could not find header row with 'Companies' column.")
        sys.exit(1)

    df = pd.read_excel(input_path, header=header_row)
    print(f"Found {len(df)} deals")

    # ── Drop unwanted columns ─────────────────────────────────────────────────
    drop_cols = ['Deal ID', 'Primary PitchBook Industry Code', 'View Company Online']
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

    # ── Add Deal Name (required by Attio) ─────────────────────────────────────
    df['Deal name'] = df['Companies'].astype(str) + ' — ' + df['Series'].astype(str)

    # ── Identify Tier 1 Investor ──────────────────────────────────────────────
    df['Tier 1 Investor'] = df.apply(
        lambda r: find_tier1(r.get('Lead/Sole Investors', ''), r.get('New Investors', '')),
        axis=1
    )

    unmatched = df[df['Tier 1 Investor'] == '']
    if len(unmatched) > 0:
        print(f"⚠ {len(unmatched)} deals with no Tier 1 match:")
        for _, row in unmatched.iterrows():
            print(f"  {row['Companies']} | Lead: {row.get('Lead/Sole Investors','')} | New: {row.get('New Investors','')}")

    # ── Fix Deal Date → YYYY-MM-DD ────────────────────────────────────────────
    df['Deal Date'] = df['Deal Date'].apply(format_date)

    # ── Fix numeric fields ────────────────────────────────────────────────────
    df['Deal Size']      = df['Deal Size'].apply(clean_number)
    df['Post Valuation'] = df['Post Valuation'].apply(clean_number)
    df['Revenue']        = df['Revenue'].apply(clean_number)

    # ── Add required Attio fields (blank — remove Required constraint in Attio)
    df['Deal Stage'] = ''
    df['Deal Owner'] = ''

    # ── Drop empty rows (trailing blanks from Excel) ─────────────────────────
    df = df.dropna(subset=['Companies'])

    # ── Reorder columns for clarity ───────────────────────────────────────────
    priority = ['Deal name', 'Companies', 'Series', 'Tier 1 Investor',
                'Deal Date', 'Deal Size', 'Post Valuation',
                'Lead/Sole Investors', 'New Investors', 'Investors',
                'Description', 'Company Website', 'HQ Location',
                'Revenue', 'Valuation/Revenue', 'Deal Stage', 'Deal Owner']
    remaining = [c for c in df.columns if c not in priority]
    df = df[priority + remaining]

    # ── Save ──────────────────────────────────────────────────────────────────
    df.to_csv(output_path, index=False)
    print(f"\n✅ Done. Saved to: {output_path}")
    print(f"   {len(df)} deals | {len(df.columns)} columns")
    print(f"   Tier 1 matched: {len(df[df['Tier 1 Investor'] != ''])} / {len(df)}")

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) == 3:
        input_file  = sys.argv[1]
        output_file = sys.argv[2]
    else:
        # Default paths for testing
        input_file  = '/sessions/kind-friendly-mendel/mnt/uploads/PitchBook_Search_Result_Columns_2026_06_09_14_34_24.xlsx'
        output_file = '/sessions/kind-friendly-mendel/mnt/outputs/pitchbook_clean.csv'

    transform(input_file, output_file)
