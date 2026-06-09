import os
import re
import io
import requests
import pandas as pd
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# ── Config (set these as Environment Variables in Render) ─────────────────────
ATTIO_API_KEY   = os.environ.get("ATTIO_API_KEY", "")
ATTIO_API_BASE  = "https://api.attio.com/v2"

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

# ── Helpers ───────────────────────────────────────────────────────────────────
def strip_parens(text):
    return re.sub(r'\s*\([^)]*\)', '', str(text)).strip()

def parse_investors(cell):
    if pd.isna(cell) or str(cell).strip() == '':
        return []
    return [strip_parens(p.strip()) for p in str(cell).split(',') if p.strip()]

def find_tier1(lead_cell, new_cell):
    for inv in parse_investors(lead_cell) + parse_investors(new_cell):
        inv_lower = inv.lower()
        if inv_lower in TIER1_CLEAN:
            return TIER1_CLEAN[inv_lower]
        for key, canonical in TIER1_CLEAN.items():
            if key in inv_lower or inv_lower in key:
                return canonical
    return ""

def format_date(val):
    if pd.isna(val):
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    try:
        return pd.to_datetime(str(val)).strftime("%Y-%m-%d")
    except:
        return str(val)

def clean_number(val):
    if pd.isna(val):
        return None
    try:
        return float(str(val).replace(',', '').replace('$', '').strip())
    except:
        return None

def transform_excel(file_bytes):
    """Transform raw PitchBook Excel bytes into a clean DataFrame."""
    xl = pd.read_excel(io.BytesIO(file_bytes), header=None)

    # Find real header row
    header_row = next(
        (i for i, row in xl.iterrows() if 'Companies' in row.values), None
    )
    if header_row is None:
        raise ValueError("Could not find header row with 'Companies' column")

    df = pd.read_excel(io.BytesIO(file_bytes), header=header_row)
    df = df.dropna(subset=['Companies'])

    # Drop unwanted columns
    df = df.drop(columns=[c for c in
        ['Deal ID', 'Primary PitchBook Industry Code', 'View Company Online']
        if c in df.columns])

    df['Deal name']       = df['Companies'].astype(str) + ' — ' + df['Series'].astype(str)
    df['Tier 1 Investor'] = df.apply(
        lambda r: find_tier1(r.get('Lead/Sole Investors', ''), r.get('New Investors', '')), axis=1
    )
    df['Deal Date']       = df['Deal Date'].apply(format_date)
    df['Deal Size']       = df['Deal Size'].apply(clean_number)
    df['Post Valuation']  = df['Post Valuation'].apply(clean_number)
    df['Revenue']         = df['Revenue'].apply(clean_number)

    return df

def attio_headers():
    return {
        "Authorization": f"Bearer {ATTIO_API_KEY}",
        "Content-Type": "application/json"
    }

def find_company_by_domain(domain):
    """Search Attio Companies by domain, return record_id or None."""
    domain = domain.replace("https://", "").replace("http://", "").replace("www.", "").strip("/").lower()
    resp = requests.post(
        f"{ATTIO_API_BASE}/objects/companies/records/query",
        headers=attio_headers(),
        json={"filter": {"domains": {"domain": {"$eq": domain}}}, "limit": 1}
    )
    data = resp.json().get("data", [])
    return data[0]["id"]["record_id"] if data else None

def find_deal_by_name(deal_name):
    """Check if a Deal with this name already exists (dedup)."""
    resp = requests.post(
        f"{ATTIO_API_BASE}/objects/deals/records/query",
        headers=attio_headers(),
        json={"filter": {"name": {"$eq": deal_name}}, "limit": 1}
    )
    data = resp.json().get("data", [])
    return data[0]["id"]["record_id"] if data else None

def upsert_deal(row, company_record_id):
    """Create deal in Attio if it doesn't already exist."""
    deal_name = row["Deal name"]

    # Skip if deal already exists
    if find_deal_by_name(deal_name):
        return "skipped"

    values = {
        "name": [{"value": deal_name}],
    }
    if row.get("Deal Date"):
        values["deal_date"] = [{"value": row["Deal Date"]}]
    if row.get("Deal Size"):
        values["deal_size"] = [{"value": row["Deal Size"]}]
    if row.get("Post Valuation"):
        values["post_valuation"] = [{"value": row["Post Valuation"]}]
    if row.get("Series"):
        values["series"] = [{"option": str(row["Series"])}]
    if row.get("Tier 1 Investor"):
        values["tier_1_investor_name"] = [{"value": row["Tier 1 Investor"]}]

    if company_record_id:
        values["associated_company"] = [{"target_object": "companies", "target_record_id": company_record_id}]

    resp = requests.post(
        f"{ATTIO_API_BASE}/objects/deals/records",
        headers=attio_headers(),
        json={"data": {"values": values}}
    )
    return "created" if resp.status_code in (200, 201) else f"error:{resp.status_code}:{resp.text[:200]}"

# ── Route ─────────────────────────────────────────────────────────────────────
@app.route("/process", methods=["POST"])
def process():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Send as multipart form field 'file'."}), 400

    file_bytes = request.files["file"].read()

    try:
        df = transform_excel(file_bytes)
    except Exception as e:
        return jsonify({"error": f"Transform failed: {str(e)}"}), 500

    results = {"created": 0, "skipped": 0, "errors": []}

    for _, row in df.iterrows():
        website = str(row.get("Company Website", "") or "")
        company_id = find_company_by_domain(website) if website else None
        status = upsert_deal(row.to_dict(), company_id)

        if status == "created":
            results["created"] += 1
        elif status == "skipped":
            results["skipped"] += 1
        else:
            results["errors"].append({"deal": row["Deal name"], "error": status})

    return jsonify({
        "status": "done",
        "created": results["created"],
        "skipped": results["skipped"],
        "errors": results["errors"]
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
