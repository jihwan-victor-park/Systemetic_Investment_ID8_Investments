#!/usr/bin/env python3
"""
LP Prospect Screener using Perplexity API
Batch researches firms and outputs scored CSV for import
"""

import csv
import json
import os
import sys
import requests
from pathlib import Path

# Configuration
PERPLEXITY_API_KEY = "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"
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
MODEL = "sonar"  # or "sonar-pro" for better results, "sonar-reasoning" for complex reasoning

def extract_firms_from_csv(csv_path: str, batch_size: int = 20) -> list:
    """Extract distinct firms from Apollo CSV, grouped into batches."""
    rows = list(csv.DictReader(open(csv_path, encoding='utf-8')))
    seen = {}
    order = []

    for r in rows:
        co = (r.get('Company Name') or '').strip()
        if not co or co in seen:
            continue

        seen[co] = {
            'firm': co,
            'website': r.get('Website', ''),
            'location': f"{r.get('Company City') or ''},{r.get('Company State') or ''}".rstrip(','),
            'contact_name': f"{r.get('First Name', '')} {r.get('Last Name', '')}".strip(),
            'contact_title': r.get('Title', ''),
            'contact_email': r.get('Email', ''),
        }
        order.append(co)

    # Group into batches
    batches = []
    for i in range(0, len(order), batch_size):
        batch = [seen[co] for co in order[i:i+batch_size]]
        batches.append(batch)

    return batches

def format_batch_prompt(firms: list) -> str:
    """Format a batch of firms into the Perplexity prompt."""
    firms_text = "\n".join([
        f"{i+1}. {f['firm']} | {f['website']} | {f['location']}"
        for i, f in enumerate(firms)
    ])

    prompt = f"""You are an LP-prospecting analyst evaluating prospective Limited Partners for ID8 Growth Opportunities Fund I ($50M Series B–D growth-stage tech/AI fund, $500k min LP commitment).

Research these firms on the web. Be skeptical: absence of venture/alts evidence = cap score low. Never fabricate AUM or activity. Return ONLY valid JSON array (no markdown, no prose).

FIRMS TO RESEARCH:
{firms_text}

For each firm, research:
1. Is it a family office, RIA, or something else?
2. Do they invest in venture/private markets/alternatives? (search for fund commitments, direct deals, SEC Form ADV)
3. Can they write $500k+ checks?
4. Tech/AI sector interest?

SCORING RUBRIC (0–100):
- Alts/venture appetite: max 35 points (concrete evidence of VC/PE investing)
- Check-size $500k+ fit: max 20 points
- Sector alignment (tech/AI/growth): max 20 points
- Type fit (genuine FO or alts RIA): max 15 points
- Emerging-manager openness: max 10 points

DISQUALIFIERS (subtract points):
- Pure public-market wealth managers with no alts
- Retail-only RIAs with small minimums
- Not actually an FO or RIA (operating companies, healthcare, etc.)

TIERS:
- A (50-70+): contact now
- B (40-49): maybe
- C (<40): skip

OUTPUT FORMAT: Return ONLY this JSON array (no other text):
[
  {{
    "firm": "Name",
    "website": "URL",
    "location": "City, State",
    "type": "family_office|RIA|other",
    "score": <integer 0-100>,
    "tier": "A|B|C",
    "alts_venture_evidence": "1 sentence + source URL or 'none found'",
    "estimated_check_capacity": "$500k-2M plausible or 'unknown'",
    "rationale": "2-3 sentences citing what you found",
    "confidence": "high|medium|low",
    "contact_hint": "Most senior contact name/title/email from research"
  }},
  ...
]

Be concrete. Cite what you actually found. Return valid JSON only."""

    return prompt

def call_perplexity(prompt: str, model: str = "sonar") -> str:
    """Call Perplexity API and return response."""
    if not PERPLEXITY_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY environment variable not set")

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4000,
        "temperature": 0.2,  # Low temp for consistency
    }

    print(f"  Calling Perplexity ({model})...", end=" ", flush=True)
    response = requests.post(PERPLEXITY_API_URL, json=payload, headers=headers, timeout=60)
    response.raise_for_status()

    result = response.json()
    print(f"✓ (tokens: {result.get('usage', {}).get('total_tokens', '?')})")

    return result["choices"][0]["message"]["content"]

def parse_json_response(text: str) -> list:
    """Extract JSON array from response, handling markdown code blocks."""
    text = text.strip()

    # Remove markdown code blocks if present
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()
    return json.loads(text)

def process_batches(batches: list, output_csv: str = "lp_prospects_scored.csv"):
    """Process all batches and write to CSV."""
    all_results = []

    for i, batch in enumerate(batches, 1):
        print(f"\n📊 Batch {i}/{len(batches)} ({len(batch)} firms)")
        print(f"   Firms: {', '.join([f['firm'][:30] for f in batch])}")

        prompt = format_batch_prompt(batch)

        try:
            response = call_perplexity(prompt)
            results = parse_json_response(response)

            # Validate and attach original contact info
            for result in results:
                # Find original firm data to get best contact
                orig = next((f for f in batch if f['firm'] == result.get('firm')), {})
                if orig and not result.get('contact_hint'):
                    if orig['contact_name'] and orig['contact_email']:
                        result['contact_hint'] = f"{orig['contact_name']} ({orig['contact_title']}) {orig['contact_email']}"
                all_results.append(result)

            print(f"   ✓ Received {len(results)} results")

        except json.JSONDecodeError as e:
            print(f"   ✗ JSON parse error: {e}")
            print(f"   Response: {response[:200]}")
        except Exception as e:
            print(f"   ✗ Error: {e}")

    # Write to CSV
    if all_results:
        write_csv(all_results, output_csv)
        print(f"\n✅ Wrote {len(all_results)} firms to {output_csv}")

        # Summary stats
        tiers = {}
        for r in all_results:
            tier = r.get('tier', 'unknown')[0]  # Extract A/B/C
            tiers[tier] = tiers.get(tier, 0) + 1

        print(f"\n📈 Summary:")
        print(f"   A-tier (contact now): {tiers.get('A', 0)}")
        print(f"   B-tier (maybe): {tiers.get('B', 0)}")
        print(f"   C-tier (skip): {tiers.get('C', 0)}")
    else:
        print("❌ No results collected")

def write_csv(results: list, output_path: str):
    """Write results to CSV."""
    if not results:
        return

    # Sort by score descending
    results.sort(key=lambda x: x.get('score', 0), reverse=True)

    fieldnames = [
        'firm', 'website', 'location', 'type', 'score', 'tier',
        'alts_venture_evidence', 'estimated_check_capacity',
        'rationale', 'confidence', 'contact_hint'
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow({k: row.get(k, '') for k in fieldnames})

def main():
    # Get input CSV
    input_csv = "/Users/oscar/Downloads/apollo-contacts-export (3).csv"
    output_csv = "/Users/oscar/Downloads/lp_prospects_scored.csv"

    if len(sys.argv) > 1:
        input_csv = sys.argv[1]
    if len(sys.argv) > 2:
        output_csv = sys.argv[2]

    if not Path(input_csv).exists():
        print(f"❌ Input CSV not found: {input_csv}")
        sys.exit(1)

    print(f"📁 Input: {input_csv}")
    print(f"📁 Output: {output_csv}")
    print(f"🔑 API Key: {'✓ set' if PERPLEXITY_API_KEY else '✗ NOT SET'}")

    if not PERPLEXITY_API_KEY:
        print("\n❌ Set PERPLEXITY_API_KEY environment variable:")
        print("   export PERPLEXITY_API_KEY='pplx_...'")
        sys.exit(1)

    # Extract and batch
    print(f"\n🔍 Extracting distinct firms...")
    batches = extract_firms_from_csv(input_csv, batch_size=20)
    print(f"✓ Found {sum(len(b) for b in batches)} distinct firms in {len(batches)} batches")

    # Process
    process_batches(batches, output_csv)

if __name__ == "__main__":
    main()
