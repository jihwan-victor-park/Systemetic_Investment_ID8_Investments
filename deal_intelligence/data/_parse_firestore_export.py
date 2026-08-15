"""One-off: decode the raw Firestore REST runQuery export (typed-value JSON)
into plain dicts, keyed by document slug, and report which qualified
companies already have a Stage 1 screen on file (latestScreen set)."""
import json
import os

_HERE = os.path.dirname(__file__)


def _decode_value(v):
    if not isinstance(v, dict):
        return v
    if "stringValue" in v:
        return v["stringValue"]
    if "booleanValue" in v:
        return v["booleanValue"]
    if "integerValue" in v:
        return int(v["integerValue"])
    if "doubleValue" in v:
        return v["doubleValue"]
    if "nullValue" in v:
        return None
    if "timestampValue" in v:
        return v["timestampValue"]
    if "arrayValue" in v:
        return [_decode_value(x) for x in v["arrayValue"].get("values", [])]
    if "mapValue" in v:
        return _decode_fields(v["mapValue"].get("fields", {}))
    return v


def _decode_fields(fields):
    return {k: _decode_value(v) for k, v in fields.items()}


def load():
    with open(os.path.join(_HERE, "qualified-screens-snapshot.json")) as f:
        raw = json.load(f)
    out = {}
    for entry in raw:
        doc = entry.get("document")
        if not doc:
            continue
        slug = doc["name"].rsplit("/", 1)[-1]
        out[slug] = _decode_fields(doc.get("fields", {}))
    return out


if __name__ == "__main__":
    companies = load()
    screened = {slug: c for slug, c in companies.items() if c.get("latestScreen")}
    unscreened = {slug: c for slug, c in companies.items() if not c.get("latestScreen")}
    print(f"total qualified: {len(companies)}")
    print(f"already screened: {len(screened)}")
    print(f"needs screening: {len(unscreened)}")
    print()
    print("=== already screened ===")
    for slug, c in sorted(screened.items(), key=lambda kv: kv[1].get("name", "")):
        ls = c.get("latestScreen") or {}
        print(f"  {c.get('name'):40s} fitScore={ls.get('fitScore')!s:6s} gate={ls.get('gate')} date={ls.get('date')}")
    print()
    print("=== needs screening ===")
    for slug, c in sorted(unscreened.items(), key=lambda kv: kv[1].get("name", "")):
        print(f"  {slug:30s} {c.get('name')}")
