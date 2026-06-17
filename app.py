import os
import re
import io
import threading
import traceback
import requests
import pandas as pd
import openpyxl
from flask import Flask, request, jsonify, send_file, send_file, make_response
from datetime import datetime

# Standalone weekly Attio → Apollo sync (single flat file, no outreach/ package)
from attio_apollo_sync import run as _run_attio_apollo_sync

app = Flask(__name__)

# In-memory status for the weekly sync (survives until the process restarts)
_sync_state = {"status": "idle", "started_at": None, "finished_at": None, "error": None}
_sync_lock  = threading.Lock()


def _sync_thread():
    try:
        _run_attio_apollo_sync()
        with _sync_lock:
            _sync_state.update({"status": "complete",
                                "finished_at": datetime.utcnow().isoformat(),
                                "error": None})
    except BaseException as exc:  # catches SystemExit from missing env vars too
        with _sync_lock:
            _sync_state.update({"status": "error",
                                "finished_at": datetime.utcnow().isoformat(),
                                "error": str(exc)})


def start_sync():
    with _sync_lock:
        if _sync_state["status"] == "running":
            return False, "Sync already running"
        _sync_state.update({"status": "running",
                            "started_at": datetime.utcnow().isoformat(),
                            "finished_at": None, "error": None})
    threading.Thread(target=_sync_thread, daemon=True).start()
    return True, "Sync started"


def get_sync_status():
    with _sync_lock:
        return dict(_sync_state)

ATTIO_API_KEY  = os.environ.get("ATTIO_API_KEY", "")
ATTIO_API_BASE = "https://api.attio.com/v2"
CRON_SECRET    = os.environ.get("CRON_SECRET", "")

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


# --- Helpers ------------------------------------------------------------------

def _has_new_investors(row: dict) -> bool:
    """True when the New Investors field is populated for this deal."""
    val = str(row.get("New Investors", "") or "").strip()
    return bool(val and val.lower() not in ("nan", "none", ""))


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

def format_date(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    try:
        return pd.to_datetime(str(val)).strftime("%Y-%m-%d")
    except:
        return None

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

def build_attio_values(row, company_record_id, stage="Watchlist", source=None):
    """Build the Attio API values dict from a DataFrame row."""
    company_name = str(row.get('Companies', '')).strip()
    values = {
        "name": [{"value": company_name}],
        "stage": [{"status": stage}],
    }
    if source:
        values["source"] = [{"value": source}]

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
            values[slug] = [{"option": val_str}]
        elif field_type == 'currency':
            num = clean_number(val)
            if num is not None:
                values[slug] = [{"currency_value": num}]
        elif field_type == 'number':
            num = clean_number(val)
            if num is not None:
                values[slug] = [{"value": num}]
        elif field_type == 'date':
            date_str = format_date(val)
            if date_str:
                values[slug] = [{"value": date_str}]

    if company_record_id:
        values["associated_company"] = [{
            "target_object": "companies",
            "target_record_id": company_record_id,
        }]

    return values

def upsert_deal(row, company_record_id, stage="Watchlist", source=None):
    company_name = str(row.get('Companies', '')).strip()
    series = str(row.get('Series', '')).strip()

    existing_id = find_deal(company_name, series)
    if existing_id:
        if company_record_id:
            patch_deal_company(existing_id, company_record_id)
        return "skipped"

    values = build_attio_values(row, company_record_id, stage, source)
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

def run_pipeline(file_bytes, stage, source=None):
    df = transform_excel(file_bytes)
    results = {"created": 0, "skipped": 0, "errors": [], "deals": []}

    def clean(val):
        s = str(val or "").strip()
        return "" if s.lower() in ("nan", "none") else s

    for _, row in df.iterrows():
        website = str(row.get("Company Website", "") or "")
        company_name = str(row.get("Companies", "")).strip()
        description = clean(row.get("Description", ""))
        company_id = find_or_create_company(company_name, website, description) if website and website != 'nan' else None
        effective_stage = "Radar" if _has_new_investors(row.to_dict()) else stage
        status = upsert_deal(row.to_dict(), company_id, effective_stage, source)

        if isinstance(status, dict) and status.get("status") == "created":
            results["created"] += 1
            results["deals"].append({
                "company":        company_name,
                "series":         clean(row.get("Series")),
                "deal_size":      clean(row.get("Deal Size")),
                "post_valuation": clean(row.get("Post Valuation")),
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
    status = upsert_deal(row, company_id, stage="Watchlist", source="Jesse")

    # Patch Round Live (Access) separately — it's a select on the deal record
    if isinstance(status, dict) and status.get("status") == "created" and data.get("Access") is True:
        requests.patch(
            f"{ATTIO_API_BASE}/objects/deals/records/{status['record_id']}",
            headers=attio_headers(),
            json={"data": {"values": {"round_live": [{"option": "Round Live"}]}}},
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
                "deal_size":      clean(str(data.get("Deal Size", ""))),
                "post_valuation": clean(str(data.get("Post Valuation", ""))),
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


@app.route("/fix-radar-stages", methods=["POST"])
def fix_radar_stages():
    """
    One-time fix: finds all Qualified deals whose New Investors or Lead Investors
    contain a top-tier VC, and moves them to Radar — only if currently Qualified.
    """
    fixed, skipped, errors = [], [], []
    offset = 0
    limit  = 100

    while True:
        resp = requests.post(
            f"{ATTIO_API_BASE}/objects/deals/records/query",
            headers=attio_headers(),
            json={"filter": {"stage": {"$eq": "Qualified"}}, "limit": limit, "offset": offset},
        )
        if resp.status_code != 200:
            return jsonify({"error": f"Attio query failed: {resp.text[:300]}"}), 500

        batch = resp.json().get("data", [])
        if not batch:
            break

        for record in batch:
            vals   = record.get("values", {})
            rid    = record["id"]["record_id"]
            name   = (vals.get("name") or [{}])[0].get("value", rid)
            new_inv = str((vals.get("new_investors_7") or [{}])[0].get("value", "") or "").strip()

            if not new_inv or new_inv.lower() in ("nan", "none", ""):
                skipped.append(name)
                continue

            patch = requests.patch(
                f"{ATTIO_API_BASE}/objects/deals/records/{rid}",
                headers=attio_headers(),
                json={"data": {"values": {"stage": [{"status": "Radar"}]}}},
            )
            if patch.status_code in (200, 201):
                fixed.append(name)
            else:
                errors.append({"deal": name, "error": patch.text[:200]})

        if len(batch) < limit:
            break
        offset += limit

    return jsonify({"fixed": fixed, "fixed_count": len(fixed),
                    "skipped_count": len(skipped), "errors": errors})


@app.route("/logo", methods=["GET"])
def logo():
    """Serve the ID8 logo for email headers."""
    path = os.path.join(os.path.dirname(__file__), "logo.png")
    if not os.path.exists(path):
        return jsonify({"error": "logo.png not found"}), 404
    return send_file(path, mimetype="image/png")


@app.route("/cron/weekly-sync", methods=["POST"])
def cron_weekly_sync():
    """
    Trigger the weekly Attio → Apollo sync.
    Protect with X-Cron-Secret header (set CRON_SECRET env var).
    Safe to call via an external scheduler (cron-job.org, Render cron, etc.).
    """
    if CRON_SECRET and request.headers.get("X-Cron-Secret") != CRON_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    started, msg = start_sync()
    return jsonify({"started": started, "message": msg})


@app.route("/cron/sync-status", methods=["GET"])
def cron_sync_status():
    """Poll the status of the most recent weekly sync."""
    return jsonify(get_sync_status())


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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
