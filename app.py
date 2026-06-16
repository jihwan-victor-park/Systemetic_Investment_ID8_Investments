import os
import re
import io
import unicodedata
import traceback
import requests
import pandas as pd
import openpyxl
from flask import Flask, request, jsonify, send_file, send_file
from datetime import datetime

app = Flask(__name__)

ATTIO_API_KEY  = os.environ.get("ATTIO_API_KEY", "")
ATTIO_API_BASE = "https://api.attio.com/v2"

DROP_COLS = [
    'Deal ID', 'Primary PitchBook Industry Code', 'View Company Online',
    'EBITDA', 'Valuation/EBITDA', 'Net Income', 'Deal Type', 'Deal Owner',
]

# Attio field mapping (CSV column -> API slug + type)
FIELD_MAP = {
    'Series':              ('series',           'select'),
    'Description':         ('description',      'text'),
    'Lead/Sole Investors': ('lead_investors',    'text'),
    'New Investors':       ('new_investors_7',   'text'),
    'Deal Size':           ('deal_size',         'currency'),
    'Post Valuation':      ('post_valuation',    'currency'),
    'Revenue':             ('revenue',           'currency'),
    'Valuation/Revenue':   ('valuation_revenue', 'number'),
    'Deal Date':           ('deal_date',         'date'),
    'Investors':           ('investors',         'text'),
    'HQ Location':         ('location',          'text'),
}

# Investor text column -> record-reference slug on the Deals object.
# These link each matched VC firm to its Companies record (clickable on the deal).
# CONFIRM these slugs against GET /debug/attributes after creating the attributes
# in the Attio UI (Record reference -> Companies, allow multiple values).
INVESTOR_REF_MAP = {
    'Lead/Sole Investors': 'lead_investors_8',
    'New Investors':       'new_investors_5',
    'Investors':           'investors_5',   # full list incl. follow-on investors
}

# Top 10 VC workflow: select attribute (Yes/No) stamped on those deals, and the
# stage new deals default to (must exist as a status on the Deal stage field).
TOP10_VC_SLUG = 'top_10_vc'
RADAR_STAGE   = 'Radar'


# --- Helpers ------------------------------------------------------------------

def attio_headers():
    return {
        "Authorization": f"Bearer {ATTIO_API_KEY}",
        "Content-Type": "application/json",
    }

def clean_number(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(str(val).replace(',', '').replace('$', '').strip())
    except:
        return None

# PitchBook (and Jesse) money values arrive expressed in $millions:
#   400 -> $400,000,000   |   44000 -> $44,000,000,000   |   1163.11 -> $1,163,110,000
# Currency fields are scaled by this factor before being stored in Attio.
MILLION = 1_000_000

def _trim(x):
    """Format a float with up to 2 decimals, dropping trailing zeros (1.50 -> '1.5', 400.00 -> '400')."""
    return f"{x:.2f}".rstrip("0").rstrip(".")

def fmt_money_millions(val):
    """Format a value expressed in $millions as a readable string for the email.
    400 -> '$400M', 2000 -> '$2B', 1163.11 -> '$1.16B', 35 -> '$35M'."""
    num = clean_number(val)
    if num is None:
        return ""
    if num >= 1000:
        return f"${_trim(num / 1000)}B"
    return f"${_trim(num)}M"

def format_date(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    try:
        return pd.to_datetime(str(val)).strftime("%Y-%m-%d")
    except:
        return None

# --- Investor parsing / matching ----------------------------------------------

_LEGAL_SUFFIXES = {
    'inc', 'incorporated', 'llc', 'llp', 'ltd', 'limited', 'lp',
    'corp', 'corporation', 'plc', 'gmbh', 'ag', 'sa',
}

def normalize_company_name(name):
    """Build a loose match key for a company/VC name.
    'Nokia (HEL: NOKIA)' -> 'nokia'; "Ontario Teachers' Pension Plan" ->
    'ontario teachers pension plan'; 'Accel Inc.' -> 'accel'."""
    if not name:
        return ""
    s = str(name).lower()
    s = ''.join(c for c in unicodedata.normalize('NFKD', s)
                if not unicodedata.combining(c))   # fold accents: é -> e
    s = re.sub(r'\([^)]*\)', ' ', s)        # drop all parenthetical groups
    s = s.replace('&', ' and ')
    s = re.sub(r'[^a-z0-9 ]', ' ', s)       # strip punctuation/apostrophes/accents
    tokens = [t for t in s.split() if t and t not in _LEGAL_SUFFIXES]
    if tokens and tokens[0] == 'the':
        tokens = tokens[1:]
    return ' '.join(tokens)

def _clean_domain(domain):
    """Reduce a raw URL/domain to a bare host: 'www.tesi.fi/en' -> 'tesi.fi'."""
    if not domain:
        return ""
    d = re.sub(r'^https?://', '', str(domain).strip(), flags=re.IGNORECASE)
    d = d.replace('www.', '').strip().strip('/').lower()
    d = d.split('/')[0]                     # drop any path
    return d

def parse_investors(raw):
    """Split an investor cell into firm names, stripping glued '(Partner)' names.
    'GIC Private(Yong Cheen Choo), ICONIQ Growth' -> ['GIC Private', 'ICONIQ Growth'].
    Keeps spaced parentheticals that are part of the name ('Insight Partners (New York)')."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    s = str(raw).strip()
    if not s or s.lower() in ('nan', 'none'):
        return []
    s = re.sub(r'(?<=\S)\([^)]*\)', '', s)  # remove parens glued on with no leading space
    return [p.strip() for p in s.split(',') if p.strip()]

def parse_investor_websites(cell):
    """Parse PitchBook's 'Investors Websites' cell into {normalized_name -> domain}.
    'General Atlantic (www.generalatlantic.com), Nokia (HEL: NOKIA) (www.nokia.com)'
    -> {'general atlantic': 'generalatlantic.com', 'nokia': 'nokia.com'}."""
    out = {}
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return out
    s = str(cell).strip()
    if not s or s.lower() in ('nan', 'none'):
        return out
    for item in s.split(','):
        item = item.strip()
        if not item:
            continue
        # the trailing (...) is the domain; everything before it is the name
        m = re.match(r'^(.*)\s+\(([^)]*)\)\s*$', item)
        if not m:
            continue
        name, domain = m.group(1).strip(), _clean_domain(m.group(2))
        key = normalize_company_name(name)
        if key and domain:
            out.setdefault(key, domain)
    return out

def extract_hyperlinks(file_bytes, header_row_0idx, col_name):
    """Extract =HYPERLINK() formula display values from an Excel column."""
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=False)
    ws = wb.active
    xl_header = header_row_0idx + 1
    col_idx = None
    for cell in ws[xl_header]:
        if cell.value == col_name:
            col_idx = cell.column
            break
    if col_idx is None:
        return {}
    result = {}
    data_start = xl_header + 1
    for xl_row in range(data_start, ws.max_row + 1):
        cell = ws.cell(row=xl_row, column=col_idx)
        val = cell.value
        if isinstance(val, str) and val.upper().startswith('=HYPERLINK('):
            m = re.search(r'=HYPERLINK\s*\(\s*"[^"]*"\s*,\s*"([^"]*)"\s*\)', val, re.IGNORECASE)
            if m:
                result[xl_row - data_start] = m.group(1)
            else:
                m2 = re.search(r'"(https?://[^"]+)"', val, re.IGNORECASE)
                if m2:
                    result[xl_row - data_start] = re.sub(r'^https?://', '', m2.group(1))
        elif val:
            result[xl_row - data_start] = str(val)
    return result


# --- Transform ----------------------------------------------------------------

def transform_excel(file_bytes):
    xl = pd.read_excel(io.BytesIO(file_bytes), header=None)
    header_row = next(
        (i for i, row in xl.iterrows() if 'Companies' in row.values), None
    )
    if header_row is None:
        raise ValueError("Could not find header row with 'Companies' column")

    df = pd.read_excel(io.BytesIO(file_bytes), header=header_row)
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=['Companies'])
    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])

    if 'Company Website' in df.columns:
        hyperlinks = extract_hyperlinks(file_bytes, header_row, 'Company Website')
        if hyperlinks:
            df['Company Website'] = df['Company Website'].astype(object)
            for pos, url in hyperlinks.items():
                if pos < len(df):
                    df.iloc[pos, df.columns.get_loc('Company Website')] = url

    return df


# --- Attio API ----------------------------------------------------------------

_select_option_cache = {}  # (object_slug, attribute_slug) -> set of existing option titles

def ensure_select_option(object_slug, attribute_slug, option_title):
    """Make sure a select option exists on an Attio attribute; create it if missing.

    Attio rejects a write referencing an unknown select option, so when PitchBook
    sends e.g. 'Series A2' (not yet in the picklist) we create the option first.
    """
    if not option_title:
        return
    key = (object_slug, attribute_slug)
    titles = _select_option_cache.get(key)
    if titles is None:
        resp = requests.get(
            f"{ATTIO_API_BASE}/objects/{object_slug}/attributes/{attribute_slug}/options",
            headers=attio_headers(),
        )
        titles = set()
        if resp.status_code == 200:
            for opt in resp.json().get("data", []):
                t = opt.get("title")
                if t:
                    titles.add(t)
        _select_option_cache[key] = titles

    if option_title in titles:
        return

    resp = requests.post(
        f"{ATTIO_API_BASE}/objects/{object_slug}/attributes/{attribute_slug}/options",
        headers=attio_headers(),
        json={"data": {"title": option_title}},
    )
    print(f"OPTION CREATE {object_slug}.{attribute_slug} '{option_title}': "
          f"{resp.status_code} {resp.text[:200]}")
    if resp.status_code in (200, 201):
        titles.add(option_title)

_company_index = None  # {"by_name": {normalized_name: id}, "by_domain": {domain: id}}

def get_company_index(refresh=False):
    """Build {normalized_name -> id} and {domain -> id} maps over all Companies.

    Used for link-only investor matching — we never create from here. Cached for the
    process; pass refresh=True at the start of a run to pick up newly-created companies.
    """
    global _company_index
    if _company_index is not None and not refresh:
        return _company_index

    by_name, by_domain = {}, {}
    offset, limit = 0, 500
    while True:
        resp = requests.post(
            f"{ATTIO_API_BASE}/objects/companies/records/query",
            headers=attio_headers(),
            json={"limit": limit, "offset": offset},
        )
        if resp.status_code != 200:
            print(f"COMPANY INDEX query failed: {resp.status_code} {resp.text[:200]}")
            break
        batch = resp.json().get("data", [])
        for rec in batch:
            rid = rec["id"]["record_id"]
            vals = rec.get("values", {})
            for nm in vals.get("name", []):
                key = normalize_company_name(nm.get("value"))
                if key:
                    by_name.setdefault(key, rid)
            for dm in vals.get("domains", []):
                d = _clean_domain(dm.get("domain"))
                if d:
                    by_domain.setdefault(d, rid)
        if len(batch) < limit:
            break
        offset += limit

    _company_index = {"by_name": by_name, "by_domain": by_domain}
    print(f"COMPANY INDEX built: {len(by_name)} names, {len(by_domain)} domains")
    return _company_index

def resolve_investor_links(row, index):
    """Resolve the Lead/New/Investors text columns to record-reference values.

    Matches each investor to an existing Companies record by domain first (from the
    'Investors Websites' column) then by normalized name. Link-only: unmatched names
    are skipped. Returns {ref_slug: [{target_object, target_record_id}, ...]}.
    """
    name_to_domain = parse_investor_websites(row.get('Investors Websites'))
    by_name, by_domain = index["by_name"], index["by_domain"]

    out = {}
    for csv_col, ref_slug in INVESTOR_REF_MAP.items():
        ids = []
        for nm in parse_investors(row.get(csv_col)):
            key = normalize_company_name(nm)
            rid = by_domain.get(name_to_domain.get(key, '')) or by_name.get(key)
            if rid and rid not in ids:
                ids.append(rid)
        if ids:
            out[ref_slug] = [
                {"target_object": "companies", "target_record_id": rid} for rid in ids
            ]
    return out

def find_or_create_company(company_name, domain, description=None):
    """Find company by domain; create it if not found. Returns record_id or None."""
    if not domain or domain == 'nan':
        return None
    clean_domain = re.sub(r'^https?://', '', str(domain)).replace('www.', '').strip('/').lower()

    resp = requests.post(
        f"{ATTIO_API_BASE}/objects/companies/records/query",
        headers=attio_headers(),
        json={"filter": {"domains": {"domain": {"$eq": clean_domain}}}, "limit": 1},
    )
    data = resp.json().get("data", [])
    if data:
        return data[0]["id"]["record_id"]

    company_values = {
        "name": [{"value": company_name}],
        "domains": [{"domain": clean_domain}],
    }
    if description and str(description).strip() and str(description).strip() != 'nan':
        company_values["description"] = [{"value": str(description).strip()}]

    resp = requests.post(
        f"{ATTIO_API_BASE}/objects/companies/records",
        headers=attio_headers(),
        json={"data": {"values": company_values}},
    )
    print(f"COMPANY CREATE {company_name}: {resp.status_code} {resp.text[:200]}")
    if resp.status_code not in (200, 201):
        return None
    return resp.json().get("data", {}).get("id", {}).get("record_id")

def find_deal(company_name, series):
    """Return existing deal record_id if this company+series already exists."""
    resp = requests.post(
        f"{ATTIO_API_BASE}/objects/deals/records/query",
        headers=attio_headers(),
        json={
            "filter": {
                "$and": [
                    {"name": {"$eq": company_name}},
                    {"series": {"$eq": series}},
                ]
            },
            "limit": 1,
        },
    )
    data = resp.json().get("data", [])
    return data[0]["id"]["record_id"] if data else None

def patch_deal_company(deal_record_id, company_record_id):
    """Patch an existing deal to set associated_company if missing."""
    requests.patch(
        f"{ATTIO_API_BASE}/objects/deals/records/{deal_record_id}",
        headers=attio_headers(),
        json={"data": {"values": {
            "associated_company": [{
                "target_object": "companies",
                "target_record_id": company_record_id,
            }]
        }}},
    )

def build_attio_values(row, company_record_id, stage="Watchlist", source=None, top10=False):
    """Build the Attio API values dict from a DataFrame row."""
    company_name = str(row.get('Companies', '')).strip()
    values = {
        "name": [{"value": company_name}],
        "stage": [{"status": stage}],
    }
    if source:
        values["source"] = [{"value": source}]
    if top10:
        ensure_select_option('deals', TOP10_VC_SLUG, 'Yes')
        values[TOP10_VC_SLUG] = "Yes"   # single-select: write the option title as a string

    for csv_col, (slug, field_type) in FIELD_MAP.items():
        val = row.get(csv_col)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        val_str = str(val).strip()
        if not val_str or val_str == 'nan':
            continue

        if field_type == 'text':
            values[slug] = [{"value": val_str}]
        elif field_type == 'select':
            ensure_select_option('deals', slug, val_str)
            values[slug] = val_str   # single-select: option title as a string
        elif field_type == 'currency':
            # Source value is in $millions -> store the real amount in Attio.
            num = clean_number(val)
            if num is not None:
                values[slug] = [{"currency_value": num * MILLION}]
        elif field_type == 'number':
            num = clean_number(val)
            if num is not None:
                values[slug] = [{"value": num}]
        elif field_type == 'date':
            date_str = format_date(val)
            if date_str:
                values[slug] = [{"value": date_str}]

    # Link investor firms to their Companies records (clickable on the deal).
    values.update(resolve_investor_links(row, get_company_index()))

    if company_record_id:
        values["associated_company"] = [{
            "target_object": "companies",
            "target_record_id": company_record_id,
        }]

    return values

def upsert_deal(row, company_record_id, stage="Watchlist", source=None, top10=False):
    company_name = str(row.get('Companies', '')).strip()
    series = str(row.get('Series', '')).strip()

    existing_id = find_deal(company_name, series)
    if existing_id:
        # Existing deal: never change its stage. For the Top 10 VC flow, stamp the
        # flag and (re)link investors; otherwise just backfill the associated company.
        patch_vals = {}
        if top10:
            ensure_select_option('deals', TOP10_VC_SLUG, 'Yes')
            patch_vals[TOP10_VC_SLUG] = "Yes"
            patch_vals.update(resolve_investor_links(row, get_company_index()))
        if company_record_id:
            patch_vals["associated_company"] = [{
                "target_object": "companies", "target_record_id": company_record_id,
            }]
        if patch_vals:
            requests.patch(
                f"{ATTIO_API_BASE}/objects/deals/records/{existing_id}",
                headers=attio_headers(),
                json={"data": {"values": patch_vals}},
            )
        return "skipped"

    values = build_attio_values(row, company_record_id, stage, source, top10)
    resp = requests.post(
        f"{ATTIO_API_BASE}/objects/deals/records",
        headers=attio_headers(),
        json={"data": {"values": values}},
    )
    if resp.status_code in (200, 201):
        record_id = resp.json().get("data", {}).get("id", {}).get("record_id", "")
        return {"status": "created", "record_id": record_id}
    return f"error:{resp.status_code}:{resp.text[:300]}"


# --- Shared pipeline logic ----------------------------------------------------

def run_pipeline(file_bytes, stage, source=None, top10=False):
    df = transform_excel(file_bytes)
    get_company_index(refresh=True)   # fresh Companies snapshot for investor matching
    results = {"created": 0, "skipped": 0, "errors": [], "deals": []}

    def clean(val):
        s = str(val or "").strip()
        return "" if s.lower() in ("nan", "none") else s

    for _, row in df.iterrows():
        website = str(row.get("Company Website", "") or "")
        company_name = str(row.get("Companies", "")).strip()
        description = clean(row.get("Description", ""))
        company_id = find_or_create_company(company_name, website, description) if website and website != 'nan' else None
        status = upsert_deal(row.to_dict(), company_id, stage, source, top10)

        if isinstance(status, dict) and status.get("status") == "created":
            results["created"] += 1
            results["deals"].append({
                "company":        company_name,
                "series":         clean(row.get("Series")),
                "deal_size":      fmt_money_millions(row.get("Deal Size")),
                "post_valuation": fmt_money_millions(row.get("Post Valuation")),
                "revenue":        fmt_money_millions(row.get("Revenue")),
                "description":    description,
                "lead_investors": clean(row.get("Lead/Sole Investors")),
                "new_investors":  clean(row.get("New Investors")),
                "investors":      clean(row.get("Investors")),
                "hq_location":    clean(row.get("HQ Location")),
                "deal_date":      format_date(row.get("Deal Date")) or "",
                "website":        website,
                "record_id":      status.get("record_id", ""),
            })
        elif status == "skipped":
            results["skipped"] += 1
        else:
            results["errors"].append({"deal": company_name, "error": status})

    return results


def _read_file_bytes():
    if "file" in request.files:
        return request.files["file"].read(), None
    if request.data:
        return request.data, None
    return None, (jsonify({"error": "No file received."}), 400)


# --- Routes ------------------------------------------------------------------

@app.route("/process", methods=["POST"])
def process():
    file_bytes, err = _read_file_bytes()
    if err:
        return err
    try:
        results = run_pipeline(file_bytes, stage="Qualified", source="ID8 Investments")
    except Exception as e:
        print("TRANSFORM ERROR:", traceback.format_exc())
        return jsonify({"error": f"Transform failed: {str(e)}"}), 500
    return jsonify({"status": "done", **results})


@app.route("/process-watchlist", methods=["POST"])
def process_watchlist():
    file_bytes, err = _read_file_bytes()
    if err:
        return err
    try:
        results = run_pipeline(file_bytes, stage="Watchlist", source="ID8 Investments")
    except Exception as e:
        print("TRANSFORM ERROR:", traceback.format_exc())
        return jsonify({"error": f"Transform failed: {str(e)}"}), 500
    return jsonify({"status": "done", **results})

@app.route("/process-top10", methods=["POST"])
def process_top10():
    """Top 10 VC weekly flow: tag deals Top 10 VC = Yes; new deals default to the
    Radar stage; existing deals keep their stage (only flag + investor links updated)."""
    file_bytes, err = _read_file_bytes()
    if err:
        return err
    try:
        results = run_pipeline(file_bytes, stage=RADAR_STAGE, source="ID8 Investments", top10=True)
    except Exception as e:
        print("TRANSFORM ERROR:", traceback.format_exc())
        return jsonify({"error": f"Transform failed: {str(e)}"}), 500
    return jsonify({"status": "done", **results})

@app.route("/process-jesse", methods=["POST"])
def process_jesse():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON received."}), 400

    def clean(val):
        s = str(val or "").strip()
        return "" if s.lower() in ("nan", "none") else s

    company_name = clean(data.get("Company", ""))
    if not company_name:
        return jsonify({"error": "Company name is required."}), 400

    series = clean(data.get("Round", ""))
    if not series:
        return jsonify({"error": "Round is required."}), 400

    website     = clean(data.get("Company Website", ""))
    description = clean(data.get("Description", ""))

    row = {
        "Companies":           company_name,
        "Company Website":     website,
        "Description":         description,
        "Series":              series,
        "Deal Size":           data.get("Deal Size"),
        "Post Valuation":      data.get("Post Valuation"),
        "Revenue":             data.get("Revenue"),
        "Deal Date":           data.get("Date"),
        "Lead/Sole Investors": clean(data.get("Lead Investor", "")),
        "New Investors":       clean(data.get("New Investors", "")),
    }

    company_id = find_or_create_company(company_name, website, description) if website else None
    status = upsert_deal(row, company_id, stage="Watchlist", source="Jesse Bloom")

    # Patch Round Live (Access) separately — it's a select on the deal record
    if isinstance(status, dict) and status.get("status") == "created" and data.get("Access") is True:
        requests.patch(
            f"{ATTIO_API_BASE}/objects/deals/records/{status['record_id']}",
            headers=attio_headers(),
            json={"data": {"values": {"round_live": "Round Live"}}},
        )

    if isinstance(status, dict) and status.get("status") == "created":
        return jsonify({
            "status": "done",
            "created": 1,
            "skipped": 0,
            "errors": [],
            "deals": [{
                "company":        company_name,
                "series":         series,
                "deal_size":      fmt_money_millions(data.get("Deal Size")),
                "post_valuation": fmt_money_millions(data.get("Post Valuation")),
                "revenue":        fmt_money_millions(data.get("Revenue")),
                "description":    description,
                "lead_investors": clean(data.get("Lead Investor", "")),
                "new_investors":  clean(data.get("New Investors", "")),
                "investors":      "",
                "hq_location":    "",
                "deal_date":      format_date(data.get("Date")) or "",
                "website":        website,
                "record_id":      status.get("record_id", ""),
            }],
        })
    elif status == "skipped":
        return jsonify({"status": "done", "created": 0, "skipped": 1, "errors": [], "deals": []})
    else:
        return jsonify({"status": "done", "created": 0, "skipped": 0,
                        "errors": [{"deal": company_name, "error": status}], "deals": []})


@app.route("/logo", methods=["GET"])
def logo():
    """Serve the ID8 logo for email headers."""
    path = os.path.join(os.path.dirname(__file__), "logo.png")
    if not os.path.exists(path):
        return jsonify({"error": "logo.png not found"}), 404
    return send_file(path, mimetype="image/png")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/debug/attributes", methods=["GET"])
def debug_attributes():
    """List all Deals object attribute slugs — use to verify field names match."""
    resp = requests.get(f"{ATTIO_API_BASE}/objects/deals", headers=attio_headers())
    if resp.status_code != 200:
        return jsonify({"error": resp.text}), resp.status_code
    attrs = resp.json().get("data", {}).get("attributes", [])
    return jsonify([{"slug": a["api_slug"], "name": a["title"], "type": a["type"]} for a in attrs])


@app.route("/backfill-investors", methods=["POST"])
def backfill_investors(): 
    """One-time pass: link investors on deals already in Attio.

    Reads each deal's stored investor *text* fields, matches names to Companies
    (by normalized name — no domains stored on existing deals), and PATCHes the
    record-reference attributes. Link-only; nothing is created.
    """
    index = get_company_index(refresh=True)
    # CSV column -> (text slug to read, reference slug to write)
    cols = {c: (FIELD_MAP[c][0], INVESTOR_REF_MAP[c]) for c in INVESTOR_REF_MAP}

    scanned = updated = links = 0
    errors = []
    offset, limit = 0, 500
    while True:
        resp = requests.post(
            f"{ATTIO_API_BASE}/objects/deals/records/query",
            headers=attio_headers(),
            json={"limit": limit, "offset": offset},
        )
        if resp.status_code != 200:
            return jsonify({"error": resp.text}), resp.status_code
        batch = resp.json().get("data", [])
        for rec in batch:
            scanned += 1
            rid = rec["id"]["record_id"]
            vals = rec.get("values", {})
            row = {}
            for csv_col, (text_slug, _ref) in cols.items():
                tv = vals.get(text_slug, [])
                row[csv_col] = tv[0].get("value") if tv else ""
            ref_values = resolve_investor_links(row, index)
            if not ref_values:
                continue
            r = requests.patch(
                f"{ATTIO_API_BASE}/objects/deals/records/{rid}",
                headers=attio_headers(),
                json={"data": {"values": ref_values}},
            )
            if r.status_code in (200, 201):
                updated += 1
                links += sum(len(v) for v in ref_values.values())
            else:
                errors.append({"deal": rid, "error": f"{r.status_code}:{r.text[:200]}"})
        if len(batch) < limit:
            break
        offset += limit

    return jsonify({"status": "done", "scanned": scanned, "updated": updated,
                    "links": links, "errors": errors})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
