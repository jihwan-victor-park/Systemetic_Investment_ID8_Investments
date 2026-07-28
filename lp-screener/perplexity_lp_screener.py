#!/usr/bin/env python3
"""
LP Prospect Screener using Perplexity API
Batch researches firms and outputs scored CSV for import.

Reads either an Apollo contacts export or a plain "Company/Contact Name/Title/City/State"
CSV (columns are auto-detected). Writes results incrementally to a JSONL checkpoint as
each batch completes, so a crash or interrupted run never loses completed work -- rerun
the same command and it picks up where it left off. Failed/missing firms get a single
individual retry pass at the end.
"""

import argparse
import csv
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# Column aliases so the same script works on an Apollo export or our own attendee-list CSV.
COLUMN_ALIASES = {
    'company': ['Company Name', 'Company'],
    'website': ['Website'],
    'city': ['Company City', 'City'],
    'state': ['Company State', 'State'],
    'country': ['Country'],
    'contact_name': ['Contact Name', 'Name'],  # used if First/Last aren't present
    'first_name': ['First Name'],
    'last_name': ['Last Name'],
    'contact_title': ['Title', 'Contact Title'],
    'contact_email': ['Email', 'Contact Email'],
    'phone': ['Phone', 'Contact Phone'],
}


def pick(row: dict, key: str) -> str:
    for name in COLUMN_ALIASES[key]:
        if name in row and row[name]:
            return row[name].strip()
    return ''


def norm_name(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def find_orig(batch: list, returned_firm: str):
    """Match a returned 'firm' string back to its source record, tolerating models that
    echo extra text (e.g. the whole 'name | website | location' input line) instead of
    just the name."""
    key = norm_name(returned_firm)
    if not key:
        return None
    for f in batch:
        ok = norm_name(f['firm'])
        if ok and (ok == key or ok in key or key in ok):
            return f
    return None


def extract_firms(csv_path: str) -> list:
    """Extract one record per distinct company from the input CSV (order preserved)."""
    rows = list(csv.DictReader(open(csv_path, encoding='utf-8')))
    seen = set()
    firms = []
    for r in rows:
        co = pick(r, 'company')
        if not co or co.lower() in seen:
            continue
        seen.add(co.lower())

        contact_name = pick(r, 'contact_name')
        if not contact_name:
            contact_name = f"{pick(r, 'first_name')} {pick(r, 'last_name')}".strip()

        loc = ', '.join(x for x in [pick(r, 'city'), pick(r, 'state')] if x)
        firms.append({
            'firm': co,
            'website': pick(r, 'website'),
            'location': loc,
            'country': pick(r, 'country'),
            'contact_name': contact_name,
            'contact_title': pick(r, 'contact_title'),
            'contact_email': pick(r, 'contact_email'),
            'phone': pick(r, 'phone'),
        })
    return firms


PROMPT_HEADER = """You are an LP-prospecting analyst evaluating prospective Limited Partners for ID8 Growth Opportunities Fund I ($50M Series B–D growth-stage tech/AI fund, $500k min LP commitment).

Research each firm below on the web. Be skeptical: absence of venture/alts evidence = cap score low. Never fabricate AUM or activity.

FIRMS TO RESEARCH (format is "index. Company Name | website | location" -- the "firm" field in your output must be ONLY the Company Name, never the website or location):
{firms_text}

For each firm, research:
1. Is it a family office, RIA, or something else?
2. Do they invest in venture/private markets/alternatives? (fund commitments, direct deals, SEC Form ADV)
3. Can they write $500k+ checks?
4. Tech/AI sector interest?

SCORING RUBRIC (0–100):
- Alts/venture appetite: max 35 points (concrete evidence of VC/PE investing)
- Check-size $500k+ fit: max 20 points
- Sector alignment (tech/AI/growth): max 20 points
- Type fit (genuine FO or alts RIA): max 15 points
- Emerging-manager openness: max 10 points

DISQUALIFIERS (subtract points): pure public-market wealth managers with no alts; retail-only RIAs with small minimums; not actually an FO or RIA (operating companies, healthcare, etc.)

TIERS: A (50-70+) contact now | B (40-49) maybe | C (<40) skip

Keep each field terse -- rationale and alts_venture_evidence under 30 words each, this matters for output budget. Return ONLY this JSON array, no markdown, no prose:
[
  {{
    "firm": "<exact name from input>",
    "website": "URL or ''",
    "location": "City, State",
    "type": "family_office|RIA|other",
    "score": <integer 0-100>,
    "tier": "A|B|C",
    "alts_venture_evidence": "<short sentence + source URL, or 'none found'>",
    "estimated_check_capacity": "<e.g. '$500k-2M plausible' or 'unknown'>",
    "rationale": "<short, concrete, cite what you found>",
    "confidence": "high|medium|low",
    "contact_hint": "<most senior contact name/title if found>"
  }}
]"""


def format_batch_prompt(firms: list) -> str:
    firms_text = "\n".join(
        f"{i+1}. {f['firm']} | {f['website']} | {f['location']}"
        for i, f in enumerate(firms)
    )
    return PROMPT_HEADER.format(firms_text=firms_text)


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=2,  # 2s, 4s, 8s, 16s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=['POST'],
        raise_on_status=False,
    )
    session.mount('https://', HTTPAdapter(max_retries=retry))
    return session


def call_perplexity(session: requests.Session, api_key: str, prompt: str,
                     model: str, max_tokens: int) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    resp = session.post(PERPLEXITY_API_URL, json=payload, headers=headers, timeout=90)
    resp.raise_for_status()
    result = resp.json()
    finish_reason = result["choices"][0].get("finish_reason")
    if finish_reason == "length":
        print("   ⚠️  response hit max_tokens -- output likely truncated, consider a smaller batch size")
    return result["choices"][0]["message"]["content"]


def parse_json_response(text: str) -> list:
    """Extract a JSON array from the response, tolerating markdown fences and stray prose."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(json)?', '', text)
        text = re.sub(r'```$', '', text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # fall back: grab the outermost [...] substring
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


class Checkpoint:
    """Append-only JSONL of completed firm results, keyed by normalized firm name."""

    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.done = {}
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self.done[norm_name(rec.get('firm', ''))] = rec

    def has(self, firm_name: str) -> bool:
        return norm_name(firm_name) in self.done

    def append(self, records: list):
        with self.lock:
            with open(self.path, 'a', encoding='utf-8') as f:
                for rec in records:
                    f.write(json.dumps(rec) + "\n")
                    self.done[norm_name(rec.get('firm', ''))] = rec

    def all_records(self) -> list:
        return list(self.done.values())


def process_one_batch(session, api_key, model, max_tokens, batch, checkpoint, batch_label):
    prompt = format_batch_prompt(batch)
    try:
        response = call_perplexity(session, api_key, prompt, model, max_tokens)
        results = parse_json_response(response)
    except json.JSONDecodeError as e:
        print(f"   ✗ {batch_label}: JSON parse error ({e}) -- {len(batch)} firms unresolved, will retry individually")
        return set()
    except Exception as e:
        print(f"   ✗ {batch_label}: {e} -- {len(batch)} firms unresolved, will retry individually")
        return set()

    matched_keys = set()
    for result in results:
        orig = find_orig(batch, result.get('firm', ''))
        if orig:
            matched_keys.add(norm_name(orig['firm']))
            result['firm'] = orig['firm']  # normalize to our canonical name, discard any echoed suffix
            if not result.get('contact_hint'):
                bits = [orig['contact_name'], orig['contact_title'], orig['contact_email']]
                result['contact_hint'] = ' / '.join(x for x in bits if x)
        else:
            # keep only the part before a stray '|' so unmatched rows don't pollute the CSV
            result['firm'] = result.get('firm', '').split('|')[0].strip()
    checkpoint.append(results)
    missing = len(batch) - len(matched_keys)
    print(f"   ✓ {batch_label}: {len(results)} returned ({missing} unmatched)")
    return matched_keys


def run(firms: list, checkpoint: Checkpoint, api_key: str, model: str,
        max_tokens: int, batch_size: int, concurrency: int):
    pending = [f for f in firms if not checkpoint.has(f['firm'])]
    if not pending:
        print("✓ Nothing pending -- all firms already in checkpoint")
        return

    batches = [pending[i:i + batch_size] for i in range(0, len(pending), batch_size)]
    print(f"\n🔍 {len(pending)} firms pending in {len(batches)} batches "
          f"(batch_size={batch_size}, concurrency={concurrency}, model={model})")

    session = make_session()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(process_one_batch, session, api_key, model, max_tokens,
                        batch, checkpoint, f"batch {i+1}/{len(batches)}"): batch
            for i, batch in enumerate(batches)
        }
        for fut in as_completed(futures):
            fut.result()  # exceptions already caught inside process_one_batch

    # Mop-up pass: anything still missing gets one individual retry.
    still_missing = [f for f in pending if not checkpoint.has(f['firm'])]
    if still_missing:
        print(f"\n🔁 Retrying {len(still_missing)} unresolved firms individually...")
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [
                pool.submit(process_one_batch, session, api_key, model, max_tokens,
                            [f], checkpoint, f"retry: {f['firm'][:30]}")
                for f in still_missing
            ]
            for fut in as_completed(futures):
                fut.result()

    final_missing = [f['firm'] for f in still_missing if not checkpoint.has(f['firm'])]
    if final_missing:
        print(f"\n⚠️  {len(final_missing)} firms still unresolved after retry:")
        for name in final_missing:
            print(f"   - {name}")


def write_csv(records: list, output_path: str):
    records = sorted(records, key=lambda x: x.get('score', 0), reverse=True)
    fieldnames = [
        'firm', 'website', 'location', 'type', 'score', 'tier',
        'alts_venture_evidence', 'estimated_check_capacity',
        'rationale', 'confidence', 'contact_hint',
    ]
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow({k: row.get(k, '') for k in fieldnames})


def main():
    parser = argparse.ArgumentParser(description="Screen LP prospect firms via Perplexity API")
    parser.add_argument('input_csv')
    parser.add_argument('output_csv')
    parser.add_argument('--batch-size', type=int, default=12,
                         help="firms per API call (default 12 -- keeps output well under max-tokens)")
    parser.add_argument('--concurrency', type=int, default=4, help="parallel API calls (default 4)")
    parser.add_argument('--model', default='sonar', help="sonar | sonar-pro | sonar-reasoning")
    parser.add_argument('--max-tokens', type=int, default=6000)
    parser.add_argument('--test', type=int, default=0,
                         help="only process the first N firms, to validate the key/prompt/parsing before a full run")
    parser.add_argument('--checkpoint', default=None,
                         help="path to the JSONL checkpoint (default: <output_csv>.checkpoint.jsonl)")
    parser.add_argument('--fresh', action='store_true', help="ignore any existing checkpoint and start over")
    args = parser.parse_args()

    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("❌ PERPLEXITY_API_KEY environment variable not set")
        sys.exit(1)

    if not Path(args.input_csv).exists():
        print(f"❌ Input CSV not found: {args.input_csv}")
        sys.exit(1)

    checkpoint_path = args.checkpoint or f"{args.output_csv}.checkpoint.jsonl"
    if args.fresh and os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)

    firms = extract_firms(args.input_csv)
    print(f"📁 Input: {args.input_csv} ({len(firms)} distinct firms)")
    print(f"📁 Output: {args.output_csv}")
    print(f"💾 Checkpoint: {checkpoint_path}")

    if args.test:
        firms = firms[:args.test]
        print(f"🧪 TEST MODE: only processing first {len(firms)} firms")

    checkpoint = Checkpoint(checkpoint_path)
    if checkpoint.done:
        print(f"⚙️  Resuming: {len(checkpoint.done)} firms already in checkpoint")

    run(firms, checkpoint, api_key, args.model, args.max_tokens, args.batch_size, args.concurrency)

    records = checkpoint.all_records()
    # only write rows for firms actually in this run's input set
    wanted = {norm_name(f['firm']) for f in firms}
    records = [r for r in records if norm_name(r.get('firm', '')) in wanted]

    if records:
        write_csv(records, args.output_csv)
        tiers = {}
        for r in records:
            t = (r.get('tier') or '?')[0]
            tiers[t] = tiers.get(t, 0) + 1
        print(f"\n✅ Wrote {len(records)} firms to {args.output_csv}")
        print(f"📈 A-tier: {tiers.get('A', 0)}  B-tier: {tiers.get('B', 0)}  C-tier: {tiers.get('C', 0)}")
    else:
        print("❌ No results collected")


if __name__ == "__main__":
    main()
