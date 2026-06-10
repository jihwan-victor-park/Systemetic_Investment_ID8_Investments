import pandas as pd
import re
import sys
import os
import glob
from datetime import datetime

# ── Folder structure ──────────────────────────────────────────────────────────
# Drop PitchBook .xlsx into:   ./Documents/
# Clean CSV for Attio lands in: ./attio_import/pitchbook_clean.csv

# ── 33 Tier 1 firms ───────────────────────────────────────────────────────────
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
TIER1_CLEAN = {re.sub(r'\s*\([^)]*\)', '', f).strip().lower(): f for f in TIER1_FIRMS}

# ── Columns to drop ───────────────────────────────────────────────────────────
DROP_COLS = [
    'Deal ID',
    'Primary PitchBook Industry Code',
    'View Company Online',
    'EBITDA',
    'Valuation/EBITDA',
    'Net Income',
    'Deal Type',
]

# ── Final column order matching the reference Attio import format ─────────────
ATTIO_COL_ORDER = [
    'Deal name',            # required by Attio
    'Companies',
    'Series',
    'Description',
    'Company Website',      # extracted from =HYPERLINK() formulas
    'Lead/Sole Investors',  # raw — parentheticals kept intact
    'New Investors',        # raw — parentheticals kept intact
    'Deal Size',
    'Post Valuation',
    'Revenue',
    'Valuation/Revenue',
    'Deal Date',            # YYYY-MM-DD
    'Investors',            # raw — parentheticals kept intact
    'HQ Location',
    'Tier 1 Investor',      # identified from investor columns
    'Deal Stage',           # blank — remove Required constraint in Attio
    'Deal Owner',           # blank — remove Required constraint in Attio
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def strip_parens(text):
    """Used ONLY internally for Tier 1 matching — never applied to output columns."""
    return re.sub(r'\s*\([^)]*\)', '', str(text)).strip()

def parse_investors(cell):
    """Parse investor cell, strip parens only for matching purposes."""
    if pd.isna(cell) or str(cell).strip() == '':
        return []
    return [strip_parens(p.strip()) for p in str(cell).split(',') if p.strip()]

def find_tier1(lead_cell, new_cell, all_cell):
    """Identify which Tier 1 firm appears in this deal's investors."""
    investors = (parse_investors(lead_cell) +
                 parse_investors(new_cell) +
                 parse_investors(all_cell))
    for inv in investors:
        inv_lower = inv.lower()
        if inv_lower in TIER1_CLEAN:
            return TIER1_CLEAN[inv_lower]
        for key, canonical in TIER1_CLEAN.items():
            if key in inv_lower or inv_lower in key:
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

def format_number(val):
    """Format numeric values with comma thousands separator and 2 decimal places."""
    if pd.isna(val):
        return ""
    try:
        return f"{float(val):,.2f}"
    except:
        return str(val)

def extract_hyperlink_column(input_path, header_row_0idx, col_name):
    """
    Read a column that contains =HYPERLINK() formulas (which pandas reads as NaN).
    Returns a dict of {row_position: display_url} for all data rows.
    header_row_0idx is 0-indexed (same as pandas header= argument).
    """
    import openpyxl
    wb = openpyxl.load_workbook(input_path, data_only=False)
    ws = wb.active

    xl_header_row = header_row_0idx + 1  # openpyxl is 1-indexed

    # Find column index
    col_idx = None
    for cell in ws[xl_header_row]:
        if cell.value == col_name:
            col_idx = cell.column
            break
    if col_idx is None:
        return {}

    result = {}
    data_start = xl_header_row + 1
    for xl_row in range(data_start, ws.max_row + 1):
        cell = ws.cell(row=xl_row, column=col_idx)
        val = cell.value
        if isinstance(val, str) and val.upper().startswith('=HYPERLINK('):
            # Parse: =HYPERLINK("url", "display") — grab display text (2nd arg)
            m = re.search(r'=HYPERLINK\s*\(\s*"[^"]*"\s*,\s*"([^"]*)"\s*\)', val, re.IGNORECASE)
            if m:
                result[xl_row - data_start] = m.group(1)
            else:
                # Fallback: grab first quoted string and strip http(s)://
                m2 = re.search(r'"(https?://[^"]+)"', val, re.IGNORECASE)
                if m2:
                    result[xl_row - data_start] = re.sub(r'^https?://', '', m2.group(1))
        elif val:
            result[xl_row - data_start] = str(val)
    return result

def find_latest_xlsx(folder):
    # Skip ~$ temp lock files created when Excel has a file open
    files = [f for f in glob.glob(os.path.join(folder, '*.xlsx'))
             if not os.path.basename(f).startswith('~$')]
    return max(files, key=os.path.getmtime) if files else None

# ── Main transform ────────────────────────────────────────────────────────────
def transform(input_path, output_path):
    print(f"📂 Reading: {os.path.basename(input_path)}")

    # Skip PitchBook metadata rows at top — find real header
    xl = pd.read_excel(input_path, header=None)
    header_row = next(
        (i for i, row in xl.iterrows() if 'Companies' in row.values), None
    )
    if header_row is None:
        print("ERROR: Could not find header row with 'Companies' column.")
        sys.exit(1)

    df = pd.read_excel(input_path, header=header_row)
    df = df.dropna(subset=['Companies'])
    print(f"   {len(df)} deals found")

    # Fix Company Website: PitchBook exports these as =HYPERLINK() formulas
    # which pandas reads as NaN — extract the display URL with openpyxl
    if 'Company Website' in df.columns:
        hyperlinks = extract_hyperlink_column(input_path, header_row, 'Company Website')
        if hyperlinks:
            # Cast column to object so string assignment doesn't trigger dtype warning
            df['Company Website'] = df['Company Website'].astype(object)
            for pos, url in hyperlinks.items():
                if pos < len(df):
                    df.iloc[pos, df.columns.get_loc('Company Website')] = url

    # Drop unwanted PitchBook columns
    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])

    # Deal name (required by Attio): "Company — Series"
    series_val = df['Series'].astype(str) if 'Series' in df.columns else ''
    df['Deal name'] = df['Companies'].astype(str)

    # Tier 1 Investor — strip parens only for matching, output is clean firm name
    lead = df.get('Lead/Sole Investors', pd.Series([''] * len(df), index=df.index))
    new  = df.get('New Investors',       pd.Series([''] * len(df), index=df.index))
    all_ = df.get('Investors',           pd.Series([''] * len(df), index=df.index))

    df['Tier 1 Investor'] = [
        find_tier1(lead.iloc[i], new.iloc[i], all_.iloc[i])
        for i in range(len(df))
    ]

    unmatched = df[df['Tier 1 Investor'] == '']
    if len(unmatched):
        print(f"⚠  {len(unmatched)} deals with no Tier 1 match:")
        for _, row in unmatched.iterrows():
            print(f"   • {row['Companies']}")

    # Format numeric columns to match reference: comma thousands + 2 decimal places
    for num_col in ['Deal Size', 'Post Valuation', 'Revenue', 'Valuation/Revenue']:
        if num_col in df.columns:
            df[num_col] = df[num_col].apply(format_number)

    # Fix Deal Date to YYYY-MM-DD (only transformation needed for Attio)
    if 'Deal Date' in df.columns:
        df['Deal Date'] = df['Deal Date'].apply(format_date)

    # Ensure Description exists (some exports omit it)
    if 'Description' not in df.columns:
        df['Description'] = ''

    # Add required-but-blank Attio fields
    df['Deal Stage'] = ''
    df['Deal Owner'] = ''

    # Reorder columns to match Attio import format
    ordered = [c for c in ATTIO_COL_ORDER if c in df.columns]
    extras  = [c for c in df.columns if c not in ATTIO_COL_ORDER]
    df = df[ordered + extras]

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"\n✅ Saved → attio_import/pitchbook_clean.csv")
    print(f"   {len(df)} deals | Tier 1 matched: {len(df[df['Tier 1 Investor'] != ''])} / {len(df)}")

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    script_dir    = os.path.dirname(os.path.abspath(__file__))
    documents_dir = os.path.join(script_dir, 'Documents')
    output_dir    = os.path.join(script_dir, 'attio_import')

    if len(sys.argv) == 3:
        input_file, output_file = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 2:
        input_file  = sys.argv[1]
        output_file = os.path.join(output_dir, 'pitchbook_clean.csv')
    else:
        input_file = find_latest_xlsx(documents_dir)
        if not input_file:
            print("❌  No .xlsx files found in Documents/")
            print("   Drop your PitchBook Excel into the Documents folder and re-run.")
            sys.exit(1)
        output_file = os.path.join(output_dir, 'pitchbook_clean.csv')
        print(f"   Auto-detected: {os.path.basename(input_file)}")

    transform(input_file, output_file)
