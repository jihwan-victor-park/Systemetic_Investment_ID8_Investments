import os
import re
import io
import sys
import time
import asyncio
import unicodedata
import traceback
import threading
import requests
import pandas as pd
import openpyxl
from flask import Flask, request, jsonify, send_file, send_file
from datetime import datetime

import uuid
import attio_apollo_sync as apollo_sync
from google.cloud import firestore as gcp_firestore

# deal_intelligence/ lives at the repo root, a sibling of this pipeline/ dir —
# gunicorn's --chdir pipeline only puts pipeline/ on sys.path, so add the
# parent explicitly rather than depending on how the process was launched.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from deal_intelligence import _secrets  # noqa: F401 — loads GCP secrets into os.environ
from deal_intelligence import pipeline as di_pipeline
from deal_intelligence import schemas as di_schemas
from deal_intelligence import config as di_config
from deal_intelligence import stage1_fit as di_stage1_fit
from deal_intelligence import stage2_research as di_stage2_research
from deal_intelligence import fit_note as di_fit_note
from deal_intelligence import firestore_push as di_firestore_push
from deal_intelligence import chat_intent as di_chat_intent
from deal_intelligence import attio_io as di_attio_io

app = Flask(__name__)

ATTIO_API_KEY  = os.environ.get("ATTIO_API_KEY", "")
ATTIO_API_BASE = "https://api.attio.com/v2"

# Jesse's Deals no longer writes to Attio (see /process-jesse) — this Firestore
# collection is the "have we already told the team about this company" record
# instead. Keyed by normalize_company_name() so it's insensitive to "Inc."/case/
# punctuation drift between sheet entries.
JESSE_SEEN_COLLECTION = "jesse_companies_seen"
_jesse_db = None

def _jesse_firestore():
    global _jesse_db
    if _jesse_db is None:
        _jesse_db = gcp_firestore.Client(project=di_config.GCP_PROJECT_ID)
    return _jesse_db

def _jesse_company_is_new(company_name):
    """True the first time this company is seen; marks it seen either way.
    Firestore, not Attio or n8n static data, is the source of truth here —
    both were unreliable (Attio has nothing to check against once we stopped
    writing to it; n8n's static data can reset on workflow edits/reactivation
    and doesn't persist during editor test runs)."""
    doc_ref = _jesse_firestore().collection(JESSE_SEEN_COLLECTION) \
        .document(normalize_company_name(company_name))
    is_new = not doc_ref.get().exists
    if is_new:
        doc_ref.set({"company": company_name, "first_seen": gcp_firestore.SERVER_TIMESTAMP})
    return is_new

DROP_COLS = [
    'Deal ID', 'Primary PitchBook Industry Code', 'View Company Online',
    'EBITDA', 'Valuation/EBITDA', 'Net Income', 'Deal Type', 'Deal Owner',
]

# Attio field mapping (CSV column -> API slug + type)
FIELD_MAP = {
    'Series':              ('series',           'select'),
    'Description':         ('description',      'text'),
    'Lead/Sole Investors': ('lead_investors_8',    'text'),
    'New Investors':       ('new_investors_5',   'text'),
    'Deal Size':           ('deal_size',         'currency'),
    'Post Valuation':      ('post_valuation',    'currency'),
    'Revenue':             ('revenue',           'currency'),
    'Valuation/Revenue':   ('valuation_revenue', 'number'),
    'Deal Date':           ('deal_date',         'date'),
    'Investors':           ('investors_5',         'text'),
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
# The slug is resolved at runtime by the attribute TITLE (below) so a slug mismatch
TOP10_VC_TITLE = 'Top 10 VC'
RADAR_STAGE    = 'Radar'


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

_attr_slug_cache = {}  # (object_slug, title_lower) -> api_slug

def deal_attr_slug(title, default=None):
    """Resolve a Deals attribute's api_slug by its TITLE (robust to slug drift).
    Falls back to `default` if the lookup fails or no title matches."""
    key = ("deals", title.strip().lower())
    if key in _attr_slug_cache:
        return _attr_slug_cache[key]
    slug = default
    resp = requests.get(f"{ATTIO_API_BASE}/objects/deals/attributes", headers=attio_headers())
    if resp.status_code == 200:
        for a in resp.json().get("data", []):
            if str(a.get("title", "")).strip().lower() == title.strip().lower():
                slug = a.get("api_slug") or default
                break
    print(f"ATTR SLUG '{title}' -> {slug}")
    _attr_slug_cache[key] = slug
    return slug

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
    'Investors Websites' column) then by normalized name. When an investor isn't found
    but the export gives its website, create the Companies record and link it. Investors
    with no match and no website are skipped (can't create without a domain).
    Returns {ref_slug: [{target_object, target_record_id}, ...]}.
    """
    name_to_domain = parse_investor_websites(row.get('Investors Websites'))
    by_name, by_domain = index["by_name"], index["by_domain"]

    out = {}
    for csv_col, ref_slug in INVESTOR_REF_MAP.items():
        ids = []
        for nm in parse_investors(row.get(csv_col)):
            key = normalize_company_name(nm)
            domain = name_to_domain.get(key, '')
            rid = by_domain.get(domain) or by_name.get(key)
            if not rid and domain:
                # Not in Attio yet, but the export gave its website -> create + cache
                # so repeats (across columns/rows) reuse the same record.
                rid = find_or_create_company(nm, domain)
                if rid:
                    by_domain[domain] = rid
                    by_name.setdefault(key, rid)
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

def _attio_post_retry(url, json_body, attempts=3, backoff=2.0):
    """POST to Attio with retries on 5xx/network errors. Attio's create endpoint
    threw a one-off 500 in production (Chai Discovery, 2026-07-20) that silently
    dropped a brand-new deal from the whole run -- no retry, and nothing surfaced
    the failure anywhere the team would see it. A 4xx is a real validation
    problem a retry won't fix, so only 5xx/network errors are retried."""
    resp = None
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.post(url, headers=attio_headers(), json=json_body)
        except requests.RequestException as exc:
            last_exc = exc
            resp = None
        if resp is not None and resp.status_code < 500:
            return resp
        if attempt < attempts:
            time.sleep(backoff * attempt)
    if resp is not None:
        return resp
    raise last_exc


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

def determine_stage(series, default_stage):
    """If series is A or earlier, move to Radar; otherwise use the provided stage."""
    early_series = {'Seed', 'Pre-Seed', 'Pre-A', 'Series A'}
    if series.strip() in early_series:
        return 'Radar'
    return default_stage

def upsert_deal(row, company_record_id, stage="Watchlist", source=None, top10=False):
    company_name = str(row.get('Companies', '')).strip()
    series = str(row.get('Series', '')).strip()
    stage = determine_stage(series, stage)

    existing_id = find_deal(company_name, series)
    if existing_id:
        # Existing deal: never change its stage. Always refresh investor links
        # (creating missing VCs when the export gives their website) and backfill the
        # associated company; the Top 10 VC flow also stamps its flag. These updates
        # never enter the email feed — only newly-created deals are returned as "created".
        patch_vals = {}
        patch_vals.update(resolve_investor_links(row, get_company_index()))
        if company_record_id:
            patch_vals["associated_company"] = [{
                "target_object": "companies", "target_record_id": company_record_id,
            }]
        if patch_vals:
            pr = requests.patch(
                f"{ATTIO_API_BASE}/objects/deals/records/{existing_id}",
                headers=attio_headers(),
                json={"data": {"values": patch_vals}},
            )
            print(f"DEAL PATCH {company_name} top10={top10} keys={list(patch_vals)}: "
                  f"{pr.status_code} {pr.text[:200]}")
        return "skipped"

    values = build_attio_values(row, company_record_id, stage, source, top10)
    try:
        resp = _attio_post_retry(f"{ATTIO_API_BASE}/objects/deals/records", {"data": {"values": values}})
    except requests.RequestException as exc:
        print(f"DEAL CREATE {company_name} top10={top10}: network error after retries: {exc}")
        return f"error:network:{exc}"
    print(f"DEAL CREATE {company_name} top10={top10}: "
          f"{resp.status_code} {resp.text[:200]}")
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

        deal_row = {
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
        }
        if isinstance(status, dict) and status.get("status") == "created":
            # Only brand-new deals (not already in Attio) get screened + emailed.
            results["created"] += 1
            deal_row["record_id"] = status.get("record_id", "")
            results["deals"].append(deal_row)
        elif status == "skipped":
            # Already in Attio — investor links refreshed, but not re-researched.
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

def _start_pipeline(stage, source, top10=False):
    file_bytes, err = _read_file_bytes()
    if err:
        return err
    with _pipeline_lock:
        if _pipeline_state.get("status") in ("running", "screening"):
            return jsonify({"error": "already running", "state": dict(_pipeline_state)}), 409
        _pipeline_state.clear()
        _pipeline_state.update({"status": "running"})

    t = threading.Thread(target=_run_pipeline_bg, args=(file_bytes, stage, source, top10), daemon=True)
    t.start()

    # Block until the whole pipeline (ingest + Perplexity screening) finishes, so
    # the single n8n HTTP node gets deals + fit scores + email_html in one response.
    # gunicorn --timeout is 1800s (see Dockerfile); we stop polling a touch before
    # that. This used to be 280s, calibrated to a 300s gunicorn timeout that's
    # since been raised for /screen's sake -- left stale here, this endpoint kept
    # bailing at 280s regardless, so any batch whose Stage 1 scoring ran past that
    # (routine with sonar-deep-research's per-deal timeout) got its /process
    # response -- and the n8n deal-intake email built straight from it -- with no
    # fit_score on any deal, even though scoring finished normally moments later.
    # If a large upload still doesn't finish in time, we return the partial state
    # and the caller can poll /process/status for the rest.
    deadline = time.time() + 1700
    while time.time() < deadline:
        with _pipeline_lock:
            s = _pipeline_state.get("status")
        if s in ("complete", "error"):
            break
        time.sleep(1)

    with _pipeline_lock:
        state = dict(_pipeline_state)

    if state.get("status") == "error":
        return jsonify(state), 500

    # status is "complete" (full result) or "screening" (timed out — deals present,
    # scores still landing; poll /process/status for the finished version).
    return jsonify({**state, "poll": "/process/status"})


@app.route("/process", methods=["POST"])
def process():
    return _start_pipeline(stage="Qualified", source="ID8 Investments")


@app.route("/process-watchlist", methods=["POST"])
def process_watchlist():
    return _start_pipeline(stage="Watchlist", source="ID8 Investments")


@app.route("/process-top10", methods=["POST"])
def process_top10():
    """Top 10 VC weekly flow: tag deals Top 10 VC = Yes; new deals default to the
    Radar stage; existing deals keep their stage (only flag + investor links updated)."""
    return _start_pipeline(stage=RADAR_STAGE, source="ID8 Investments", top10=True)


@app.route("/process/status", methods=["GET"])
def process_status():
    with _pipeline_lock:
        return jsonify(dict(_pipeline_state))

@app.route("/process-jesse", methods=["POST"])
def process_jesse():
    """Validate + format a row from Jesse's Deals sheet. Writes nothing to Attio —
    n8n accumulates these into a once-a-day digest instead of a live CRM sync
    (Jesse's rows are rarely complete when marked Ready, so pushing them into
    Attio immediately created sparse, half-filled deal records). "is_new" comes
    from Firestore (see _jesse_company_is_new), which is the system of record
    for "already told the team about this" now that Attio isn't in the loop."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON received."}), 400

    def clean(val):
        s = str(val or "").strip()
        return "" if s.lower() in ("nan", "none") else s

    company_name = clean(data.get("Company", ""))
    if not company_name:
        return jsonify({"error": "Company name is required."}), 400

    is_new = _jesse_company_is_new(company_name)

    return jsonify({
        "company":         company_name,
        "website":         clean(data.get("Company Website", "")),
        "series":          clean(data.get("Round", "")),
        "is_new":          is_new,
        "description":     clean(data.get("Description", "")),
        "deal_size":       fmt_money_millions(data.get("Deal Size")),
        "post_valuation":  fmt_money_millions(data.get("Post Valuation")),
        "revenue":         fmt_money_millions(data.get("Revenue")),
        "deal_date":       format_date(data.get("Date")) or "",
        "lead_investors":  clean(data.get("Lead Investor", "")),
        "new_investors":   clean(data.get("New Investors", "")),
    })


@app.route("/process-jesse/seed", methods=["POST"])
def process_jesse_seed():
    """One-off backfill: mark every company already sitting in the Jesses Deals
    tab as 'seen' in Firestore, so the daily digest only reports genuinely new
    submissions going forward — not the entire existing sheet on day one.
    Upload the raw ID8_Deal_Pipeline workbook (the 'Jesses Deals' tab, header
    on the 2nd row). Safe to re-run; re-seeding an existing company is a no-op
    other than refreshing its first_seen timestamp."""
    file_bytes, err = _read_file_bytes()
    if err:
        return err

    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name="Jesses Deals", header=1)
    companies = set()
    for val in df.get("Company", []):
        name = str(val or "").strip()
        if name and name.lower() != "nan":
            companies.add(name)

    db = _jesse_firestore()
    for name in companies:
        db.collection(JESSE_SEEN_COLLECTION).document(normalize_company_name(name)).set(
            {"company": name, "first_seen": gcp_firestore.SERVER_TIMESTAMP}
        )

    return jsonify({"status": "done", "seeded": len(companies), "companies": sorted(companies)})


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


_update_state = {"status": "idle"}
_update_lock = threading.Lock()

_pipeline_state = {"status": "idle"}
_pipeline_lock = threading.Lock()


def _run_pipeline_bg(file_bytes, stage, source, top10):
    """Background worker for /process, /process-watchlist, /process-top10.

    Phase 1 (fast): ingest deals into Attio → state becomes "screening".
    Phase 2 (slow): Perplexity Stage 1 scoring → state becomes "complete".

    n8n should poll /process/status until status == "complete" to get fit scores.
    If PERPLEXITY_API_KEY is absent, phase 2 is skipped and status goes straight
    to "complete" with no fit fields.
    """
    with _pipeline_lock:
        _pipeline_state.update({"status": "running", "created": 0, "skipped": 0,
                                 "errors": [], "deals": [], "error": None})
    try:
        results = run_pipeline(file_bytes, stage=stage, source=source, top10=top10)
    except Exception as e:
        print("PIPELINE ERROR:", traceback.format_exc())
        with _pipeline_lock:
            _pipeline_state.update({"status": "error", "error": str(e)})
        return

    # Publish Attio-ingestion results immediately so a short-polling caller can
    # already render the deal list while screening is in progress.
    with _pipeline_lock:
        _pipeline_state.update({"status": "screening", **results})

    # ── Stage 1 screening ────────────────────────────────────────────────────
    new_deals = results.get("deals", [])
    publish = bool(os.environ.get("GH_TOKEN"))  # push hub pages only when token present
    if new_deals and os.environ.get("PERPLEXITY_API_KEY"):
        try:
            di_inputs = [
                di_schemas.DealInput(
                    record_id=d["record_id"] if d.get("record_id") else f"proc-{i}",
                    name=d["company"],
                    domain=d.get("website") or None,
                    round=d.get("series") or None,
                    hq=d.get("hq_location") or None,
                    lead_investors=d.get("lead_investors") or None,
                )
                for i, d in enumerate(new_deals)
            ]
            # Use a synthetic record_id lookup key that matches what DealInput got.
            rid_map = {
                (d["record_id"] if d.get("record_id") else f"proc-{i}"): d
                for i, d in enumerate(new_deals)
            }
            screen_result = asyncio.run(
                di_pipeline.screen(di_inputs, dry_run=False, publish=publish)
            )
            fit_list  = screen_result.get("fits", [])
            stage1_list = screen_result.get("stage1", [])
            hub_by_rid = {s["name"]: s.get("hub_url", "") for s in stage1_list}
            for f in fit_list:
                d = rid_map.get(f.record_id)
                if not d:
                    continue
                d["fit_score"]      = round(f.fit_score, 1)
                d["fit_raw_score"]  = round(f.raw_score, 1)
                d["fit_gate"]       = f.gate
                d["fit_tier"]       = f.quality_tier
                d["fit_rationale"]  = f.rationale
                d["fit_confidence"] = f.confidence
                d["fit_hard_auto_pass"]        = f.hard_auto_pass
                d["fit_hard_auto_pass_reason"] = f.hard_auto_pass_reason
                d["hub_url"]        = hub_by_rid.get(f.name, "")
                d["fit_citations"]  = f.citations
                d["fit_params"]     = [
                    {"key": p.key, "score": p.score, "evidence": p.evidence}
                    for p in f.params
                ]
            results["email_html"]     = screen_result.get("email_html", "")
            results["email_text"]     = screen_result.get("email_text", "")
            results["screened"]       = screen_result.get("screened", 0)
            results["gated"]          = screen_result.get("gated", 0)
            results["more_diligence"] = screen_result.get("more_diligence", 0)
            results["watch_list"]     = screen_result.get("watch_list", 0)
        except Exception as e:
            print("SCREENING ERROR:", traceback.format_exc())
            results["screening_error"] = str(e)

        # Screening just pushed new company pages to GitHub. The hub is a static
        # Docusaurus site on Firebase, so those pages go live only after a rebuild
        # + firebase deploy — kick that off here so the workflow doesn't have to.
        # Fire-and-forget: the email goes out as soon as /process returns, and the
        # build (npm build + deploy) lands a minute or so later, so a freshly added
        # deal's "Full research" link may be briefly stale on the very first email.
        # Guarded on `publish`: without GH_TOKEN no pages were pushed, so there is
        # nothing new to redeploy.
        if publish:
            try:
                build_id, err = _start_hub_build()
                if err:
                    print(f"HUB BUILD trigger failed: {err}")
                else:
                    results["hub_build_id"] = build_id
                    print(f"HUB BUILD triggered: {build_id}")
            except Exception:
                print("HUB BUILD trigger error:", traceback.format_exc())

    with _pipeline_lock:
        _pipeline_state.update({"status": "complete", **results})


def _run_update_investors(file_bytes):
    """Backfill worker — runs in a background thread (the full pass over a large export
    plus the Companies index build exceeds the 30s gunicorn worker timeout, so it can't
    run inline). Progress is published to _update_state for /update-investors/status."""
    try:
        df = transform_excel(file_bytes)
    except Exception as e:
        print("TRANSFORM ERROR:", traceback.format_exc())
        with _update_lock:
            _update_state.update({"status": "error", "error": f"Transform failed: {e}"})
        return

    total = len(df)
    with _update_lock:
        _update_state.update({"status": "running", "total": total, "processed": 0,
                              "updated": 0, "unchanged": 0, "not_found": 0, "links": 0,
                              "missing": [], "errors": [], "error": None})

    get_company_index(refresh=True)
    index = get_company_index()
    updated = unchanged = not_found = links = 0
    missing, errors = [], []

    for i, (_, row) in enumerate(df.iterrows()):
        rowd = row.to_dict()
        company_name = str(rowd.get("Companies", "")).strip()
        series = str(rowd.get("Series", "")).strip()
        try:
            existing_id = find_deal(company_name, series)
            if not existing_id:
                not_found += 1
                missing.append(f"{company_name} ({series})")
            else:
                ref_values = resolve_investor_links(rowd, index)
                if not ref_values:
                    unchanged += 1
                else:
                    r = requests.patch(
                        f"{ATTIO_API_BASE}/objects/deals/records/{existing_id}",
                        headers=attio_headers(),
                        json={"data": {"values": ref_values}},
                    )
                    if r.status_code in (200, 201):
                        updated += 1
                        links += sum(len(v) for v in ref_values.values())
                    else:
                        errors.append({"deal": company_name, "error": f"{r.status_code}:{r.text[:200]}"})
        except Exception as e:
            errors.append({"deal": company_name, "error": str(e)[:200]})

        with _update_lock:
            _update_state.update({"processed": i + 1, "updated": updated, "unchanged": unchanged,
                                  "not_found": not_found, "links": links,
                                  "missing": missing, "errors": errors})

    with _update_lock:
        _update_state["status"] = "complete"


@app.route("/update-investors", methods=["POST"])
def update_investors():
    """Backfill investor links on EXISTING deals from an uploaded PitchBook export.

    Update-only: matches each row's deal by name+series and PATCHes its investor
    references; if the deal isn't found it is SKIPPED — never created (no duplicate
    deals). Missing investor *Companies* are still created when the export gives their
    website. Sends no email; nothing here is a 'created' deal.

    Runs in the background and returns immediately — poll GET /update-investors/status.
    """
    file_bytes, err = _read_file_bytes()
    if err:
        return err
    with _update_lock:
        if _update_state.get("status") == "running":
            return jsonify({"error": "already running", "state": dict(_update_state)}), 409
        _update_state.clear()
        _update_state.update({"status": "running"})
    threading.Thread(target=_run_update_investors, args=(file_bytes,), daemon=True).start()
    return jsonify({"status": "started", "poll": "/update-investors/status"})


@app.route("/update-investors/status", methods=["GET"])
def update_investors_status():
    with _update_lock:
        return jsonify(dict(_update_state))


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


@app.route("/fix-attio-import-stages", methods=["POST"])
def fix_attio_import_stages():
    """One-time correction for hub-next companies the bulk Attio import
    mis-bucketed into New Deals before push_company_from_attio's stage
    mapping existed -- see deal_intelligence.firestore_push.backfill_attio_stages.
    Synchronous (a Firestore-only scan, no external API calls), same style as
    /fix-radar-stages above."""
    if not _require_internal_secret():
        return jsonify({"error": "forbidden"}), 403
    return jsonify(di_firestore_push.backfill_attio_stages())


@app.route("/fix-company-rounds", methods=["POST"])
def fix_company_rounds():
    """One-time backfill: seeds `round` from origin.round for companies that
    existed before the round field was added -- see
    deal_intelligence.firestore_push.backfill_company_rounds."""
    if not _require_internal_secret():
        return jsonify({"error": "forbidden"}), 403
    return jsonify(di_firestore_push.backfill_company_rounds())


_apollo_state = {"status": "idle"}
_apollo_lock  = threading.Lock()


def _run_sync_apollo():
    """Background worker: mirror all Attio People into Apollo and park them in the
    dormant holding sequence so Apollo flags them as already-sequenced in new
    prospecting searches. Idempotent — safe to run weekly (see attio_apollo_sync)."""
    try:
        people = apollo_sync.pull_attio_people()
    except Exception as e:
        print("APOLLO SYNC pull error:", traceback.format_exc())
        with _apollo_lock:
            _apollo_state.update({"status": "error", "error": f"Attio pull failed: {e}"})
        return

    contacts   = [apollo_sync.extract_contact(r) for r in people]
    with_email = [c for c in contacts if c.get("email")]
    total = len(with_email)
    with _apollo_lock:
        _apollo_state.update({"status": "running", "pulled": len(people), "with_email": total,
                              "no_email": len(contacts) - total, "processed": 0, "upserted": 0,
                              "failed": 0, "enrolled": 0, "errors": [], "error": None})

    apollo_ids, failed = [], 0
    for i, c in enumerate(with_email):
        aid = apollo_sync.create_apollo_contact(c)
        if aid:
            apollo_ids.append(aid)
        else:
            failed += 1
        time.sleep(0.12)  # stay under Apollo rate limits
        if (i + 1) % 10 == 0 or (i + 1) == total:
            with _apollo_lock:
                _apollo_state.update({"processed": i + 1, "upserted": len(apollo_ids), "failed": failed})

    enrolled, errs = apollo_sync.enroll_in_holding_sequence(apollo_ids)
    with _apollo_lock:
        _apollo_state.update({"status": "complete", "processed": total, "upserted": len(apollo_ids),
                              "failed": failed, "enrolled": enrolled, "errors": errs})


@app.route("/sync-apollo", methods=["POST"])
def sync_apollo():
    """Mirror Attio People → Apollo and enroll them in the holding sequence.

    Runs in the background (the full People pull + per-contact upsert exceeds the
    gunicorn worker timeout) and returns immediately — poll GET /sync-apollo/status.
    Requires APOLLO_API_KEY (a MASTER key — add_contact_ids 403s otherwise) and
    APOLLO_HOLDING_SEQUENCE_ID (a dormant sequence with no active email steps).
    """
    missing = [v for v in ("ATTIO_API_KEY", "APOLLO_API_KEY", "APOLLO_HOLDING_SEQUENCE_ID")
               if not os.environ.get(v)]
    if missing:
        return jsonify({"error": f"missing env vars: {', '.join(missing)}"}), 400
    with _apollo_lock:
        if _apollo_state.get("status") == "running":
            return jsonify({"error": "already running", "state": dict(_apollo_state)}), 409
        _apollo_state.clear()
        _apollo_state.update({"status": "running"})
    threading.Thread(target=_run_sync_apollo, daemon=True).start()
    return jsonify({"status": "started", "poll": "/sync-apollo/status"})


@app.route("/sync-apollo/status", methods=["GET"])
def sync_apollo_status():
    with _apollo_lock:
        return jsonify(dict(_apollo_state))


# Fixed job_id (not a fresh uuid per run) -- this endpoint is a singleton,
# n8n-triggered-on-a-schedule job, so "is one already running" is answered by
# reading one well-known doc rather than tracking multiple ids.
_SCREEN_DEALS_JOB_ID = "screen-deals-backlog"


def _run_screen_deals(job_id, dry_run, stage1_only, publish):
    try:
        result = asyncio.run(di_pipeline.run(dry_run=dry_run, stage1_only=stage1_only, publish=publish))
        # email_html/email_text can run well past Firestore's 1MiB document
        # cap for a large qualified pool, and nothing reads them back off this
        # status doc -- n8n reads results from Attio directly and posts its
        # own Slack summary (see deal_intelligence/README.md's "n8n wiring"),
        # it never consumed this field from the JSON body. Drop both, keep
        # every small summary field (counts, stage1 list, memos).
        result = {k: v for k, v in result.items() if k not in ("email_html", "email_text")}
        _set_chat_job(job_id, {"status": "complete", **result})
    except Exception as e:
        _set_chat_job(job_id, {"status": "error", "error": str(e)})


@app.route("/screen-deals", methods=["POST"])
def screen_deals():
    """Deal Intelligence stage 1 (fit score, every Qualified deal) and, unless
    stage1_only, stage 2 (deep research + memo for deals that clear the gate).

    Runs in the background — Perplexity research per deal, bounded concurrency,
    can take minutes for a large qualified pool — and returns immediately; poll
    GET /screen-deals/status. JSON body, all optional:
      {"dry_run": false, "stage1_only": true}
    dry_run skips the Attio write-back. stage1_only defaults true so triggering
    this with no body never spends an Anthropic call or writes a memo; pass
    stage1_only: false once the Attio write-back fields exist and stage 2 is wired.

    State lives in the same Firestore chat_jobs mechanism as /research-chat
    (a fixed doc id, not a fresh one per run) instead of an in-process dict --
    the in-process version could route a start-POST and a status-GET to two
    different Cloud Run instances and 404 a job that was actually running
    fine; this endpoint's request/response shape is unchanged either way.
    """
    missing = [v for v in ("ATTIO_API_KEY", "PERPLEXITY_API_KEY") if not os.environ.get(v)]
    if missing:
        return jsonify({"error": f"missing env vars: {', '.join(missing)}"}), 400
    body = request.get_json(silent=True) or {}
    dry_run = bool(body.get("dry_run", False))
    stage1_only = bool(body.get("stage1_only", True))
    # publish writes per-company hub pages + .docx to disk. Off by default over
    # HTTP: this service runs on Cloud Run with an ephemeral filesystem, so hub
    # pages must be generated where they can be committed to git (local/CI), not
    # in this container. The endpoint always returns email_html regardless.
    publish = bool(body.get("publish", False))
    current = _get_chat_job(_SCREEN_DEALS_JOB_ID)
    if current and current.get("status") == "running":
        return jsonify({"error": "already running", "state": current}), 409
    _start_chat_job(_SCREEN_DEALS_JOB_ID, {
        "status": "running", "type": "screen_deals_backlog", "label": "Attio qualified backlog",
        "createdAt": datetime.utcnow().isoformat() + "Z",
    })
    threading.Thread(target=_run_screen_deals, args=(_SCREEN_DEALS_JOB_ID, dry_run, stage1_only, publish),
                      daemon=True).start()
    return jsonify({"status": "started", "poll": "/screen-deals/status"})


@app.route("/screen-deals/status", methods=["GET"])
def screen_deals_status():
    job = _get_chat_job(_SCREEN_DEALS_JOB_ID)
    return jsonify(job or {"status": "idle"})


@app.route("/screen", methods=["POST"])
def screen():
    """Score a SPECIFIC batch of deals (the intake batch from /process), not the
    whole Qualified pool. n8n posts the deals it just added; this scores them via
    Perplexity, writes fit score / gate / rationale / hub link back to Attio, and
    returns email_html for the intake email. Synchronous — returns when done.

    Body:
      {
        "deals": [
          {"record_id": "...", "name": "Acme (SF, CA; AI X)", "round": "Series B",
           "lead_investors": "Accel", "hq": "San Francisco, CA", "domain": "acme.com"}
        ],
        "dry_run": false   // optional; true skips the Attio write-back
      }
    record_id is needed for write-back; omit it to just score (e.g. a dry preview).
    """
    if not os.environ.get("PERPLEXITY_API_KEY"):
        return jsonify({"error": "missing env var: PERPLEXITY_API_KEY"}), 400
    body = request.get_json(silent=True) or {}
    raw_deals = body.get("deals") or []
    if not raw_deals:
        return jsonify({"error": "body must include a non-empty 'deals' array"}), 400

    fields = ("record_id", "name", "domain", "round", "lead_investors", "hq")
    deals = []
    for i, d in enumerate(raw_deals):
        if not d.get("name"):
            return jsonify({"error": f"deals[{i}] is missing 'name'"}), 400
        deals.append(di_schemas.DealInput(
            record_id=d.get("record_id") or f"batch-{i}",
            **{k: d.get(k) for k in fields if k != "record_id"}))

    dry_run = bool(body.get("dry_run", False))
    result = asyncio.run(di_pipeline.screen(deals, dry_run=dry_run, publish=False))
    result.pop("fits", None)  # dataclasses aren't JSON-serializable
    return jsonify(result)


# ── Research chat (hub-next "investigate a company" tool) ────────────────────
# Ad-hoc, one-off research on a company NAMED IN CHAT, not necessarily an Attio
# deal record — so unlike /screen and /screen-deals, this never touches Attio.
# Stage 1 still gets a real fit score and (unlike the Attio path) is published
# straight to Firestore, so it shows up in hub-next's Qualified Deals list like
# any other screen. Stage 2 has no hub-next display surface today, so its memo
# is returned to the caller directly and not persisted anywhere.
#
# Runs in a background thread and is polled, same shape as /screen-deals,
# because Stage 1 now runs sonar-deep-research and Stage 2 runs several
# research angles plus a Claude synthesis -- both take minutes, too long for a
# single synchronous request.
#
# Job state lives in Firestore, NOT an in-process dict -- Cloud Run can (and
# does) route the POST that starts a job and the GET that polls it to two
# different container instances, and an in-memory dict on instance A is
# invisible to instance B, which then 404s the poll ("not found") even though
# the job is running fine. Firestore is shared across instances the same way
# it already is for everything else in this service.
_CHAT_JOBS_COLLECTION = "chat_jobs"
_chat_jobs_db = None


def _chat_jobs_firestore():
    global _chat_jobs_db
    if _chat_jobs_db is None:
        _chat_jobs_db = gcp_firestore.Client(project=di_config.GCP_PROJECT_ID)
    return _chat_jobs_db


def _start_chat_job(job_id: str, data: dict):
    """First write of a job's life -- a full (non-merge) overwrite, so a
    reused fixed job_id (see /screen-deals below) can't leak result fields
    from a previous run into the new one."""
    _chat_jobs_firestore().collection(_CHAT_JOBS_COLLECTION).document(job_id).set(data)


def _set_chat_job(job_id: str, data: dict):
    # merge=True: every phase transition AFTER the start write only ADDS
    # fields (fit/slug/verdict, memo, error, counters) -- it never needs to
    # remove one, so a merge write lets createdAt/label/type survive a job's
    # whole lifecycle instead of getting wiped by the next .set().
    _chat_jobs_firestore().collection(_CHAT_JOBS_COLLECTION).document(job_id).set(data, merge=True)


def _get_chat_job(job_id: str):
    doc = _chat_jobs_firestore().collection(_CHAT_JOBS_COLLECTION).document(job_id).get()
    return doc.to_dict() if doc.exists else None


_STALE_JOB_MINUTES = 30


def _list_active_jobs():
    """Every chat_jobs doc currently 'running' -- single-field equality
    filter, no composite index needed. Backs the hub-next jobs tray.

    A background thread's job doc is the ONLY record that it's alive --
    there's no separate heartbeat. If the Cloud Run container that was
    running it gets recycled mid-job (a deploy, a scale-down, an OOM), the
    thread just dies and the doc is stuck at status='running' forever; the
    tray would otherwise show it as active indefinitely. Anything older than
    _STALE_JOB_MINUTES (comfortably past STAGE1_TIMEOUT_SECONDS, the longest
    single call any job type here makes) gets flipped to 'error' here and
    dropped from the list, rather than trusting 'running' at face value.
    Jobs from before this field existed (no createdAt at all) count as stale
    immediately -- there's no way to tell how old they are, so don't guess.
    """
    now = datetime.utcnow()
    active = []
    for doc in _chat_jobs_firestore().collection(_CHAT_JOBS_COLLECTION).where("status", "==", "running").stream():
        data = doc.to_dict()
        created_at = data.get("createdAt")
        stale = True
        if created_at:
            try:
                age_minutes = (now - datetime.fromisoformat(created_at.rstrip("Z"))).total_seconds() / 60
                stale = age_minutes > _STALE_JOB_MINUTES
            except ValueError:
                stale = True
        if stale:
            _set_chat_job(doc.id, {"status": "error", "error": "stale — job never completed (likely interrupted by a deploy or restart)"})
        else:
            active.append({"job_id": doc.id, **data})
    return active


def _require_internal_secret():
    """Optional shared-secret gate. hub-next's server-side API route is the
    only intended caller (never the browser directly) -- if INTERNAL_API_SECRET
    is configured, require it; if it isn't set yet, don't block (matches every
    other endpoint on this service today, which has no request auth at all)."""
    expected = os.environ.get("INTERNAL_API_SECRET")
    if not expected:
        return True
    return request.headers.get("X-Internal-Secret") == expected


def _run_chat_stage1(job_id: str, deal: "di_schemas.DealInput"):
    try:
        fit = asyncio.run(di_stage1_fit.score_deal(deal))
        slug = di_fit_note.company_id(deal)
        docx_bytes = di_fit_note.build_docx_bytes(fit, deal)
        di_firestore_push.push_company_screen_firestore(fit, deal, slug, docx_bytes)
        _set_chat_job(job_id, {
            "status": "complete", "stage": 1,
            "fit": fit.to_dict(), "slug": slug,
            "verdict": di_fit_note._badge_text(fit),
            "hub_path": f"/docs/qualified-deals/{slug}",
        })
    except Exception as e:
        _set_chat_job(job_id, {"status": "error", "stage": 1, "error": str(e)})


def _run_chat_stage2(job_id: str, deal: "di_schemas.DealInput"):
    try:
        memo = asyncio.run(di_stage2_research.deep_research(deal))
        _set_chat_job(job_id, {"status": "complete", "stage": 2, "memo": memo.to_dict()})
    except Exception as e:
        _set_chat_job(job_id, {"status": "error", "stage": 2, "error": str(e)})


@app.route("/research-chat", methods=["POST"])
def research_chat():
    """Start an ad-hoc research job on a company named in the chat. Body:
      {"name": "Acme", "domain": "acme.com", "round": "Series C",
       "lead_investors": "Accel", "hq": "SF, CA", "stage": 1}
    Only "name" and "stage" (1 or 2) are required; the rest sharpen the
    research the way they would for a real qualified-deal screen."""
    if not _require_internal_secret():
        return jsonify({"error": "forbidden"}), 403
    missing = [v for v in ("PERPLEXITY_API_KEY",) if not os.environ.get(v)]
    if missing:
        return jsonify({"error": f"missing env vars: {', '.join(missing)}"}), 400
    body = request.get_json(silent=True) or {}
    stage = body.get("stage", 1)
    if stage not in (1, 2):
        return jsonify({"error": "'stage' must be 1 or 2"}), 400
    if stage == 2 and not os.environ.get("ANTHROPIC_API_KEY"):
        return jsonify({"error": "missing env var: ANTHROPIC_API_KEY (needed for Stage 2 synthesis)"}), 400

    name = (body.get("name") or "").strip()
    domain, round_, lead_investors, hq = (body.get("domain") or None, body.get("round") or None,
                                           body.get("lead_investors") or None, body.get("hq") or None)

    # Stage 1 only: free-text "message" gets parsed into a company + optional
    # context (deal_intelligence/chat_intent.py) -- this is the ONLY intent
    # that parser recognizes, and it's the only thing this endpoint does with
    # it. Stage 2 has no chat-intent parsing yet, by design (see chat_intent.py
    # docstring) -- it still requires "name" directly, same as before.
    message = (body.get("message") or "").strip()
    context = (body.get("context") or "").strip() or None
    if stage == 1 and message and not name:
        # Synchronous, inline in the request (unlike the actual research
        # below, which is backgrounded) -- so an unhandled exception here
        # (bad/expired PERPLEXITY_API_KEY, a transient Perplexity 429/500,
        # a network blip) would otherwise propagate past Flask's default
        # error handler as a plain HTML 500 page. hub-next's route.js can
        # only do `res.json()` on whatever comes back, so an HTML body
        # surfaces as an opaque "invalid response from pipeline service" --
        # catch it here and return real JSON with the actual cause instead.
        try:
            parsed = di_chat_intent.parse_investigate_message(message, context=context)
        except Exception as e:
            return jsonify({"error": f"chat-intent parsing failed: {e}"}), 502
        if parsed["needs_clarification"] or not parsed["name"]:
            return jsonify({
                "status": "needs_clarification",
                "clarification_question": parsed["clarification_question"] or
                    "Which company would you like me to investigate?",
            })
        name = parsed["name"]
        domain = domain or parsed["domain"]
        round_ = round_ or parsed["round"]
        lead_investors = lead_investors or parsed["lead_investors"]
        hq = hq or parsed["hq"]

    if not name:
        return jsonify({"error": "'name' is required"}), 400

    deal = di_schemas.DealInput(
        record_id=f"chat-{uuid.uuid4().hex[:10]}", name=name,
        domain=domain, round=round_, lead_investors=lead_investors, hq=hq,
    )
    job_id = uuid.uuid4().hex
    _start_chat_job(job_id, {
        "status": "running", "stage": stage, "type": "chat",
        "label": f"{name} — Stage {stage}", "createdAt": datetime.utcnow().isoformat() + "Z",
    })
    target = _run_chat_stage1 if stage == 1 else _run_chat_stage2
    threading.Thread(target=target, args=(job_id, deal), daemon=True).start()
    # "name" echoed back so the frontend can show the resolved company name
    # while polling, even when it only had a free-text message to go on.
    return jsonify({"job_id": job_id, "status": "started", "poll": f"/research-chat/{job_id}", "name": name})


@app.route("/research-chat/<job_id>", methods=["GET"])
def research_chat_status(job_id):
    if not _require_internal_secret():
        return jsonify({"error": "forbidden"}), 403
    job = _get_chat_job(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    return jsonify(job)


# ── Generic job listing/status (hub-next's global jobs tray) ─────────────────
# Every background job in this service (chat Stage 1/2, a per-row rerun, the
# Attio bulk import, and the qualified-deal backlog below) writes through
# _set_chat_job into the same chat_jobs collection -- these two routes are a
# type-agnostic way to list/poll any of them, so the tray doesn't need to know
# which specific endpoint started a given job.
@app.route("/jobs", methods=["GET"])
def list_jobs():
    if not _require_internal_secret():
        return jsonify({"error": "forbidden"}), 403
    return jsonify({"jobs": _list_active_jobs()})


@app.route("/jobs/<job_id>", methods=["GET"])
def job_status(job_id):
    if not _require_internal_secret():
        return jsonify({"error": "forbidden"}), 403
    job = _get_chat_job(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    return jsonify({"job_id": job_id, **job})


def _run_company_screen(job_id: str, slug: str, deal: "di_schemas.DealInput"):
    """Same chain as _run_chat_stage1 (score -> docx -> Firestore push), but
    for an EXISTING company row: `slug` is pinned from the caller rather than
    recomputed from the deal, so results land back on the same doc the
    "Run Analysis" button was clicked on instead of risking a second,
    differently-slugged company doc if company_id(deal) drifts from what's
    already stored (e.g. a manually-edited name/domain)."""
    try:
        fit = asyncio.run(di_stage1_fit.score_deal(deal))
        docx_bytes = di_fit_note.build_docx_bytes(fit, deal)
        di_firestore_push.push_company_screen_firestore(fit, deal, slug, docx_bytes, source="chat")
        _set_chat_job(job_id, {
            "status": "complete", "fit": fit.to_dict(), "slug": slug,
            "verdict": di_fit_note._badge_text(fit),
        })
    except Exception as e:
        _set_chat_job(job_id, {"status": "error", "error": str(e)})


@app.route("/screen-company/<slug>", methods=["POST"])
def screen_company(slug):
    """Run Analysis for one specific, already-known company row. Body:
      {"name": "Acme", "domain": "acme.com", "round": "Series C",
       "hq": "SF, CA", "lead_investors": "Accel"}
    hub-next supplies these (pulled from the company's own stored `origin`
    fields when present) rather than this endpoint re-reading Firestore
    itself, keeping it stateless-per-request like /research-chat."""
    if not _require_internal_secret():
        return jsonify({"error": "forbidden"}), 403
    missing = [v for v in ("PERPLEXITY_API_KEY",) if not os.environ.get(v)]
    if missing:
        return jsonify({"error": f"missing env vars: {', '.join(missing)}"}), 400
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "'name' is required"}), 400
    deal = di_schemas.DealInput(
        record_id=f"rerun-{slug}-{uuid.uuid4().hex[:8]}", name=name,
        domain=body.get("domain") or None, round=body.get("round") or None,
        lead_investors=body.get("lead_investors") or None, hq=body.get("hq") or None,
    )
    job_id = uuid.uuid4().hex
    _start_chat_job(job_id, {
        "status": "running", "type": "stage1_rerun", "companySlug": slug,
        "label": f"{name} — Run Analysis", "createdAt": datetime.utcnow().isoformat() + "Z",
    })
    threading.Thread(target=_run_company_screen, args=(job_id, slug, deal), daemon=True).start()
    return jsonify({"job_id": job_id, "status": "started", "poll": f"/jobs/{job_id}"})


def _run_attio_import(job_id: str):
    try:
        pairs = di_attio_io.list_all_deals()
        total = len(pairs)
        created = skipped = errors = 0
        for i, (deal, attio_stage) in enumerate(pairs):
            try:
                result = di_firestore_push.push_company_from_attio(deal, attio_stage)
                created += 1 if result.get("created") else 0
                skipped += 0 if result.get("created") else 1
            except Exception:
                errors += 1
            if (i + 1) % 10 == 0 or (i + 1) == total:
                _set_chat_job(job_id, {"processed": i + 1, "total": total,
                                        "created": created, "skipped": skipped, "errors": errors})
        _set_chat_job(job_id, {"status": "complete", "processed": total, "total": total,
                                "created": created, "skipped": skipped, "errors": errors})
    except Exception as e:
        _set_chat_job(job_id, {"status": "error", "error": str(e)})


@app.route("/import-attio-deals", methods=["POST"])
def import_attio_deals():
    """Pull every Attio deal regardless of stage and upsert a metadata-only
    company stub for each into hub-next's Firestore (stage='new' on brand-new
    companies, origin refresh only on existing ones -- see
    push_company_from_attio). No Stage 1 scoring here; that's the separate
    per-row "Run Analysis" trigger (POST /screen-company/<slug>) once Oscar
    has triaged a deal himself."""
    if not _require_internal_secret():
        return jsonify({"error": "forbidden"}), 403
    missing = [v for v in ("ATTIO_API_KEY",) if not os.environ.get(v)]
    if missing:
        return jsonify({"error": f"missing env vars: {', '.join(missing)}"}), 400
    job_id = uuid.uuid4().hex
    _start_chat_job(job_id, {
        "status": "running", "type": "attio_import", "label": "Attio import",
        "createdAt": datetime.utcnow().isoformat() + "Z", "processed": 0, "total": 0,
    })
    threading.Thread(target=_run_attio_import, args=(job_id,), daemon=True).start()
    return jsonify({"job_id": job_id, "status": "started", "poll": f"/jobs/{job_id}"})


# ── Hub publish (rebuild + deploy the Firebase site) ──────────────────────────
# The hub is a static Docusaurus site, so new screen pages only appear after a
# rebuild + firebase deploy. This backend is Python (no Node), so the build runs
# in Cloud Build. n8n calls POST /publish-hub after screening, polls
# /publish-hub/status until SUCCESS, THEN sends the email — so the "Full research"
# links are already live when the email goes out.
_CLOUD_BUILD_API = "https://cloudbuild.googleapis.com/v1"
_GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "molten-crowbar-498920-q8")
_GCP_PROJECT_NUM = os.environ.get("GCP_PROJECT_NUM", "137750788450")
_GH_REPO = os.environ.get("GH_REPO", "ocachin/id8-intelligence")


def _metadata_token():
    """Access token for the Cloud Run service account, from the metadata server."""
    r = requests.get(
        "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
        headers={"Metadata-Flavor": "Google"}, timeout=5)
    r.raise_for_status()
    return r.json()["access_token"]


def _hub_build_config():
    """Inline Cloud Build: clone (via GH_TOKEN secret) -> npm build -> firebase deploy."""
    clone = (f"git clone https://x-access-token:$$GH_TOKEN@github.com/{_GH_REPO}.git repo")
    deploy = (f"npx -y firebase-tools@latest deploy --only hosting "
              f"--project {_GCP_PROJECT_ID} --non-interactive")
    return {
        "steps": [
            {"name": "gcr.io/cloud-builders/git", "entrypoint": "bash",
             "args": ["-c", clone], "secretEnv": ["GH_TOKEN"]},
            {"name": "node:20", "dir": "repo/hub", "entrypoint": "bash",
             "args": ["-c", "npm ci && npm run build"]},
            {"name": "node:20", "dir": "repo/hub", "entrypoint": "bash",
             "args": ["-c", deploy]},
        ],
        "availableSecrets": {"secretManager": [
            {"versionName": f"projects/{_GCP_PROJECT_NUM}/secrets/GH_TOKEN/versions/latest",
             "env": "GH_TOKEN"},
        ]},
        "timeout": "900s",
    }


def _start_hub_build():
    """Kick off the Cloud Build that rebuilds + deploys the hub.

    Returns (build_id, error). Shared by the /publish-hub route and the
    auto-trigger at the end of a screening run — screening pushes new company
    pages to GitHub, but the live Firebase site is a static build, so it only
    reflects them after a rebuild + firebase deploy.
    """
    token = _metadata_token()
    r = requests.post(
        f"{_CLOUD_BUILD_API}/projects/{_GCP_PROJECT_ID}/builds",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=_hub_build_config(), timeout=30)
    if r.status_code not in (200, 201):
        return None, r.text[:600]
    build_id = r.json().get("metadata", {}).get("build", {}).get("id") or ""
    return build_id, None


@app.route("/publish-hub", methods=["POST"])
def publish_hub():
    """Kick off a Cloud Build that rebuilds + deploys the hub. Returns a build id;
    poll /publish-hub/status?id=<id> until status is SUCCESS before sending email."""
    try:
        build_id, err = _start_hub_build()
    except Exception as e:
        return jsonify({"error": f"no metadata token (not on Cloud Run?): {e}"}), 500
    if err:
        return jsonify({"error": "could not start build", "detail": err}), 502
    return jsonify({"status": "building", "build_id": build_id})


@app.route("/publish-hub/status", methods=["GET"])
def publish_hub_status():
    build_id = request.args.get("id", "")
    if not build_id:
        return jsonify({"error": "missing id"}), 400
    token = _metadata_token()
    r = requests.get(
        f"{_CLOUD_BUILD_API}/projects/{_GCP_PROJECT_ID}/builds/{build_id}",
        headers={"Authorization": f"Bearer {token}"}, timeout=15)
    data = r.json()
    # Cloud Build status: QUEUED, WORKING, SUCCESS, FAILURE, TIMEOUT, CANCELLED
    return jsonify({"status": data.get("status"), "log_url": data.get("logUrl")})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
