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
from deal_intelligence import radar_access as di_radar_access
from deal_intelligence import radar_mandate as di_radar_mandate
from deal_intelligence import radar_state as di_radar_state
from deal_intelligence import tier1_firms as di_tier1
from deal_intelligence import email_format as di_email_format
from deal_intelligence import rubric as di_rubric
# Re-exported: the placement rule moved to deal_intelligence/placement.py so
# import_attio_deals_csv.py could share it (see that module's docstring).
# `from app import determine_placement` still resolves here.
from deal_intelligence.placement import (  # noqa: F401
    QUALIFIED_STAGE, determine_placement, determine_stage, expected_placement)

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

# Email subject/heading per intake flow. The flow key is threaded from the route
# through _start_pipeline into _run_pipeline_bg, rather than re-derived from
# (stage, top10) -- /process and /process-top10 now BOTH pass stage='Qualified'
# (see determine_placement), so the stage alone no longer identifies the flow.
EMAIL_TITLES = {
    "deal_flow": "Weekly Deal Flow",
    "top10":     "Top 10 VC Radar",
    "watchlist": "Watchlist Update",
}


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

def _attio_write_retry(method, url, json_body, attempts=3, backoff=2.0):
    """Write to Attio with retries on 5xx/network errors. Attio's create endpoint
    threw a one-off 500 in production (Chai Discovery, 2026-07-20) that silently
    dropped a brand-new deal from the whole run -- no retry, and nothing surfaced
    the failure anywhere the team would see it. A 4xx is a real validation
    problem a retry won't fix, so only 5xx/network errors are retried.

    Generalized from the POST-only version 2026-08-26. The original protected
    `POST /records` and nothing else, but a create is not the only write whose
    loss is silent: `upsert_deal`'s existing-deal branch PATCHes investor links,
    the associated company and the Top 10 VC flag for every deal an intake run
    re-sees, and /update-deal-stage + /update-deal-fields PATCH a partner's hand
    edit made in hub-next. Each of those was a bare requests.patch, so the exact
    transient 500 this helper exists for would drop them just as quietly -- and
    for the hub edits, the human who made the change is told nothing beyond a
    502 they cannot act on.

    Exhaustion behaviour is unchanged from the POST version: when every attempt
    came back 5xx the LAST RESPONSE IS RETURNED, not raised, so callers keep
    their existing status-code branches and an Attio outage stays a handled
    error rather than an unhandled traceback partway through a run. Only a total
    network failure -- no response received at all -- raises."""
    resp = None
    last_exc = None
    send = getattr(requests, method)
    for attempt in range(1, attempts + 1):
        try:
            resp = send(url, headers=attio_headers(), json=json_body)
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


def _attio_post_retry(url, json_body, attempts=3, backoff=2.0):
    """POST to Attio with retries. See _attio_write_retry."""
    return _attio_write_retry("post", url, json_body, attempts, backoff)


def _attio_patch_retry(url, json_body, attempts=3, backoff=2.0):
    """PATCH to Attio with retries. See _attio_write_retry."""
    return _attio_write_retry("patch", url, json_body, attempts, backoff)


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
    # Top 10 VC flag -- 2026-07-28. `top10` has been a parameter on this
    # function since it was written, but nothing ever actually wrote it to
    # Attio (the docstring at upsert_deal's existing-deal branch even
    # claimed "the Top 10 VC flow also stamps its flag", which wasn't
    # true -- confirmed by grepping TOP10_VC_TITLE's only other reference,
    # its own definition). That's why every company sourced from the
    # /process-top10 pathway (PitchBook's own "Top 10 VC" saved search --
    # by construction, every one of these deals genuinely has a Top 10 VC
    # on the cap table) still read top10VC=false in hub-next: the signal
    # was computed correctly at import time and then silently dropped.
    # Only ever write "Yes" -- never write "No" here, since a deal
    # re-imported later through the regular (non-top10) pathway shouldn't
    # retroactively un-flag a company that a PRIOR top10 import already
    # confirmed is Top 10 VC-backed (this field means "confirmed Top 10 VC
    # at some point", not "this specific import run said so").
    if top10:
        top10_slug = deal_attr_slug(TOP10_VC_TITLE, default='top10_vc')
        ensure_select_option('deals', top10_slug, 'Yes')
        values[top10_slug] = 'Yes'
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

# Series B or earlier -> Radar. Matched by pattern, not by an exact set: the
# old exact-match set ({'Seed', 'Pre-Seed', 'Pre-A', 'Series A'}) missed every
# real-world variant PitchBook actually sends -- 'Series A1'/'Series A2' (see
# ensure_select_option's own docstring, which cites 'Series A2' as a value that
# shows up and isn't in the picklist yet), 'Seed Round', 'Angel', and any
# casing other than Title Case. Those all silently fell through to the caller's
# default stage (Qualified/Watchlist) instead of landing on Radar.
#
# Widened from "Series A or earlier" to "Series B or earlier" 2026-07-28
# (Oscar: "Radar should include Series B") -- see RADAR_PLAN.md Part I. ID8
def upsert_deal(row, company_record_id, stage="Watchlist", source=None, top10=False,
                top10_firms=None):
    """`top10_firms` is the PER-DEAL Top 10 match (match_top10 against this
    row's own investors); `top10` is the route-level flag /process-top10 sets
    for its whole file. Either one confirms Top 10 VC backing, so both feed the
    Attio flag -- but only the per-deal list can gate Radar placement, which is
    why it has to be resolved before this call rather than after it."""
    company_name = str(row.get('Companies', '')).strip()
    series = str(row.get('Series', '')).strip()
    stage, hub_tags = determine_placement(series, stage, top10_firms)
    if stage is None:
        # Below mandate with no Top 10 backer -- no Attio deal, no screening,
        # no hub page. Reported by run_pipeline, never silently discarded.
        return {"status": "filtered", "reason": "below B+ mandate, no Top 10 VC",
                "series": series, "hub_tags": []}
    top10 = bool(top10 or top10_firms)

    existing_id = find_deal(company_name, series)
    if existing_id:
        # Existing deal (this company+series already came in through ANOTHER
        # intake source -- the two PitchBook saved searches overlap heavily by
        # construction). Refresh investor links, backfill the associated
        # company, stamp the Top 10 VC flag.
        #
        # 2026-08-03: this branch used to `return "skipped"` and deliberately
        # never touch the stage ("Existing deal: never change its stage"),
        # which is exactly the bug Oscar identified. Whichever source landed
        # the company FIRST won permanently, and the second source's entire
        # contribution was dropped: no stage/tag re-evaluation, no email row,
        # no Stage 1 screening, no hub page. Only the top10 flag survived. So a
        # Series D Top 10 VC deal that the weekly drop had already filed stayed
        # wherever the weekly run put it, and a Series B never picked up its
        # second (radar) bucket.
        #
        # It now returns the resolved placement so run_pipeline can surface the
        # deal and reconcile it. Attio's own `stage` is still NOT patched here
        # -- that would fight a human who deliberately re-filed the deal in the
        # CRM, and Attio can only hold one stage anyway. Reconciliation happens
        # on the hub side, through the additive `tags` array that was built for
        # exactly this (hub-next/src/lib/stages.js), which is additive and so
        # cannot clobber a manual stage choice.
        patch_vals = {}
        patch_vals.update(resolve_investor_links(row, get_company_index()))
        if company_record_id:
            patch_vals["associated_company"] = [{
                "target_object": "companies", "target_record_id": company_record_id,
            }]
        # See build_attio_values' own comment -- only ever stamp "Yes", never
        # "No", so a later non-top10 re-import can't un-flag a company a
        # PRIOR top10 sweep already confirmed.
        if top10:
            top10_slug = deal_attr_slug(TOP10_VC_TITLE, default='top10_vc')
            ensure_select_option('deals', top10_slug, 'Yes')
            patch_vals[top10_slug] = 'Yes'
        if patch_vals:
            try:
                pr = _attio_patch_retry(
                    f"{ATTIO_API_BASE}/objects/deals/records/{existing_id}",
                    {"data": {"values": patch_vals}},
                )
            except requests.RequestException as exc:
                # Network failure after every retry. Reported as an error rather
                # than swallowed: this branch carries the whole contribution of a
                # re-seen deal (investor links, associated company, Top 10 flag),
                # and losing it silently is the bug 2026-08-03 already fixed once
                # at the routing level.
                print(f"DEAL PATCH {company_name}: network error after retries: {exc}")
                return f"error:network:{exc}"
            print(f"DEAL PATCH {company_name} top10={top10} keys={list(patch_vals)}: "
                  f"{pr.status_code} {pr.text[:200]}")
            if pr.status_code not in (200, 201):
                return f"error:{pr.status_code}:{pr.text[:300]}"
        return {"status": "existing", "record_id": existing_id,
                "stage": stage, "hub_tags": hub_tags}

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
        return {"status": "created", "record_id": record_id,
                "stage": stage, "hub_tags": hub_tags}
    return f"error:{resp.status_code}:{resp.text[:300]}"


# --- Shared pipeline logic ----------------------------------------------------

def run_pipeline(file_bytes, stage, source=None, top10=False):
    df = transform_excel(file_bytes)
    get_company_index(refresh=True)   # fresh Companies snapshot for investor matching
    # `filtered`: rows deliberately not filed (below B+ with no Top 10 backer).
    # Distinct from `errors` -- nothing went wrong, the deal just has no home.
    results = {"created": 0, "skipped": 0, "errors": [], "deals": [], "filtered": []}

    def clean(val):
        s = str(val or "").strip()
        return "" if s.lower() in ("nan", "none") else s

    for _, row in df.iterrows():
        website = str(row.get("Company Website", "") or "")
        company_name = str(row.get("Companies", "")).strip()
        description = clean(row.get("Description", ""))
        # Investor names off all three PitchBook investor columns, for Tier 1
        # matching alongside the domains resolved from 'Investors Websites'.
        #
        # Resolved BEFORE upsert_deal as of 2026-08-10. It used to run straight
        # after, which made the per-deal Top 10 match arrive too late to affect
        # anything that mattered: placement had already been decided without it
        # (so Radar took every below-B deal regardless of cap table) and the
        # Attio flag came from the route-level `top10` instead (so a Sequoia-led
        # Series B in the ordinary weekly drop never got stamped). The match
        # itself was fine -- it just fed the email and nothing else.
        investor_names = []
        for col in INVESTOR_REF_MAP:
            investor_names.extend(parse_investors(row.get(col)))
        investor_domains = sorted(set(parse_investor_websites(row.get('Investors Websites')).values()))
        top10_firms = di_tier1.match_top10(investor_domains, investor_names)

        # Filtered deals bail out HERE, before find_or_create_company -- a deal
        # we're not filing shouldn't leave a new Company record behind in Attio
        # as a side effect. upsert_deal re-derives the same placement and would
        # refuse it too; this is the cheaper gate, not the authoritative one.
        if determine_placement(clean(row.get("Series")), stage, top10_firms)[0] is None:
            results["filtered"].append({
                "company": company_name,
                "series": clean(row.get("Series")),
                "reason": "below B+ mandate, no Top 10 VC",
            })
            continue

        company_id = find_or_create_company(company_name, website, description) if website and website != 'nan' else None
        status = upsert_deal(row.to_dict(), company_id, stage, source, top10, top10_firms)

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
            # Which Top 10 firms are actually on this cap table, matched by
            # investor domain + name alias rather than by maintaining per-firm
            # portfolios (Oscar 2026-08-03). Feeds the hub's tier1Firms and is
            # strictly more precise than Attio's `contains` saved search --
            # see deal_intelligence/tier1_firms.py.
            "top10_firms":    top10_firms,
            "investor_domains": investor_domains,
        }
        status_name = status.get("status") if isinstance(status, dict) else None
        if status_name in ("created", "existing"):
            # BOTH brand-new and already-present deals now flow onward: they get
            # screened (if not already screened -- see _already_screened) and
            # rendered into the email. Previously only "created" did, so a
            # company the other intake source had already landed was silently
            # dropped from this run entirely. `is_new` lets the email separate
            # them into "new" vs "already in Attio — updated" sections.
            deal_row["record_id"] = status.get("record_id", "")
            deal_row["is_new"] = status_name == "created"
            deal_row["stage"] = status.get("stage", "")
            deal_row["hub_tags"] = status.get("hub_tags", [])
            results["deals"].append(deal_row)
            if status_name == "created":
                results["created"] += 1
            else:
                # Kept as `skipped` for backward compatibility -- n8n and
                # /process/status consumers already read this key.
                results["skipped"] += 1
        elif status_name == "filtered":
            # Defensive: run_pipeline's own pre-check above normally catches
            # these first. Reaching here means the two disagreed -- record it
            # as filtered, not as an error, so it can't inflate the error count.
            results["filtered"].append({
                "company": company_name,
                "series": status.get("series", ""),
                "reason": status.get("reason", ""),
            })
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

def _start_pipeline(stage, source, top10=False, flow=None):
    global _pipeline_state

    file_bytes, err = _read_file_bytes()
    if err:
        return err

    # Only ONE intake run may be in flight at a time: the service has a 512 MiB
    # limit and a single set of module-level state dicts, so two real pipelines
    # at once would both OOM and clobber each other's results.
    #
    # But a second caller has to QUEUE, not be rejected. This used to return 409
    # "already running" the instant it saw a run in progress, which silently
    # killed a whole weekly intake: the PitchBook and Top 10 Drive drops land
    # seconds apart, so n8n fires both flows nearly simultaneously
    # (2026-08-10: /process-top10 at 13:10:43, /process 409'd 9s later, 3ms in).
    # It went unnoticed before 2026-08-03 only because 3 gunicorn workers meant
    # 3 independent copies of _pipeline_state -- the guard could never see a run
    # happening in another process, so colliding drops both got through by
    # accident. 21225bb collapsed that to 1 worker for memory and status-polling
    # correctness, which made this guard real for the first time.
    #
    # Waiting is safe here because the caller's own budget below is reduced by
    # however long it queued, so queue + run together still land inside
    # gunicorn's 1800s --timeout rather than being cut off mid-response.
    queue_started = time.time()
    if not _pipeline_slot.acquire(timeout=_QUEUE_WAIT_SECONDS):
        with _pipeline_lock:
            busy = dict(_pipeline_state)
        return jsonify({"error": "busy — another intake run is still going",
                        "waited_seconds": round(time.time() - queue_started),
                        "state": busy}), 503
    queued_for = time.time() - queue_started

    # A per-run dict, held by reference, rather than a shared global the next run
    # would overwrite: whoever queued behind us rebinds _pipeline_state the
    # moment we finish, and reading the global after our own run completed would
    # then hand this caller the *next* flow's freshly-reset {"status": "running"}.
    run_state = {"status": "running", "queued_seconds": round(queued_for)}
    with _pipeline_lock:
        _pipeline_state = run_state

    try:
        t = threading.Thread(target=_run_pipeline_bg,
                             args=(file_bytes, stage, source, top10, flow, run_state),
                             daemon=True)
        t.start()
    except BaseException:
        # The worker releases the slot in its own finally; if it never started,
        # nothing else ever will and every later run would queue until timeout.
        _pipeline_slot.release()
        raise

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
    #
    # Budget is 1700s MINUS however long we sat in the queue, so a queued run
    # can't push the total past gunicorn's 1800s and lose the response anyway --
    # the exact failure mode the queue was added to prevent. The floor keeps a
    # long-queued caller from being handed a zero-length budget and returning
    # "running" immediately.
    deadline = time.time() + max(120, 1700 - queued_for)
    while time.time() < deadline:
        with _pipeline_lock:
            s = run_state.get("status")
        if s in ("complete", "error"):
            break
        time.sleep(1)

    with _pipeline_lock:
        state = dict(run_state)

    if state.get("status") == "error":
        return jsonify(state), 500

    # status is "complete" (full result) or "screening" (timed out — deals present,
    # scores still landing; poll /process/status for the finished version).
    return jsonify({**state, "poll": "/process/status"})


@app.route("/process", methods=["POST"])
def process():
    return _start_pipeline(stage="Qualified", source="ID8 Investments", flow="deal_flow")


@app.route("/process-watchlist", methods=["POST"])
def process_watchlist():
    return _start_pipeline(stage="Watchlist", source="ID8 Investments", flow="watchlist")


@app.route("/process-top10", methods=["POST"])
def process_top10():
    """Top 10 VC flow: tag deals Top 10 VC = Yes. Unlike the other drops this
    export carries deals at ANY series (it's every deal from a Top 10 firm, not
    a stage-filtered search), so placement is left entirely to
    determine_placement's series rule -- below B lands on Radar, B lands on
    both, above B lands on Qualified.

    `stage` here is the IN-MANDATE destination, not 'Radar'. It used to be
    RADAR_STAGE, which -- because determine_stage returned the default for any
    series above B -- pinned every Top 10 VC deal to Radar and kept C/D/E deals
    out of Qualified entirely. See determine_placement's docstring."""
    return _start_pipeline(stage=QUALIFIED_STAGE, source="ID8 Investments", top10=True,
                           flow="top10")


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

# Admission slot for /process, /process-watchlist, /process-top10 -- one intake
# run at a time, with the rest queueing rather than being turned away. See the
# long note in _start_pipeline for why rejecting was wrong. BoundedSemaphore so
# a double release (a bug) raises immediately instead of quietly permitting two
# concurrent runs on a 512 MiB service.
_pipeline_slot = threading.BoundedSemaphore(1)
# How long a queued caller waits for the slot before giving up with a 503. Sized
# against a real Stage 1 batch (550s and 467s are both in the Aug 2026 logs) so
# a normal collision always gets served, while leaving the 120s floor above.
_QUEUE_WAIT_SECONDS = 900


def _run_pipeline_bg(file_bytes, stage, source, top10, source_key=None, run_state=None):
    """Thread entry point: runs the worker, then always hands the admission slot
    back. Only this thread can release it, so an early return or an unhandled
    crash inside the worker must not be able to strand the slot -- if it did,
    every later intake run would queue for the full _QUEUE_WAIT_SECONDS and then
    503, turning one bad run into a permanently wedged endpoint.
    """
    if run_state is None:          # direct callers (tests, /recover-*) keep the global
        run_state = _pipeline_state
    try:
        _run_pipeline_worker(file_bytes, stage, source, top10, source_key, run_state)
    except BaseException:
        print("PIPELINE WORKER CRASHED:", traceback.format_exc())
        with _pipeline_lock:
            run_state.update({"status": "error", "error": "pipeline worker crashed"})
    finally:
        _pipeline_slot.release()


def _run_pipeline_worker(file_bytes, stage, source, top10, source_key, run_state):
    """Background worker for /process, /process-watchlist, /process-top10.

    Phase 1 (fast): ingest deals into Attio → state becomes "screening".
    Phase 2 (slow): Perplexity Stage 1 scoring → state becomes "complete".

    n8n should poll /process/status until status == "complete" to get fit scores.
    If PERPLEXITY_API_KEY is absent, phase 2 is skipped and status goes straight
    to "complete" with no fit fields.
    """
    with _pipeline_lock:
        run_state.update({"status": "running", "created": 0, "skipped": 0,
                                 "errors": [], "deals": [], "error": None})
    try:
        results = run_pipeline(file_bytes, stage=stage, source=source, top10=top10)
    except Exception as e:
        print("PIPELINE ERROR:", traceback.format_exc())
        with _pipeline_lock:
            run_state.update({"status": "error", "error": str(e)})
        return

    # Publish Attio-ingestion results immediately so a short-polling caller can
    # already render the deal list while screening is in progress.
    with _pipeline_lock:
        run_state.update({"status": "screening", **results})

    # ── Stage 1 screening ────────────────────────────────────────────────────
    # Screen every deal this run surfaced (new AND already-in-Attio) EXCEPT the
    # ones that already have a screen on file. Before 2026-08-03 this list was
    # "created deals only", which got both halves wrong: a company the other
    # intake source had already landed was never screened at all, while a
    # genuinely re-created deal could be re-screened at full
    # sonar-deep-research cost. `_already_screened` is a cheap single-doc
    # Firestore read per deal (see firestore_push.has_screen).
    all_deals = results.get("deals", [])
    unscreened, already_screened = [], []
    for d in all_deals:
        # Derive the slug via fit_note.company_id on a DealInput, NOT
        # slugify(name): company_id prefers the website domain
        # ('acme.com' -> 'acme') and only falls back to a name slug, so
        # slugifying the raw PitchBook company name (which carries a category
        # suffix, e.g. 'Pocket (Business/Productivity Software)') would look up
        # a document that does not exist and report every deal as unscreened.
        probe = di_schemas.DealInput(
            record_id=d.get("record_id") or "", name=d.get("company", ""),
            domain=d.get("website") or None,
        )
        slug = di_fit_note.company_id(probe)
        try:
            prior = di_firestore_push.latest_screen(slug) if slug else None
        except Exception as exc:
            # Never let a Firestore hiccup silently skip screening -- default to
            # screening the deal, same fail-open posture as the rest of this path.
            print(f"[latest_screen] {slug}: {exc}")
            prior = None
        d["already_screened"] = prior is not None
        if prior:
            # Carry the prior score so the email's re-seen section can report a
            # real number instead of just naming the company.
            d["prior_screen"] = prior
            d["hub_url"] = d.get("hub_url") or di_fit_note.hub_url(probe)
        d["_slug"] = slug
        (already_screened if prior else unscreened).append(d)
    results["reused_screens"] = len(already_screened)
    if already_screened:
        print(f"SCREENING: reusing {len(already_screened)} existing screen(s), "
              f"scoring {len(unscreened)} new: "
              f"{[d.get('company') for d in already_screened]}")

    # ── Placement (hub stage + additive tags) ────────────────────────────────
    # Applied to EVERY deal in the run, screened or not, and BEFORE screening so
    # a company created by push_company_screen_firestore below already carries
    # the right primary stage instead of its hardcoded 'qualified' default.
    #
    # This is the step that actually makes "a deal can be in more than one
    # stage" real for intake: determine_placement's tags were previously
    # computed and then dropped. It matters most for a re-seen deal, which skips
    # screening entirely and so gets no other Firestore write at all -- exactly
    # the deal whose second-source placement was being lost.
    placed, placement_errors = 0, []
    for d in all_deals:
        slug, tags = d.get("_slug"), d.get("hub_tags") or []
        stage_lc = str(d.get("stage") or "").strip().lower() or None
        if not slug:
            continue
        try:
            if di_firestore_push.apply_placement(
                    slug, tags, stage=stage_lc,
                    top10_firms=d.get("top10_firms") or None).get("written"):
                placed += 1
        except Exception as exc:
            # Non-blocking: placement is metadata. Losing it must not abort a run
            # whose Attio write and screening already succeeded.
            print(f"[apply_placement] {slug}: {exc}")
            placement_errors.append({"company": d.get("company"), "error": str(exc)})
    results["placements_applied"] = placed
    if placement_errors:
        results["placement_errors"] = placement_errors

    new_deals = unscreened
    gh_token_present = bool(os.environ.get("GH_TOKEN"))
    # Always publish: hub-next (Firestore) is the live hub and needs no GH_TOKEN
    # at all -- pipeline.screen() only consults GH_TOKEN itself, internally, to
    # decide whether the OLD git-based hub also gets pages pushed. Gating this
    # whole flag on GH_TOKEN (as it used to) meant that whenever GH_TOKEN was
    # absent/rotated, Stage 1 screening still ran (burning Perplexity credits)
    # but push_company_screen_firestore() was never even called, so nothing
    # ever landed in hub-next -- silently, with no error anywhere.
    publish = True
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
                    # Per-deal Top 10 match, so a screen pushed from the weekly
                    # drop carries the same top10VC signal the /process-top10
                    # route sets. Only ever True -- never False, so this can't
                    # un-flag a company an earlier confirmed match already set.
                    top10=True if d.get("top10_firms") else None,
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
        # Guarded on GH_TOKEN specifically (not `publish`, which is now always
        # True for hub-next's sake) -- without GH_TOKEN no git pages were
        # pushed, so there is nothing new for the OLD hub to redeploy.
        if gh_token_present:
            try:
                build_id, err = _start_hub_build()
                if err:
                    print(f"HUB BUILD trigger failed: {err}")
                else:
                    results["hub_build_id"] = build_id
                    print(f"HUB BUILD triggered: {build_id}")
            except Exception:
                print("HUB BUILD trigger error:", traceback.format_exc())

    # ── Intake email ─────────────────────────────────────────────────────────
    # Built here, for EVERY flow, from the full deal list (new + re-seen, with
    # whatever fit fields landed above). This replaces the per-flow HTML that
    # each n8n Code node used to assemble itself -- those had drifted so that
    # only the PitchBook weekly email rendered fit scores at all, and none of
    # them could show a re-seen deal. n8n now just uses {{ $json.email_html }}.
    #
    # Deliberately outside the `if new_deals and PERPLEXITY_API_KEY` block: a
    # run with nothing new to screen (every deal already on file) still needs
    # its email, which is exactly the case that used to go out empty.
    try:
        title = EMAIL_TITLES.get(source_key, "Deal Intake")
        results["email_html"] = di_email_format.intake_email_html(
            results.get("deals", []), title=title,
            filtered=results.get("filtered") or None)
        results["email_text"] = di_email_format.intake_email_text(
            results.get("deals", []), title=title,
            filtered=results.get("filtered") or None)
        # Built with .day rather than strftime('%-d'): the no-pad directive is a
        # glibc/BSD extension, not portable, and this runs both on Cloud Run and
        # on a Mac laptop.
        now = datetime.now()
        results["email_subject"] = (
            f"{title} — {now:%B} {now.day}, {now:%Y} "
            f"({results.get('created', 0)} new"
            + (f", {results.get('skipped', 0)} updated" if results.get('skipped') else "")
            + ")"
        )
    except Exception:
        print("EMAIL RENDER ERROR:", traceback.format_exc())

    with _pipeline_lock:
        run_state.update({"status": "complete", **results})


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


def _fit_from_response_row(d: dict):
    """Rebuild (DealInput, DealFit) from one row of a /process response body.

    Recovery path for a run whose screening succeeded but whose hub push never
    happened -- e.g. the GH_TOKEN-gated Firestore bug fixed 2026-08-03, where
    Stage 1 ran and paid for Perplexity but push_company_screen_firestore was
    never called. n8n keeps each execution's node output for 14 days
    (EXECUTIONS_DATA_MAX_AGE=336 in n8n-cloudrun/deploy.sh), so the HTTP Request
    node's stored output is a complete copy of that response and can be replayed
    here at zero research cost.

    WHAT SURVIVES: fit_score, raw_score, gate, tier, the FULL rationale (the
    truncation to 220 chars happened only in the email HTML, not the response),
    confidence, hard_auto_pass + reason, citations, and per-dimension
    key/score/evidence.

    WHAT DOES NOT: subcategory-level findings. _run_pipeline_bg only ever
    serialized {key, score, evidence} per dimension, so the point tier of the
    three-tier rationale was never in the response to begin with -- it existed
    only in the DealFit object in memory. A screen rebuilt here therefore
    renders its dimensions and evidence but has no subcategory hover detail.
    That is a deliberate, visible gap, not a silent one: the caller gets
    `subcategories_recovered: false` per deal so it's clear these are
    reconstructed screens rather than fresh ones.
    """
    deal = di_schemas.DealInput(
        record_id=d.get("record_id") or "",
        name=d.get("company") or "",
        domain=d.get("website") or None,
        round=d.get("series") or None,
        hq=d.get("hq_location") or None,
        lead_investors=d.get("lead_investors") or None,
        round_date=d.get("deal_date") or None,
        description=d.get("description") or None,
    )
    params = [
        di_schemas.ParamScore(
            key=p.get("key", ""), score=float(p.get("score") or 0),
            weight=round(100.0 / len(di_rubric.PARAMS), 2) if di_rubric.PARAMS else 0.0,
            evidence=p.get("evidence", ""), subcategories=[],
        )
        for p in (d.get("fit_params") or []) if p.get("key")
    ]
    fit = di_schemas.DealFit(
        record_id=deal.record_id, name=deal.name,
        fit_score=float(d.get("fit_score") or 0),
        raw_score=float(d.get("fit_raw_score") or d.get("fit_score") or 0),
        params=params,
        rationale=d.get("fit_rationale") or "",
        confidence=d.get("fit_confidence") or "medium",
        gate=bool(d.get("fit_gate")),
        quality_tier=d.get("fit_tier") or "pass",
        citations=d.get("fit_citations") or [],
        hard_auto_pass=bool(d.get("fit_hard_auto_pass")),
        hard_auto_pass_reason=d.get("fit_hard_auto_pass_reason") or "",
    )
    return deal, fit


def _extract_deals(body):
    """Pull the deal rows out of whatever shape got pasted in.

    Deliberately tolerant, because the source is a copy-paste out of the n8n UI
    and n8n represents the same data three different ways depending on where you
    copy from: the raw response object, an array of workflow items, or that array
    with each item wrapped in {"json": {...}}. Requiring one exact shape here
    would just mean a round-trip of 400s to discover which one you happened to
    grab. Recognized:
        {"deals": [...]}                  the /process response body
        [{"deals": [...]}, ...]           n8n items
        [{"json": {"deals": [...]}}, ...] n8n items, wrapped
        [{"company": ..., ...}, ...]      a bare array of deal rows
    """
    def rows_from(obj):
        if isinstance(obj, dict):
            if isinstance(obj.get("deals"), list):
                return obj["deals"]
            if isinstance(obj.get("json"), dict):
                return rows_from(obj["json"])
            # A single deal row on its own.
            if "company" in obj or "fit_score" in obj:
                return [obj]
        return []

    if isinstance(body, dict):
        return [r for r in rows_from(body) if isinstance(r, dict)]
    if isinstance(body, list):
        out = []
        for item in body:
            out.extend(rows_from(item))
        # A bare array of deal rows that rows_from didn't claim.
        if not out:
            out = [i for i in body if isinstance(i, dict) and
                   ("company" in i or "fit_score" in i)]
        return [r for r in out if isinstance(r, dict)]
    return []


@app.route("/recover-screens", methods=["POST"])
def recover_screens():
    """Replay an already-paid-for screening run into hub-next, with no Perplexity calls.

    Body: the /process response body, or just its deals array:
        {"deals": [ ... ]}          <- paste from n8n's HTTP Request node output
    Optional: {"dry_run": true} to report what WOULD be pushed and change nothing.

    Only rows that actually carry a fit_score are pushed; a row with no score was
    never screened and there is nothing to recover for it. Existing screens are
    left alone unless {"overwrite": true} -- so this is safe to re-run, and can't
    stomp a real screen with a reconstructed one that lacks subcategories."""
    if not _require_internal_secret():
        return jsonify({"error": "forbidden"}), 403
    body = request.get_json(silent=True)
    deals = _extract_deals(body)
    if not deals:
        return jsonify({
            "error": "no deals found in the request body",
            "expected": ("the /process response body, n8n's node output (an array of "
                          "items, with or without the {json:{...}} wrapper), or a bare "
                          "array of deal rows"),
            "hint": ("save the JSON to a file and send it with  -d @deals.json  rather "
                      "than inline, and pass ?dry_run=1 in the URL"),
        }), 400
    # dry_run/overwrite are read from the QUERY STRING as well as the body,
    # because the whole point is to POST an unmodified n8n node output -- that
    # JSON has no dry_run key in it, and requiring one hand-edited in would mean
    # the safe preview is the awkward path and the destructive one is the easy
    # path. Query string wins when present.
    def _flag(name):
        q = request.args.get(name)
        if q is not None:
            return q.lower() not in ("", "0", "false", "no")
        return bool((body or {}).get(name)) if isinstance(body, dict) else False
    dry_run = _flag("dry_run")
    overwrite = _flag("overwrite")

    pushed, skipped, errors = [], [], []
    for d in deals:
        if not isinstance(d, dict):
            continue
        name = d.get("company") or "(unnamed)"
        if d.get("fit_score") is None:
            skipped.append({"company": name, "reason": "no fit_score in this row — never screened"})
            continue
        try:
            deal, fit = _fit_from_response_row(d)
            slug = di_fit_note.company_id(deal)
            if not slug:
                skipped.append({"company": name, "reason": "could not derive a slug"})
                continue
            if not overwrite and di_firestore_push.has_screen(slug):
                skipped.append({"company": name, "slug": slug,
                                "reason": "already has a screen on file (pass overwrite:true to replace)"})
                continue
            if dry_run:
                pushed.append({"company": name, "slug": slug, "fit_score": fit.fit_score,
                                "dry_run": True, "subcategories_recovered": False})
                continue
            docx_bytes = di_fit_note.build_docx_bytes(fit, deal)
            di_firestore_push.push_company_screen_firestore(
                fit, deal, slug, docx_bytes, source="attio")
            pushed.append({"company": name, "slug": slug, "fit_score": fit.fit_score,
                            "gate": fit.gate, "subcategories_recovered": False})
        except Exception as exc:
            print(f"[recover-screens] {name}: {traceback.format_exc()}")
            errors.append({"company": name, "error": str(exc)})

    return jsonify({
        "pushed": len(pushed), "skipped": len(skipped), "errors": len(errors),
        "dry_run": dry_run,
        "note": ("Reconstructed from a stored /process response: dimensions, evidence, "
                 "rationale and citations are complete, but subcategory-level findings "
                 "were never serialized into that response and cannot be recovered "
                 "without re-screening."),
        "details": {"pushed": pushed, "skipped": skipped, "errors": errors},
    })


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


# hub-next stage key -> Attio's "stage" status-attribute title. Inverse of
# deal_intelligence.config.ATTIO_STAGE_MAP (which maps Attio's raw title,
# lowercased, back onto these same keys for the read/import direction) --
# see hub-next/src/lib/stages.js's STAGES for where these keys come from.
HUB_STAGE_TO_ATTIO_TITLE = {
    "watchlist": "Watchlist",
    "pipeline": "Pipeline",
    "qualified": "Qualified",
    "radar": "Radar",
    "invested": "Invested",
}


@app.route("/update-deal-stage", methods=["POST"])
def update_deal_stage():
    """Push a stage change made by hand in hub-next (the per-row dropdown --
    see hub-next/src/lib/companies.js's updateCompanyStage) back onto the
    matching Attio Deal record, so the two don't silently drift apart. This
    is the one direction that previously didn't exist at all -- Attio ->
    hub-next sync (push_company_from_attio) has existed for a while, but a
    stage edit made directly in hub-next used to stay siloed in Firestore
    forever. Body: {"record_id": "<attio deal record id>", "stage": "<hub-next
    stage key, e.g. 'qualified'>"}. Same write shape fix_radar_stages already
    uses above (status attribute -> [{"status": "<Title>"}]) -- see
    hub-next/src/app/(hub)/docs/projects/pitchbook-attio/page.jsx's "Write
    values are not read values" note for why that shape matters.
    Best-effort by design: hub-next's own PATCH call treats a failure here as
    non-fatal (Firestore is hub-next's own source of truth regardless of
    whether the Attio mirror succeeds), so this returns a normal error
    response rather than anything hub-next needs to retry on its own."""
    if not _require_internal_secret():
        return jsonify({"error": "forbidden"}), 403
    body = request.get_json(silent=True) or {}
    record_id = (body.get("record_id") or "").strip()
    stage_key = (body.get("stage") or "").strip().lower()
    if not record_id:
        return jsonify({"error": "'record_id' is required"}), 400
    title = HUB_STAGE_TO_ATTIO_TITLE.get(stage_key)
    if not title:
        return jsonify({"error": f"unknown stage {stage_key!r}, must be one of {sorted(HUB_STAGE_TO_ATTIO_TITLE)}"}), 400

    try:
        resp = _attio_patch_retry(
            f"{ATTIO_API_BASE}/objects/deals/records/{record_id}",
            {"data": {"values": {"stage": [{"status": title}]}}},
        )
    except requests.RequestException as exc:
        return jsonify({"error": f"Attio unreachable after retries: {exc}"}), 502
    if resp.status_code not in (200, 201):
        return jsonify({"error": f"Attio PATCH failed: {resp.text[:300]}"}), 502
    return jsonify({"ok": True, "record_id": record_id, "stage": title})


# hub-next edit -> the Attio Deal attribute it writes, and how that attribute's
# value has to be shaped. These are the SAME slugs the import direction reads
# back (deal_intelligence/config.py's READ_SLUGS: round -> "series",
# round_date -> "deal_date"), which is the whole point: an edit made in the hub
# has to land where the next import will look, or it comes straight back as a
# hub-vs-Attio conflict on the next reconciler run.
#
# `series` is a SELECT, so it needs ensure_select_option first -- a write
# referencing an unknown option is rejected outright (see that function's
# docstring), and a partner typing "Series B1" in the hub is exactly how an
# unknown option arrives. Write shapes match build_attio_values: select is a
# plain string, date is [{"value": "YYYY-MM-DD"}].
HUB_EDITABLE_DEAL_FIELDS = {
    "series": "select",
    "deal_date": "date",
}


@app.route("/update-deal-fields", methods=["POST"])
def update_deal_fields():
    """Push a Series or Deal Date edited by hand in hub-next (the deals tables'
    inline Series box and Deal Date picker -- see hub-next/src/lib/companies.js's
    updateCompanyRound/updateCompanyRoundDate) back onto the matching Attio Deal
    record. The field-level sibling of /update-deal-stage above, and the same
    best-effort contract: hub-next treats a failure here as non-fatal because
    Firestore is its own source of truth, so this returns a normal error
    response rather than anything the caller retries.

    Body: {"record_id": "<attio deal record id>", "series": "Series B",
    "deal_date": "2026-08-12"}. Both fields are optional; whichever is PRESENT
    is written, and an explicit null clears that attribute in Attio (an
    unclosed round genuinely has no Deal Date, and the hub lets you clear one
    entered by mistake). Sending neither is a 400 rather than a silent no-op --
    that only ever means the caller sent the wrong body shape.
    """
    if not _require_internal_secret():
        return jsonify({"error": "forbidden"}), 403
    body = request.get_json(silent=True) or {}
    record_id = (body.get("record_id") or "").strip()
    if not record_id:
        return jsonify({"error": "'record_id' is required"}), 400

    values, written = {}, []
    for slug, field_type in HUB_EDITABLE_DEAL_FIELDS.items():
        if slug not in body:
            continue
        raw = body[slug]
        val = "" if raw is None else str(raw).strip()
        written.append(slug)
        if not val:
            # Attio clears an attribute with an empty list, not with null --
            # same shape build_attio_values uses to write one, minus the value.
            values[slug] = []
        elif field_type == "select":
            ensure_select_option("deals", slug, val)
            values[slug] = val
        else:
            values[slug] = [{"value": val}]

    if not values:
        return jsonify({"error": f"nothing to write -- send at least one of {sorted(HUB_EDITABLE_DEAL_FIELDS)}"}), 400

    try:
        resp = _attio_patch_retry(
            f"{ATTIO_API_BASE}/objects/deals/records/{record_id}",
            {"data": {"values": values}},
        )
    except requests.RequestException as exc:
        return jsonify({"error": f"Attio unreachable after retries: {exc}"}), 502
    if resp.status_code not in (200, 201):
        return jsonify({"error": f"Attio PATCH failed: {resp.text[:300]}"}), 502
    return jsonify({"ok": True, "record_id": record_id, "written": written})


def _extract_attio_record_id(body):
    """Dig the Deal record id out of whatever shape the caller sent.

    Attio's native workflow "Send HTTP request" action lets you template the
    body freely, so the documented shape here is the simplest one:
    {"record_id": "{{ record.id.record_id }}"}. But Attio's own reference chips
    are easy to mis-wire (cc-attio-sync/README.md has a whole section on a
    List-Entry-vs-Record mismatch that produced exactly that class of bug), and
    Attio's webhook-subscription payloads use a different nesting again -- so
    every shape that has ever plausibly arrived is accepted rather than 400ing
    on a body that clearly identifies a record. In order: the flat key, Attio's
    `data.id.record_id` record shape, and its webhook `events[].id.record_id`.

    An UNRENDERED template is rejected rather than passed through. Attio's JSON
    body editor types each property as a literal String by default, so a value
    typed by hand arrives as the eight characters `{{ record.id.record_id }}`
    instead of an id -- which is what the first live run did on 2026-08-13.
    Forwarded blindly, that produced a 502 quoting a URL-encoded
    `/records/%7B%7B%20record.id.record_id%20%7D%7D`, which reads like an Attio
    API outage rather than a mis-wired chip. Caught here it's a 400 naming the
    real problem, which is the difference between a five-minute fix and an hour.
    """
    if not isinstance(body, dict):
        return None
    for key in ("record_id", "recordId", "id"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            if "{{" in val or "}}" in val:
                return None
            return val.strip()
        if isinstance(val, dict) and isinstance(val.get("record_id"), str):
            return val["record_id"].strip()
    data = body.get("data")
    if isinstance(data, dict):
        found = _extract_attio_record_id(data)
        if found:
            return found
    events = body.get("events")
    if isinstance(events, list):
        for ev in events:
            found = _extract_attio_record_id(ev if isinstance(ev, dict) else {})
            if found:
                return found
    return None


def _mandate_scan_target(push_result):
    """Which doc, if any, a webhook push left unscored and worth scoring.

    Only genuinely new material: a brand-new company, or a new round doc. An
    existing company that merely got its Deal Date refreshed already has its
    screen, and rescoring it on every webhook fire would spend real Perplexity
    money on each retry Attio makes.
    """
    if push_result.get("created"):
        return push_result.get("slug")
    extra = push_result.get("additionalRound") or {}
    if extra.get("created"):
        return extra.get("id")
    return None


def _maybe_start_mandate_scan(deal, push_result):
    """Score a newly-imported deal in the BACKGROUND, if it fits the mandate.

    Oscar, 2026-08-13: "auto scan if fits mandate but put it already in there
    for us to have it already in the hub and then run the scoring in the
    background". So the import is never blocked on the scan -- the doc is
    already written by the time this is called, and this only ever adds a
    score to it. The webhook returns immediately; Attio sees a fast 200 rather
    than sitting through several minutes of sonar-deep-research and timing out.

    The gate is `placement.expected_placement`, the same rule deal_sync
    reconciles against (Tier 1 (33) + above B -> Qualified; Top 10 + B-or-below
    -> Radar). `stage is None` means the rule gives the deal no automatic home,
    which is exactly the population not worth paying to score automatically --
    it stays in the hub, unscored, for manual triage.

    Returns a dict that goes into the webhook response, so Attio's own Runs
    view says whether a scan started and why not when it didn't -- otherwise
    "did it scan?" is only answerable by digging through Cloud Run logs.
    """
    slug = _mandate_scan_target(push_result)
    if not slug:
        return {"started": False, "reason": "nothing new to score"}
    if not os.environ.get("PERPLEXITY_API_KEY"):
        return {"started": False, "reason": "PERPLEXITY_API_KEY not configured"}

    names = [n for n in (deal.lead_investors or "").split(",") if n.strip()]
    top10 = di_tier1.match_top10(investor_domains=deal.investor_domains, investor_names=names)
    tier1_33 = di_tier1.match_tier1_33(investor_names=names)
    stage, _tags, reason = expected_placement(deal.round, top10_firms=top10, tier1_33_firms=tier1_33)
    if not stage:
        return {"started": False, "reason": reason or "outside mandate", "slug": slug}

    job_id = uuid.uuid4().hex
    _start_chat_job(job_id, {
        "status": "running", "type": "stage1_attio_webhook", "companySlug": slug,
        "label": f"{deal.name} — auto-scan (Attio)",
        "createdAt": datetime.utcnow().isoformat() + "Z",
    })
    threading.Thread(target=_run_company_screen, args=(job_id, slug, deal), daemon=True).start()
    return {"started": True, "job_id": job_id, "slug": slug,
            "placement": stage, "reason": reason, "poll": f"/jobs/{job_id}"}


@app.route("/attio-deal-created", methods=["POST"])
def attio_deal_created():
    """One deal, straight from Attio, the moment it's created.

    Oscar, 2026-08-13: "for Attio to the Hub make it so that there's a workflow
    in Attio (native) it triggers a http request that will deduce the new deal
    created and check if its on hub and add it (many times deal pipeline will
    come like this)." Until now the only Attio -> hub path was the BULK pull
    (/import-attio-deals, run by hand from the hub's Admin page), so a deal
    typed straight into Attio -- which is how a lot of pipeline actually
    arrives -- sat invisible to the hub until someone remembered to run that
    import.

    Body: {"record_id": "<attio deal record id>"} (see
    _extract_attio_record_id for the other shapes accepted). The deal is then
    re-read from Attio rather than trusted from the webhook body, so it's
    parsed by exactly the same code path as a bulk import (attio_io.get_deal ->
    _parse_deal_record) and picks up fields the trigger payload wouldn't carry
    -- above all the domain, which lives on the linked Company record, not the
    Deal.

    "Check if it's on hub and add it" is push_company_from_attio's existing
    contract, unchanged: it upserts by the same company slug every other import
    path uses, so a deal the hub already has refreshes rather than duplicating,
    and the response's `created` flag says which happened. That makes this
    endpoint safe to fire on every creation, and safe for Attio to retry.

    Called by Attio directly, on ATTIO_WEBHOOK_SECRET -- see
    _require_attio_webhook_auth. The original design routed Attio through
    hub-next's /api/attio/deal-created because this service was believed to be
    IAM-private and hub-next public. Checked 2026-08-13 and both halves are
    backwards: hub-next now sits behind Cloud IAP, which 302s any request
    without a Google-signed OIDC token (so Attio can never reach it), while
    THIS service answers the open internet unauthenticated. The hub-next proxy
    is left in place and still works -- it authenticates with X-Internal-Secret
    as before -- but it is no longer the path Attio takes.
    """
    if not _require_attio_webhook_auth():
        return jsonify({"error": "forbidden"}), 403
    body = request.get_json(silent=True) or {}
    record_id = _extract_attio_record_id(body)
    if not record_id:
        # `sent` echoes the raw value back, truncated. When the cause is an
        # unrendered chip, seeing your own "{{ record.id.record_id }}" quoted
        # in the response is what makes the problem obvious -- received_keys
        # alone looks correct in exactly that case, because the KEY is right
        # and only the value is wrong.
        raw = body.get("record_id") if isinstance(body, dict) else None
        return jsonify({
            "error": "could not find a Deal record id in the request body",
            "expected": '{"record_id": "<attio deal record id>"}',
            "received_keys": sorted(body.keys())[:20] if isinstance(body, dict) else None,
            "sent": raw[:80] if isinstance(raw, str) else None,
            "hint": ("the value looks like an unrendered Attio template -- in the workflow's "
                     "JSON body editor, use the {x} button on that property to insert the "
                     "record id as a variable instead of typing it as a String")
                    if isinstance(raw, str) and "{{" in raw else None,
        }), 400

    try:
        found = di_attio_io.get_deal(record_id)
    except Exception as e:
        print("ATTIO DEAL CREATED fetch error:", traceback.format_exc())
        return jsonify({"error": f"Attio fetch failed: {e}"}), 502
    if found is None:
        # Not an error the caller can act on -- the record genuinely isn't
        # there any more. 200 so Attio doesn't retry a deleted record forever.
        return jsonify({"ok": True, "record_id": record_id, "skipped": "no such Attio deal record"})

    deal, attio_stage = found
    try:
        result = di_firestore_push.push_company_from_attio(deal, attio_stage)
    except Exception as e:
        print("ATTIO DEAL CREATED push error:", traceback.format_exc())
        return jsonify({"error": f"Firestore push failed: {e}"}), 500
    # Best-effort and non-blocking, like every other side effect on this path:
    # the company is already in the hub by now, so a scan that can't start is
    # a missing score, not a failed import.
    try:
        scan = _maybe_start_mandate_scan(deal, result)
    except Exception as e:
        print("ATTIO DEAL CREATED scan-start error:", traceback.format_exc())
        scan = {"started": False, "reason": f"scan could not be started: {e}"}
    return jsonify({
        "ok": True,
        "record_id": record_id,
        "scan": scan,
        "name": deal.name,
        "attio_stage": attio_stage,
        "series": deal.round,
        **result,
    })


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
    """One-time backfill: seeds round/roundDate/roundSize from their
    origin.* counterparts for companies that existed before those top-level
    fields were written (roundDate/roundSize as of 2026-07-28 -- see
    deal_intelligence.firestore_push.backfill_company_rounds for why a
    re-screen alone doesn't fix an existing company's blank Deal Date)."""
    if not _require_internal_secret():
        return jsonify({"error": "forbidden"}), 403
    return jsonify(di_firestore_push.backfill_company_rounds())


@app.route("/backfill-top10-vc", methods=["POST"])
def backfill_top10_vc():
    """One-time seed for hub-next's `top10VC` field from a pasted snapshot of
    Attio's "Top 10 VC" Deals-object view -- see
    deal_intelligence.firestore_push.backfill_top10_vc. Body: {"names": [...]}."""
    if not _require_internal_secret():
        return jsonify({"error": "forbidden"}), 403
    names = (request.get_json(silent=True) or {}).get("names") or []
    if not isinstance(names, list) or not names:
        return jsonify({"error": "'names' must be a non-empty array"}), 400
    return jsonify(di_firestore_push.backfill_top10_vc(names))


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


def _run_screen_deals(job_id, dry_run, stage1_only, publish, skip_screened=True):
    try:
        result = asyncio.run(di_pipeline.run(dry_run=dry_run, stage1_only=stage1_only,
                                             publish=publish, skip_screened=skip_screened))
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
    # Default True as of 2026-08-03 (was False). The old default belonged to a
    # world where "publish" only meant the OLD static hub -- pages written to
    # disk and committed to git, impossible from an ephemeral Cloud Run
    # container. That reasoning is now stale: `publish` also gates the hub-next
    # Firestore push, which is a plain API write and works fine from here. With
    # it defaulting off, the obvious call ran full sonar-deep-research on the
    # whole backlog and then pushed NOTHING to the hub -- the same
    # spend-money-and-silently-drop-the-result failure as the GH_TOKEN bug fixed
    # in 932b069, just reached from the other direction. Pass
    # {"publish": false} to deliberately score without publishing.
    publish = bool(body.get("publish", True))
    # Default True: only screen deals that don't already have a screen on file,
    # so this endpoint is the cheap "fill in whatever is missing" pass and is
    # safe to re-run. Pass {"rescreen_all": true} to deliberately re-screen the
    # whole Qualified pool (e.g. after a rubric change). See pipeline.run.
    skip_screened = not bool(body.get("rescreen_all", False))
    current = _get_chat_job(_SCREEN_DEALS_JOB_ID)
    if current and current.get("status") == "running":
        return jsonify({"error": "already running", "state": current}), 409
    _start_chat_job(_SCREEN_DEALS_JOB_ID, {
        "status": "running", "type": "screen_deals_backlog", "label": "Attio qualified backlog",
        "createdAt": datetime.utcnow().isoformat() + "Z",
    })
    threading.Thread(target=_run_screen_deals,
                     args=(_SCREEN_DEALS_JOB_ID, dry_run, stage1_only, publish, skip_screened),
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


def _require_attio_webhook_auth():
    """Auth for the one route a third party (Attio) calls directly.

    Verified 2026-08-13: this service answers unauthenticated requests from the
    open internet, and INTERNAL_API_SECRET is not set on it -- so
    _require_internal_secret alone is a no-op and every route here, this one
    included, is currently open. That was survivable while only n8n and hub-next
    knew the URL; it is not once an Attio workflow is pointed at it, because the
    URL then lives in a third-party UI.

    So this route gets its OWN secret rather than borrowing the internal one:
    the value pasted into Attio's header field should not also be the credential
    that unlocks /update-deal-stage and friends. Once ATTIO_WEBHOOK_SECRET is
    set the gate is strict -- an absent or wrong header is a 403, with no
    fallback to the permissive _require_internal_secret path.

    Both header spellings are accepted for the same reason hub-next's proxy
    accepts both (Attio's action UI is a free-text header field, and
    X-Attio-Webhook-Secret / X-Webhook-Secret are trivially confusable).
    hub-next's proxy still authenticates the way it always did, via
    X-Internal-Secret, so the older path keeps working unchanged.
    """
    expected = os.environ.get("ATTIO_WEBHOOK_SECRET")
    if not expected:
        return _require_internal_secret()
    provided = (request.headers.get("X-Attio-Webhook-Secret")
                or request.headers.get("X-Webhook-Secret"))
    if provided == expected:
        return True
    internal = os.environ.get("INTERNAL_API_SECRET")
    return bool(internal) and request.headers.get("X-Internal-Secret") == internal


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


def _run_company_stage2(job_id: str, slug: str, deal: "di_schemas.DealInput"):
    """Same idea as _run_company_screen, but for Stage 2 (deep research memo)
    on an already-known, already-Stage-1-screened company row -- pins `slug`
    so the memo is persisted against this company's own doc (see
    firestore_push.push_company_memo_firestore) instead of only living in the
    ephemeral chat_jobs doc the way a Research Chat-started Stage 2 still does."""
    try:
        memo = asyncio.run(di_stage2_research.deep_research(deal))
        di_firestore_push.push_company_memo_firestore(memo, slug)
        _set_chat_job(job_id, {"status": "complete", "stage": 2, "memo": memo.to_dict(), "slug": slug})
    except Exception as e:
        _set_chat_job(job_id, {"status": "error", "stage": 2, "error": str(e)})


@app.route("/company-stage2/<slug>", methods=["POST"])
def company_stage2(slug):
    """Start Stage 2 (deep research memo) for one specific, already-known
    company row -- the table-row equivalent of Research Chat's Stage 2, for a
    company that already cleared Stage 1. Body:
      {"name": "Acme", "domain": "acme.com", "round": "Series C", "hq": "SF, CA",
       "lead_investors": "Accel"}"""
    if not _require_internal_secret():
        return jsonify({"error": "forbidden"}), 403
    missing = [v for v in ("PERPLEXITY_API_KEY", "ANTHROPIC_API_KEY") if not os.environ.get(v)]
    if missing:
        return jsonify({"error": f"missing env vars: {', '.join(missing)}"}), 400
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "'name' is required"}), 400
    deal = di_schemas.DealInput(
        record_id=f"stage2-{slug}-{uuid.uuid4().hex[:8]}", name=name,
        domain=body.get("domain") or None, round=body.get("round") or None,
        lead_investors=body.get("lead_investors") or None, hq=body.get("hq") or None,
    )
    job_id = uuid.uuid4().hex
    _start_chat_job(job_id, {
        "status": "running", "stage": 2, "type": "stage2", "companySlug": slug,
        "label": f"{name} — Stage 2", "createdAt": datetime.utcnow().isoformat() + "Z",
    })
    threading.Thread(target=_run_company_stage2, args=(job_id, slug, deal), daemon=True).start()
    return jsonify({"job_id": job_id, "status": "started", "poll": f"/jobs/{job_id}"})


def _run_attio_import(job_id: str):
    try:
        pairs = di_attio_io.list_all_deals()
        total = len(pairs)
        created = skipped = errors = 0
        # Built ONCE for the whole loop -- push_company_from_attio would
        # otherwise re-read the entire topVCs/partnerVCs collections on
        # every single deal that resolves to Radar (RADAR_PLAN.md's own S3
        # mandate-screen check / radar_access.py's syndicate gate), the same
        # per-row-refetch mistake the hub-perf fix already corrected for
        # listCompanies()'s investor cross-reference.
        tier1_index = di_radar_mandate.build_tier1_index(di_radar_state.list_top_vcs())
        partner_index = di_radar_access.build_partner_index(di_radar_state.list_partner_vcs())
        for i, (deal, attio_stage) in enumerate(pairs):
            try:
                result = di_firestore_push.push_company_from_attio(deal, attio_stage, tier1_index, partner_index)
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
