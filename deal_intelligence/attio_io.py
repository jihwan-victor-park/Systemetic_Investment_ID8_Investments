"""Read qualified deals from Attio and write results back.

Write-back uses Attio's write value formats (see project memory): number is
[{"value": n}], select is a plain string, text is [{"value": "..."}]. Writes are
skipped for any field whose slug is not configured, so this is safe to run before
the Attio fields exist.
"""
from concurrent.futures import ThreadPoolExecutor

from . import config
from .net import session
from .schemas import DealInput, DealFit, DealMemo


def _headers():
    return {"Authorization": f"Bearer {config.ATTIO_API_KEY}", "Content-Type": "application/json"}


def _value(values, slug):
    """Best-effort scalar read from an Attio values dict."""
    v = values.get(slug)
    if not v:
        return None
    if isinstance(v, list) and v:
        cell = v[0]
        # currency_value added 2026-07-28 for deal_size (Radar's capital-clock
        # roundSize input) -- pipeline/app.py's build_attio_values already
        # stores the real dollar amount there (source $millions * MILLION),
        # not millions, so no unit conversion is needed on the way back out.
        for k in ("value", "option", "status", "target_record_id", "full_name", "currency_value"):
            if isinstance(cell, dict) and k in cell:
                inner = cell[k]
                return inner.get("title") if isinstance(inner, dict) else inner
        return cell if not isinstance(cell, dict) else None
    return v


def _company_domain(record_id: str):
    """Deals don't carry domain directly -- pipeline/app.py's build_attio_values
    links each Deal to a Company record via `associated_company`, and domain
    lives on that Company's `domains` field. Best-effort: a lookup failure
    just means no domain, not a hard error, since domain is enrichment
    (helps the model disambiguate a company name) rather than something
    Stage 1 can't function without."""
    if not record_id:
        return None
    url = f"{config.ATTIO_BASE}/objects/companies/records/{record_id}"
    r = session.get(url, headers=_headers(), timeout=30)
    if not r.ok:
        return None
    domains = r.json().get("data", {}).get("values", {}).get("domains") or []
    return domains[0].get("domain") if domains and isinstance(domains[0], dict) else None


def _parse_top10(raw_value):
    """The Top 10 VC slug is a select attribute -- _value() returns its
    option title as a plain string ('Yes'/'No'), not a bool. None means the
    option was never set (unknown), distinct from a confirmed 'No' -- see
    DealInput.top10's own docstring on why that distinction matters."""
    if raw_value is None:
        return None
    return str(raw_value).strip().lower() == "yes"


def _parse_deal_record(rec: dict) -> DealInput:
    """Turn one raw Attio Deal record into a DealInput, resolving domain via
    the linked Company record when the deal itself has none (see
    _company_domain's docstring). Shared by get_qualified_deals() and
    list_all_deals() so the two don't drift."""
    values = rec.get("values", {})
    rid = rec.get("id", {}).get("record_id")
    s = config.READ_SLUGS
    domain = _value(values, s["domain"])
    if not domain:
        company_ref = values.get("associated_company")
        company_rid = None
        if isinstance(company_ref, list) and company_ref:
            cell = company_ref[0]
            company_rid = cell.get("target_record_id") if isinstance(cell, dict) else None
        domain = _company_domain(company_rid)
    return DealInput(
        record_id=rid,
        name=_value(values, s["name"]) or "(unnamed deal)",
        domain=domain,
        round=_value(values, s["round"]),
        hq=_value(values, s["hq"]),
        lead_investors=_value(values, s["lead_investors"]),
        round_date=_value(values, s["round_date"]),
        description=_value(values, s["description"]),
        deal_size=_value(values, s["deal_size"]),
        top10=_parse_top10(_value(values, s["top10"])),
        raw=values,
    )


def get_qualified_deals(limit: int = 500) -> list:
    """Query the Deals object for records at the Qualified stage."""
    if not config.ATTIO_API_KEY:
        raise RuntimeError("ATTIO_API_KEY not set")
    url = f"{config.ATTIO_BASE}/objects/{config.DEALS_OBJECT}/records/query"
    body = {"filter": {config.STAGE_SLUG: config.QUALIFIED_VALUE}, "limit": limit}
    r = session.post(url, json=body, headers=_headers(), timeout=60)
    r.raise_for_status()
    return [_parse_deal_record(rec) for rec in r.json().get("data", [])]


def list_all_deals(limit: int = 500, max_workers: int = None) -> list:
    """Query every Deal record regardless of stage, paginated (no filter),
    same offset-pagination shape as pipeline/app.py's backfill_investors().
    Returns (DealInput, attio_stage) pairs -- the raw Attio stage string is
    kept separate from DealInput since it's import/origin metadata, not
    research context score_deal() needs.

    Domain resolution is one extra Attio GET per deal that lacks a `domain`
    Deal attribute (i.e. most of them -- see _company_domain's docstring),
    so this runs those lookups through a bounded thread pool rather than
    sequentially -- otherwise a few hundred deals means a few hundred
    sequential round trips."""
    if not config.ATTIO_API_KEY:
        raise RuntimeError("ATTIO_API_KEY not set")
    if max_workers is None:
        max_workers = config.ATTIO_IMPORT_PARALLEL
    url = f"{config.ATTIO_BASE}/objects/{config.DEALS_OBJECT}/records/query"
    records = []
    offset = 0
    while True:
        body = {"limit": limit, "offset": offset}
        r = session.post(url, json=body, headers=_headers(), timeout=60)
        r.raise_for_status()
        batch = r.json().get("data", [])
        records.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    def _parse_with_stage(rec):
        deal = _parse_deal_record(rec)
        attio_stage = _value(rec.get("values", {}), config.STAGE_SLUG)
        return deal, attio_stage

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(_parse_with_stage, records))


def _patch(record_id: str, attio_values: dict):
    if not attio_values:
        return
    url = f"{config.ATTIO_BASE}/objects/{config.DEALS_OBJECT}/records/{record_id}"
    session.patch(url, json={"data": {"values": attio_values}}, headers=_headers(), timeout=60).raise_for_status()


def write_fit(fit: DealFit, hub_url: str = None):
    """Write the stage-1 score, gate, rationale, and hub research link onto the deal."""
    w = config.WRITE_SLUGS
    values = {}
    if w["fit_score"]:
        values[w["fit_score"]] = [{"value": fit.fit_score}]
    if w["fit_gate"]:
        values[w["fit_gate"]] = "Yes" if fit.gate else "No"   # single-select: plain string
    if w["fit_rationale"]:
        values[w["fit_rationale"]] = [{"value": fit.rationale[:2000]}]
    if w["hub_url"] and hub_url:
        values[w["hub_url"]] = [{"value": hub_url}]
    _patch(fit.record_id, values)


def write_memo(memo: DealMemo, memo_url: str = None):
    """Write the final score and a link to the memo back onto the deal."""
    w = config.WRITE_SLUGS
    values = {}
    if w["final_score"] and memo.final_score is not None:
        values[w["final_score"]] = [{"value": memo.final_score}]
    if w["memo_url"] and (memo_url or memo.markdown_path):
        values[w["memo_url"]] = [{"value": memo_url or memo.markdown_path}]
    _patch(memo.record_id, values)
