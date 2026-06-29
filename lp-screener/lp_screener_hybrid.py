#!/usr/bin/env python3
"""
LP Prospect Screener — Hybrid pre-filter + Perplexity research
Target: RIAs, Family Offices, Multi-Family Offices, Private Wealth managers in LA area
"""

import csv, json, re, os, sys, asyncio, requests

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# ─── LOCATION ────────────────────────────────────────────────────────────────
LA_CITIES = {
    'los angeles', 'beverly hills', 'santa monica', 'pasadena', 'irvine',
    'newport beach', 'westlake village', 'malibu', 'bel air', 'century city',
    'west hollywood', 'calabasas', 'sherman oaks', 'encino', 'woodland hills',
    'studio city', 'brentwood', 'marina del rey', 'culver city', 'el segundo',
    'manhattan beach', 'hermosa beach', 'redondo beach', 'long beach',
    'torrance', 'carson', 'glendale', 'burbank', 'northridge', 'chatsworth',
    'thousand oaks', 'camarillo', 'ventura', 'santa barbara',
}

# ─── INDUSTRY GATE ───────────────────────────────────────────────────────────
# Only these Apollo industry values are allowed through
GOOD_INDUSTRIES = {
    'financial services',
    'investment management',
    'capital markets',
    'wealth management',
    'fund-raising',  # some FOs show up here; let through and name-filter
}

# These industry values are immediate disqualifiers regardless of name
BAD_INDUSTRIES = {
    'venture capital & private equity',   # GPs, not LPs
    'accounting',
    'law practice',
    'legal services',
    'management consulting',
    'online media',
    'internet',
    'nonprofit organization management',
    'information technology & services',
    'airlines/aviation',
    'security & investigations',
    'staffing & recruiting',
    'professional training & coaching',
    'writing & editing',
    'real estate',
    'think tanks',
    'entertainment',
    'hospital & health care',
    'health, wellness and fitness',
    'insurance',
    'banking',
    'outsourcing/offshoring',
    'consumer goods',
    'retail',
    'marketing and advertising',
    'public relations and communications',
    'human resources',
}

# ─── NAME-BASED SIGNALS ──────────────────────────────────────────────────────
# Firm must contain at least ONE positive signal
POSITIVE_NAME_SIGNALS = [
    r'wealth\s+management',
    r'wealth\s+(advisor|advisors|advisers|partners|capital|group)',
    r'private\s+wealth',
    r'family\s+office',
    r'family\s+wealth',
    r'investment\s+(counsel|management|advisory|advisors|partners)',
    r'asset\s+management',
    r'capital\s+management',
    r'financial\s+(planning|advisory|advisors|advisers|services|group|partners)',
    r'wealth$',  # ends in "wealth"
    r'^wealth',  # starts with "wealth"
    r'\bria\b',
    r'private\s+(capital|investment)',
    r'multi.?family',
    r'registered\s+investment',
    r'financial\s+planning',
    r'fiduciary',
    r'portfolio\s+management',
]

# Firm name must NOT match any of these (even if industry looks ok)
NEGATIVE_NAME_PATTERNS = [
    # VC/PE/Equity shops
    r'\b(ventures|venture\s+group|venture\s+capital|private\s+equity|growth\s+equity)\b',
    r'\b(buyout|leveraged|mezzanine|distressed)\b',
    r'\bequity\s+(partners|group|capital|fund)\b',

    # Known large institutional GPs (not LPs)
    r'\b(oaktree|blackrock|vanguard|fidelity|blackstone|carlyle|kkr|apollo global)\b',
    r'\b(leonard green|freeman spogli|platinum equity|lightbay capital|the gores group)\b',
    r'\b(capital group|tcw|pimco|dimensional fund)\b',

    # Accounting / Legal / CPA
    r'\b(cpa|certified public accountant|accountants?)\b',
    r'\b(law\s+corporation|law\s+offices?|law\s+firm|llp|plc|attorneys?)\b',
    r'\b(legal\s+services|counsel\s+llp)\b',

    # Insurance / annuity
    r'\b(insurance\s+services?|annuity|life\s+insurance)\b',
    r'financial\s+&\s+insurance',
    r'financial\s+and\s+insurance',

    # Pension / Retirement specialists
    r'\b(pension\s+planner|retirement\s+specialist|pension\s+plan|retirement\s+income)\b',

    # Coaching / Education / Literacy
    r'\b(coaching|financial\s+literacy|financial\s+empowerment|empowered)\b',

    # Media / News / Podcast
    r'\b(media|news\s+network|podcast|broadcasting)\b',

    # Non-profit / Alliance / Institute
    r'\b(cross\s+border\s+alliance|community\s+foundation|institute\s+for)\b',

    # Staffing / Recruiting
    r'\b(staffing|recruiting)\b',

    # Business Management (entertainment/celebrity focused)
    r'\b(business\s+management)\b',

    # Fintech / Software / Technology
    r'\b(fintech|saas|software)\b',

    # Lending / Mortgage
    r'\b(lending\s+group|mortgage|loan)\b',

    # Applied / basic financial planning (retail-focused)
    r'^applied\s+financial\s+planning',

    # Too generic / unclear
    r'^(profit\s+partner|hubwallet|creditdonkey|appmo|ufinancial)\b',
]

# ─── CONTACT QUALITY ─────────────────────────────────────────────────────────
GOOD_TITLE_SIGNALS = [
    'partner', 'managing director', 'founder', 'co-founder', 'president',
    'chief executive', 'chief investment', 'ceo', 'cio', 'managing partner',
    'head of', 'director of', 'principal', 'vice president', 'vp',
    'portfolio manager', 'investment officer', 'wealth advisor', 'wealth manager',
    'financial advisor', 'relationship manager',
]

BAD_TITLE_SIGNALS = [
    'lp', 'limited partner', 'administrative', 'receptionist', 'coordinator',
    'hr ', 'human resources', 'recruiter', 'marketing', 'operations manager',
    'it ', 'information technology', 'software', 'developer', 'engineer',
    'data ', 'compliance officer',  # not wrong but not decision-makers
]


def norm(v):
    return (v or '').strip()


def is_la(row):
    city = norm(row.get('Company City')).lower()
    return city in LA_CITIES


def industry_ok(row):
    ind = norm(row.get('Industry')).lower()
    if not ind:
        return True  # unknown industry: let name signals decide
    for bad in BAD_INDUSTRIES:
        if bad in ind:
            return False
    # If industry is explicitly good, pass
    for good in GOOD_INDUSTRIES:
        if good in ind:
            return True
    # Industry present but not in either list: block (e.g. "real estate", "healthcare")
    return False


def name_has_positive_signal(firm_name):
    name = firm_name.lower()
    for pat in POSITIVE_NAME_SIGNALS:
        if re.search(pat, name):
            return True
    return False


def name_has_negative_signal(firm_name):
    name = firm_name.lower()
    for pat in NEGATIVE_NAME_PATTERNS:
        if re.search(pat, name):
            return True
    return False


def title_quality(title):
    t = title.lower()
    if any(s in t for s in BAD_TITLE_SIGNALS):
        return 'bad'
    if any(s in t for s in GOOD_TITLE_SIGNALS):
        return 'good'
    return 'ok'


def extract_firms(csv_path):
    """
    Extract one record per firm:
    - LA area only
    - Industry gate (good or unknown, not bad)
    - Name must have positive signal AND no negative signal
    - Best (most senior) contact per firm
    """
    rows = list(csv.DictReader(open(csv_path, encoding='utf-8', errors='replace')))

    firm_contacts = {}  # firm -> list of contacts

    for r in rows:
        co = norm(r.get('Company Name'))
        if not co:
            continue
        if not is_la(r):
            continue
        if not industry_ok(r):
            continue
        if not name_has_positive_signal(co):
            continue
        if name_has_negative_signal(co):
            continue

        first = norm(r.get('First Name'))
        last = norm(r.get('Last Name'))
        title = norm(r.get('Title'))
        email = norm(r.get('Email'))

        if not (first and last):
            continue
        if title.lower() in ('lp', 'limited partner', ''):
            continue

        contact = {
            'firm': co,
            'website': norm(r.get('Website')),
            'location': f"{norm(r.get('Company City'))}, {norm(r.get('Company State'))}".strip(', '),
            'industry': norm(r.get('Industry')),
            'company_type': norm(r.get('Company Type 2490 0616201746')),
            'aum': norm(r.get('AUM')),
            'contact_name': f"{first} {last}",
            'contact_title': title,
            'contact_email': email,
            'title_q': title_quality(title),
        }

        if co not in firm_contacts:
            firm_contacts[co] = []
        firm_contacts[co].append(contact)

    # Pick best contact per firm (good > ok > bad)
    results = []
    RANK = {'good': 0, 'ok': 1, 'bad': 2}
    for co, contacts in firm_contacts.items():
        best = sorted(contacts, key=lambda c: RANK[c['title_q']])[0]
        results.append(best)

    return results


def format_batch_prompt(firms):
    lines = []
    for i, f in enumerate(firms):
        contact = f"{f['contact_name']} ({f['contact_title']}) {f['contact_email']}".strip()
        aum = f" | AUM: {f['aum']}" if f['aum'] else ''
        ctype = f" | Type: {f['company_type']}" if f['company_type'] else ''
        lines.append(
            f"{i+1}. {f['firm']} | {f['website']} | {f['location']}{ctype}{aum} | Contact: {contact}"
        )

    firms_text = '\n'.join(lines)

    return f"""You are an LP-prospecting analyst for ID8 Growth Opportunities Fund I — a $50M Series B–D growth-stage tech/AI venture co-invest fund. Min LP commitment $500k. Target LPs: Family Offices, Multi-Family Offices, RIAs with discretionary AUM.

Research each firm. Be skeptical — no venture/alts evidence = low score. Never fabricate.

FIRMS:
{firms_text}

For each firm, determine:
1. Is it a genuine FO, RIA, or multi-family office? (not a VC/PE fund, not an operating company)
2. Does it allocate to venture/private markets/alternatives? Search SEC Form ADV, news, Crunchbase.
3. Can it write $500k+ checks comfortably?
4. Any tech/AI/growth-stage interest?
5. Is it open to emerging/Fund I managers?

SCORING (0–100):
- Alts/venture appetite (max 35): concrete evidence of VC/PE/fund allocations
- Check-size $500k+ (max 20): AUM suggests capacity
- Sector alignment tech/AI (max 20): stated interest or portfolio evidence
- Type fit FO/RIA (max 15): genuine allocator, not just an adviser
- Emerging-manager openness (max 10): Fund I friendly signals

PENALIZE: pure public-market managers, retail-only RIAs, advisory-only (no discretionary capital), insurance/annuity shops.

Tiers: A (>=60 contact now) | B (40-59 maybe) | C (<40 skip)

Return ONLY a JSON array, no prose, no markdown:
[{{"firm":"Name","website":"URL","location":"City, State","type":"family_office|RIA|other","score":0,"tier":"A|B|C","alts_venture_evidence":"1 sentence + URL or none found","estimated_check_capacity":"$Xk-$YM or unknown","rationale":"2-3 sentences citing sources","confidence":"high|medium|low","contact_hint":"name (title) email"}}]"""


async def call_perplexity_async(prompt, batch_num, model='sonar-pro'):
    headers = {'Authorization': f'Bearer {PERPLEXITY_API_KEY}', 'Content-Type': 'application/json'}
    payload = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 4000, 'temperature': 0.2}
    loop = asyncio.get_event_loop()
    try:
        resp = await loop.run_in_executor(None, lambda: requests.post(PERPLEXITY_API_URL, json=payload, headers=headers, timeout=90))
        resp.raise_for_status()
        result = resp.json()
        tokens = result.get('usage', {}).get('total_tokens', '?')
        print(f'  [Batch {batch_num}] ✓ ({tokens} tokens)')
        return batch_num, result['choices'][0]['message']['content'], None
    except Exception as e:
        print(f'  [Batch {batch_num}] ✗ {e}')
        return batch_num, None, str(e)


def parse_json(text):
    text = text.strip()
    for prefix in ('```json', '```'):
        if text.startswith(prefix):
            text = text[len(prefix):]
    if text.endswith('```'):
        text = text[:-3]
    return json.loads(text.strip())


def write_csv(results, path):
    if not results:
        return
    results.sort(key=lambda x: x.get('score', 0), reverse=True)
    fields = ['firm', 'website', 'location', 'type', 'score', 'tier',
              'contact_name', 'contact_title', 'contact_email',
              'alts_venture_evidence', 'estimated_check_capacity',
              'rationale', 'confidence']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in results:
            w.writerow({k: row.get(k, '') for k in fields})


async def run(candidates, output_csv, batch_size=10, parallel=8):
    batches = []
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        batches.append((i // batch_size + 1, batch, format_batch_prompt(batch)))

    total = len(batches)
    print(f'\n🚀 {len(candidates)} firms → {total} batches, {parallel} parallel workers\n')

    all_results = []
    for i in range(0, total, parallel):
        group = batches[i:i + parallel]
        nums = f"{group[0][0]}–{group[-1][0]}"
        print(f'📊 Batches {nums} / {total}')
        tasks = [call_perplexity_async(prompt, num) for num, _, prompt in group]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for response, (num, batch, _) in zip(responses, group):
            if isinstance(response, Exception):
                continue
            _, content, err = response
            if err or not content:
                continue
            try:
                results = parse_json(content)
                for r in results:
                    if not r.get('tier'):
                        r['tier'] = 'C'
                    orig = next((f for f in batch if f['firm'] == r.get('firm')), {})
                    r['contact_name'] = orig.get('contact_name', '')
                    r['contact_title'] = orig.get('contact_title', '')
                    r['contact_email'] = orig.get('contact_email', '')
                all_results.extend(results)
            except Exception as e:
                print(f'  [Batch {num}] JSON parse error: {e}')

    write_csv(all_results, output_csv)

    tiers = {'A': 0, 'B': 0, 'C': 0}
    for r in all_results:
        tiers[r.get('tier', 'C')[0]] = tiers.get(r.get('tier', 'C')[0], 0) + 1

    print(f'\n✅ {len(all_results)} firms → {output_csv}')
    print(f'   A (contact now): {tiers["A"]}')
    print(f'   B (maybe):       {tiers["B"]}')
    print(f'   C (skip):        {tiers["C"]}')


def main():
    input_csv = sys.argv[1] if len(sys.argv) > 1 else '/Users/oscar/Downloads/apollo-contacts-export (2).csv'
    output_csv = '/Users/oscar/Downloads/lp_candidates_scored.csv'
    candidates_csv = '/Users/oscar/Downloads/lp_candidates.csv'

    if not PERPLEXITY_API_KEY:
        print('❌ Set PERPLEXITY_API_KEY')
        sys.exit(1)

    print(f'📁 {input_csv}')
    firms = extract_firms(input_csv)
    print(f'✓ {len(firms)} candidates after LA + industry + name filter\n')

    # Show what made it through so user can sanity-check
    for i, f in enumerate(firms, 1):
        print(f"  {i:3d}. {f['firm'][:50]:<50} | {f['industry'][:25]:<25} | {f['contact_name']} ({f['contact_title'][:30]})")

    # Write candidates list
    fields = ['firm', 'website', 'location', 'industry', 'company_type', 'aum', 'contact_name', 'contact_title', 'contact_email']
    with open(candidates_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in firms:
            w.writerow({k: row.get(k, '') for k in fields})
    print(f'\n📋 Candidates → {candidates_csv}')

    asyncio.run(run(firms, output_csv, batch_size=10, parallel=8))


if __name__ == '__main__':
    main()
