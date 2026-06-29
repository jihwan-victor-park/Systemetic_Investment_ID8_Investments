# LP Prospect Screening System — Complete Filtering Guide

## Overview
**Goal:** Identify ultra-high-net-worth individuals (UHNWIs), family offices, and small RIAs as prospective Limited Partners for ID8 Growth Opportunities Fund I.

**Key Insight:** The wrong approach pulls in massive platforms (Raymond James, Mercer, Edward Jones, Fidelity). The right approach is **restrictive inclusion + aggressive exclusion + employee count filter**.

---

## Stage 1: Apollo CSV Filtering (Pre-Research)

This is where you filter BEFORE we even touch Perplexity. These filters cut noise by 90%.

### 1a. Inclusion Keywords (ONLY these)
These are self-descriptive terms only real family offices and boutique RIAs use. Large asset managers never call themselves these.

```
✅ family office
✅ single family office
✅ multi-family office
✅ private family office
✅ family wealth
✅ registered investment advisor
✅ RIA
```

**Why:** Large platforms (Mercer, Edward Jones, etc.) use "wealth management" and "investment management" but real FOs use specific, self-descriptive terminology.

### 1b. Exclusion Keywords (REMOVE these)

**Retail Wirehouses & Large Platforms:**
- bank, banking
- brokerage, broker-dealer
- insurance
- Raymond James
- Edward Jones
- Morgan Stanley
- Wells Fargo
- Merrill Lynch
- UBS
- Fidelity
- Vanguard
- BlackRock
- Charles Schwab
- Ameriprise
- Northwestern Mutual
- LPL Financial

**Wrong Asset Classes:**
- hedge fund
- private equity
- venture capital
- real estate
- asset management (too broad)
- fund administration

**Wrong Service Types:**
- accounting
- tax
- payroll
- fintech
- software
- technology

**Why Each Category:**
- **Wirehouses:** Retail wealth platforms, not high-conviction LPs
- **Insurance:** Different product entirely
- **PE/VC/Hedge:** Institutional allocators, not your profile (competitors or different mandate)
- **Real estate:** Wrong alternative asset class
- **Accounting/tax:** Financial services but wrong kind (service providers, not allocators)
- **Fintech/software:** Tech companies masquerading as financial services

### 1c. Employee Count Filter (CRITICAL)
```
1-50 employees
```

**Why This Matters:**
- Real family offices: 2–30 people
- Real RIAs serving HNWIs: 5–50 people
- Large "RIAs": 500+ employees (Raymond James, LPL, etc.)
- Any firm >50 employees claiming to be FO/RIA is likely a platform

**This single filter cuts out 90% of wrong results.**

### 1d. Location Filter
```
Los Angeles area
(Beverly Hills, Pasadena, Irvine, Santa Monica, Newport Beach, Westlake Village, etc.)
```

---

## Stage 2: Our Pre-Processing (CSV to Candidates)

After you export Apollo data with Stage 1 filters, we apply additional quality checks:

### 2a. Type Classification
Using Apollo's `Company Type` field + Industry + firm name:

**INCLUDE:**
- Company Type = "RIA", "Family Office", or "Both"
- Industry = "investment management" (after Stage 1 exclusions)
- Firm name matches keeper keywords (family office, registered investment advisor)

**EXCLUDE:**
- Any venture capital, private equity, growth equity firms
- Healthcare, government, operating companies
- Firms with <2 or >50 employees (outliers)

### 2b. Contact Extraction
Extract the most senior decision-maker per firm:

**Good Titles (keep):**
- Partner, Principal, Managing Director, Managing Partner
- Founder, Co-Founder
- Chief Investment Officer (in wealth context)
- VP Investments, Head of Investments, Director of Investments
- President, CEO (in small firm context)

**Bad Titles (skip):**
- Limited Partner, LP (not a real person)
- Consultant, Coordinator, Assistant, Analyst
- HR, Operations, Administrative
- Generic (Wealth Advisor, Financial Advisor without decision-making context)

**Contact Quality Rule:**
- Prefer contacts with senior investment titles
- Skip firms where only contact is support staff
- For multi-location firms with LA office: keep if decision-maker is identifiable

### 2c. Location + Office Filter
**INCLUDE:**
- LA-area address (primary office)
- Multi-office firms with LA office AND decision-maker identifiable there

**EXCLUDE:**
- Non-LA firms (even if they have a satellite office)
- Firms where location is unknown/generic

---

## Stage 3: Perplexity Research & Scoring

Once we have pre-filtered candidates, Perplexity researches each firm to answer:

### 3a. Research Questions
1. **Type Confirmation:** Is it actually a family office, RIA, or something else?
2. **Alts/Venture Appetite:** Do they invest in venture/private markets/alternatives?
   - Concrete evidence: named fund commitments, direct deals, SEC Form ADV showing alternatives
   - Weak signal: generic "we offer alternatives" statement
   - No evidence: score ≤30 (cap it low)
3. **Check Size Capacity:** Can they write $500k+ checks?
   - Family offices >$100M AUM: yes
   - RIAs with large clients: probably yes
   - Boutique firms: maybe
4. **Sector Alignment:** Tech/AI/growth-stage interest?
5. **Decision-Making Speed:** Do they back emerging managers or only established funds?

### 3b. Scoring Rubric (0–100)

| Component | Max Points | Evidence |
|-----------|-----------|----------|
| Alts/venture appetite | 35 | Named fund commitments, direct deals, Form ADV showing PE/VC |
| Check-size $500k+ fit | 20 | AUM, client base, stated minimums |
| Sector alignment (tech/AI/growth) | 20 | Portfolio, stated interests, market positioning |
| Type fit (genuine FO or alts RIA) | 15 | Apollo classification + verification |
| Emerging-manager openness | 10 | Track record with early-stage funds |

**Disqualifiers (subtract points):**
- Pure public-market wealth managers with no alternatives
- Retail-only RIAs with $50k minimums
- Stated policy against blind-pool or emerging-manager funds
- Majority retail client base

### 3c. Tiering

| Tier | Score | Action |
|------|-------|--------|
| **A** | 50–100 | Contact now — clear fit, evidence of alts appetite |
| **B** | 40–49 | Maybe — partial fit, worth investigation |
| **C** | <40 | Skip — poor fit, no alternatives evidence |

---

## Stage 4: Output & Outreach

Final CSV contains:
- **firm** — company name
- **location** — city, state
- **type** — family_office, RIA, or other
- **score** — 0–100 (from Perplexity research)
- **tier** — A, B, or C
- **alts_venture_evidence** — what we found (or "none found")
- **rationale** — 2–3 sentences citing concrete findings
- **contact_hint** — name, title, email of primary contact
- **estimated_check_capacity** — whether they can write $500k+
- **confidence** — high, medium, low (based on research depth)

**Outreach Priority:**
1. A-tier prospects → direct outreach to contact_hint
2. B-tier prospects → secondary follow-up or deeper research
3. C-tier → skip (or review exclusion reasons if curious)

---

## Full Workflow Summary

```
Step 1: Apollo Export
├─ Include keywords: family office, RIA, single family office, multi-family office, family wealth
├─ Exclude keywords: bank, PE, VC, insurance, Raymond James, Edward Jones, etc.
├─ Employee count: 1-50
├─ Location: Los Angeles
└─ Result: ~50-200 firms (depending on dataset size)

Step 2: Our Pre-Processing
├─ Type classification (confirm RIA/FO, reject operating companies)
├─ Contact extraction (senior decision-makers only)
├─ Location validation (LA area + multi-office check)
└─ Result: ~30-100 candidates

Step 3: Perplexity Research (8 parallel workers)
├─ Research each firm for alts appetite, check size, sector fit
├─ Score 0-100 using rubric
├─ Tier as A/B/C
└─ Result: Scored candidates ready for outreach

Step 4: Outreach
├─ A-tier (50+): Contact immediately
├─ B-tier (40-49): Secondary list
└─ C-tier (<40): Archive/skip
```

---

## Key Success Factors

1. **Restrictive Inclusion** — Only "family office" and "RIA" keywords, not broad "wealth management"
2. **Aggressive Exclusion** — Cut out entire categories of wrong types (PE, VC, insurance, banks)
3. **Employee Count** — 1-50 is the magic filter that eliminates platforms
4. **Small Firm Focus** — You're looking for companies you've never heard of, not Raymond James
5. **Decision-Maker Contacts** — Extract Partners/Directors, not advisors
6. **Concrete Evidence** — Perplexity must find real deals, not vague statements
7. **LA Concentration** — Reduces noise, increases relevance

---

## What This Produces

- **High precision:** Only firms that match your actual target profile
- **Fewer false positives:** No more Raymond James or large platforms polluting results
- **Real decision-makers:** Contacts who actually approve LP commitments
- **Actionable tiers:** A-tier is ready to call; B-tier worth deeper work; C-tier skip
