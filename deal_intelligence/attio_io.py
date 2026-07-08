"""Read qualified deals from Attio and write results back.

Write-back uses Attio's write value formats (see project memory): number is
[{"value": n}], select is a plain string, text is [{"value": "..."}]. Writes are
skipped for any field whose slug is not configured, so this is safe to run before
the Attio fields exist.
"""
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
        for k in ("value", "option", "status", "target_record_id", "full_name"):
            if isinstance(cell, dict) and k in cell:
                inner = cell[k]
                return inner.get("title") if isinstance(inner, dict) else inner
        return cell if not isinstance(cell, dict) else None
    return v


def get_qualified_deals(limit: int = 500) -> list:
    """Query the Deals object for records at the Qualified stage."""
    if not config.ATTIO_API_KEY:
        raise RuntimeError("ATTIO_API_KEY not set")
    url = f"{config.ATTIO_BASE}/objects/{config.DEALS_OBJECT}/records/query"
    body = {"filter": {config.STAGE_SLUG: config.QUALIFIED_VALUE}, "limit": limit}
    r = session.post(url, json=body, headers=_headers(), timeout=60)
    r.raise_for_status()
    deals = []
    for rec in r.json().get("data", []):
        values = rec.get("values", {})
        rid = rec.get("id", {}).get("record_id")
        s = config.READ_SLUGS
        deals.append(DealInput(
            record_id=rid,
            name=_value(values, s["name"]) or "(unnamed deal)",
            domain=_value(values, s["domain"]),
            round=_value(values, s["round"]),
            hq=_value(values, s["hq"]),
            lead_investors=_value(values, s["lead_investors"]),
            raw=values,
        ))
    return deals


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
