#!/usr/bin/env python3
"""
ID8 NYC VC Warm Lead Tracker - Deep Research v2
Reads an Apollo CSV, researches targets deeply, and outputs category scores + total score.
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

import requests

API_URL = "https://api.perplexity.ai/chat/completions"
MODEL = "sonar-pro"
BATCH_SIZE = 10
MAX_TOKENS = 5000
TEMPERATURE = 0.2
MAX_RETRIES = 2


def extract_firms_from_csv(csv_path: str, batch_size: int = 10) -> list:
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
    seen = {}
    order = []
    for r in rows:
        firm = (r.get("Company Name") or r.get("Company") or r.get("Organization") or "").strip()
        if not firm or firm in seen:
            continue
        seen[firm] = {
            "firm": firm,
            "website": (r.get("Website") or r.get("Website URL") or "").strip(),
            "location": ", ".join([x for x in [(r.get("Company City") or r.get("City") or "").strip(), (r.get("Company State") or r.get("State") or "").strip()] if x]),
            "contact_name": " ".join([x for x in [(r.get("First Name") or "").strip(), (r.get("Last Name") or "").strip()] if x]).strip(),
            "contact_title": (r.get("Title") or r.get("Job Title") or "").strip(),
            "contact_email": (r.get("Email") or r.get("Email Address") or "").strip(),
        }
        order.append(firm)
    return [[seen[f] for f in order[i:i + batch_size]] for i in range(0, len(order), batch_size)]


def format_batch_prompt(firms: list) -> str:
    firms_text = "\n".join([
        f"{i+1}. {f['firm']} | {f['website']} | {f['location']} | {f['contact_name']} | {f['contact_title']} | {f['contact_email']}"
        for i, f in enumerate(firms)
    ])

    return f"""You are a senior VC research analyst for ID8 Investments.
Research each target deeply using web evidence and do not over-penalize firms that are early-stage VCs but have limited public footprints.
Prioritize uncovering pre-seed, seed, Series A, follow-on/pro rata relevance, NYC ecosystem ties, and tech/AI focus.

Return ONLY valid JSON array. No markdown. No prose.

TARGETS:
{firms_text}

For each target:
1. Identify the exact firm type.
2. Search for fund strategy, stage focus, geography, sectors, and public investing activity.
3. Look specifically for early-stage signals: pre-seed, seed, Series A, startup investing, pro rata, follow-on, portfolio, accelerator, angel, emerging manager, or founder-network signals.
4. Look for NYC relevance or Northeast ecosystem ties.
5. Assign category scores and a total score.

SCORING (each 0-20 unless noted):
- nyc_relevance
- vc_activity
- early_stage_fit
- pro_rata_fit
- tech_ai_alignment
- emerging_manager_openness
- relationship_warmth
- check_capacity_fit

TOTAL SCORE (0-100): weighted total from category scores
Suggested weights:
- nyc_relevance: 10
- vc_activity: 15
- early_stage_fit: 20
- pro_rata_fit: 15
- tech_ai_alignment: 10
- emerging_manager_openness: 10
- relationship_warmth: 10
- check_capacity_fit: 10

TIERS:
- A: 75-100
- B: 55-74
- C: 0-54

OUTPUT SCHEMA:
[
  {{
    "firm": "Name",
    "website": "URL",
    "location": "City, State",
    "contact_name": "Name",
    "contact_title": "Title",
    "contact_email": "Email",
    "type": "vc|family_office|ria|angel|operating_company|other",
    "nyc_relevance": 0,
    "vc_activity": 0,
    "early_stage_fit": 0,
    "pro_rata_fit": 0,
    "tech_ai_alignment": 0,
    "emerging_manager_openness": 0,
    "relationship_warmth": 0,
    "check_capacity_fit": 0,
    "total_score": 0,
    "tier": "A|B|C",
    "confidence": "high|medium|low",
    "category_summary": "Short sentence summarizing why the score is what it is.",
    "evidence_urls": ["https://...", "https://..."],
    "next_action": "Short outreach suggestion."
  }}
]

Rules:
- Be conservative but not blind to hidden early-stage VC fit.
- If evidence is mixed, use medium confidence.
- Include evidence URLs for major claims.
- If a firm appears to be a real early-stage VC, do not score it low just because the public site is sparse.
- If there is no evidence, say so and score appropriately."""


def call_perplexity(prompt: str, api_key: str, model: str = MODEL) -> str:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
    }
    r = requests.post(API_URL, json=payload, headers=headers, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def parse_json_response(text: str):
    t = text.strip()
    if t.startswith("```json"):
        t = t[7:]
    if t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    return json.loads(t.strip())


def weighted_total(row: dict) -> int:
    weights = {
        "nyc_relevance": 10,
        "vc_activity": 15,
        "early_stage_fit": 20,
        "pro_rata_fit": 15,
        "tech_ai_alignment": 10,
        "emerging_manager_openness": 10,
        "relationship_warmth": 10,
        "check_capacity_fit": 10,
    }
    total = 0
    for k, w in weights.items():
        total += float(row.get(k, 0) or 0) / 20.0 * w
    return int(round(total))


def tier_from_total(total: int) -> str:
    if total >= 75:
        return "A"
    if total >= 55:
        return "B"
    return "C"


def normalize_result(row: dict, orig: dict) -> dict:
    for k in ["website", "location", "contact_name", "contact_title", "contact_email"]:
        if not row.get(k):
            row[k] = orig.get(k, "")
    row["total_score"] = weighted_total(row)
    row["tier"] = tier_from_total(row["total_score"])
    if not row.get("confidence"):
        row["confidence"] = "medium"
    if not row.get("evidence_urls"):
        row["evidence_urls"] = []
    return row


def write_csv(results: list, output_path: str):
    if not results:
        return
    results.sort(key=lambda x: x.get("total_score", 0), reverse=True)
    fieldnames = [
        "firm", "website", "location", "contact_name", "contact_title", "contact_email", "type",
        "nyc_relevance", "vc_activity", "early_stage_fit", "pro_rata_fit", "tech_ai_alignment",
        "emerging_manager_openness", "relationship_warmth", "check_capacity_fit", "total_score",
        "tier", "confidence", "category_summary", "evidence_urls", "next_action"
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in results:
            out = dict(row)
            if isinstance(out.get("evidence_urls"), list):
                out["evidence_urls"] = " | ".join(out["evidence_urls"])
            w.writerow({k: out.get(k, "") for k in fieldnames})


def main():
    input_csv = "/Users/oscar/Downloads/apollo_list_vcs.csv"
    output_csv = "/Users/oscar/Downloads/id8_nyc_vc_warm_leads_scored.csv"
    output_json = "/Users/oscar/Downloads/id8_nyc_vc_warm_leads_scored.json"

    if len(sys.argv) > 1:
        input_csv = sys.argv[3]
    if len(sys.argv) > 2:
        output_csv = sys.argv[4]

    if not Path(input_csv).exists():
        print(f"Input CSV not found: {input_csv}")
        sys.exit(1)

    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        print("Set PERPLEXITY_API_KEY in your environment.")
        sys.exit(1)

    batches = extract_firms_from_csv(input_csv, batch_size=BATCH_SIZE)
    all_results = []
    errors = []

    print(f"Input: {input_csv}")
    print(f"Batches: {len(batches)}")
    print(f"Model: {MODEL}")

    for i, batch in enumerate(batches, 1):
        prompt = format_batch_prompt(batch)
        success = False
        last_err = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"Batch {i}/{len(batches)} attempt {attempt} ...")
                response = call_perplexity(prompt, api_key=api_key)
                results = parse_json_response(response)
                if not isinstance(results, list):
                    raise ValueError("Model did not return a JSON array")

                for result in results:
                    orig = next((f for f in batch if f["firm"] == result.get("firm")), {})
                    all_results.append(normalize_result(result, orig))
                success = True
                print(f"  ✓ {len(results)} results")
                break
            except Exception as e:
                last_err = str(e)
                time.sleep(2 * attempt)

        if not success:
            errors.append({"batch": i, "error": last_err})
            print(f"  ✗ {last_err}")

    if all_results:
        write_csv(all_results, output_csv)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(sorted(all_results, key=lambda x: x.get("total_score", 0), reverse=True), f, indent=2, ensure_ascii=False)
        print(f"Wrote CSV: {output_csv}")
        print(f"Wrote JSON: {output_json}")
        print(f"Total results: {len(all_results)}")
        if errors:
            print(f"Errors in {len(errors)} batches")
    else:
        print("No results collected.")


if __name__ == "__main__":
    main()