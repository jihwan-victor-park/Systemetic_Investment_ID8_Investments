# LP Prospect Filtering Strategy — Double-Filter Approach

## Overview
We use a **two-stage filtering system** to identify high-quality LP prospects (Family Offices, RIAs, and Wealth Management firms) in LA:
1. **Stage 1 (Apollo):** Built-in Apollo filters to narrow the raw export
2. **Stage 2 (Script):** Our pre-filtering logic to catch edge cases and refine

---

## STAGE 1: APOLLO FILTERING (Initial Export)

### Why This Matters
Apollo's default "wealth management" + "investment management" filters are too broad. They pull in:
- ❌ Large platforms (Mercer, Edward Jones, Raymond James, UBS, Fidelity)
- ❌ Retail wealth operations (hundreds/thousands of employees)
- ❌ Banks and brokerages (different business model)

**We want:** Small, independent family offices and RIAs (2–50 employees max) that manage ultra-HNW capital discretely.

---

### Apollo Filter Configuration

#### 1. **INCLUDE Keywords** (Company Name/Keywords field)
```
family office
single family office
multi-family office
private family office
family wealth
private wealth management
```

**Why these:**
- **Self-descriptive terms** — only real FOs call themselves "family office"
- **Large asset managers never use these labels** — they use "management," "advisors," "capital"
- **Tight match** — reduces noise significantly

**❌ DO NOT USE:**
- ❌ "wealth management" (too broad — pulls Edward Jones, Raymond James)
- ❌ "investment management" (includes every asset manager)
- ❌ "financial services" (covers banks, insurance, accounting)

---

#### 2. **EXCLUDE Keywords** (Company Name/Keywords field)
```
bank
banking
brokerage
broker dealer
insurance
Raymond James
Edward Jones
Morgan Stanley
Wells Fargo
Merrill Lynch
UBS
Fidelity
Vanguard
BlackRock
Charles Schwab
Ameriprise
Northwestern Mutual
LPL Financial
asset management
fund administration
hedge fund
private equity
venture capital
real estate
accounting
tax
payroll
fintech
software
technology
consulting
```

**Why each category:**

| Category | Why Exclude | Example |
|----------|------------|---------|
| Banks / Wirehouses | Retail wealth platforms, not FOs | Morgan Stanley, UBS, Wells Fargo |
| Insurance | Different product/business model | Northwestern Mutual |
| PE / VC / Hedge Fund | Institutional allocators, not LPs we target | Blackstone, Sequoia |
| Real Estate | Wrong alternative asset class | CBRE, Cushman & Wakefield |
| Accounting / Tax / Payroll | Financial services but wrong kind | Deloitte, H&R Block |
| Fintech / Software / Tech | Tech companies in "financial services" category | Stripe, Plaid (misclassified) |
| Consulting | Management consulting, not investment | McKinsey, Bain |

---

#### 3. **Employee Count Filter**
```
1–50 employees
```

**Why this is critical:**
- **Real family offices:** 2–30 people (founder + small team)
- **RIAs serving HNW/FO clients:** 10–50 people (boutique operations)
- **Retail platforms:** 500+ employees (Edward Jones, Merrill Lynch, Fidelity)

**This single filter removes 90% of wrong-fit firms.**

---

#### 4. **Title Filter** (Contact Seniority)
```
Partner
CIO
Managing Director
Principal
Head of Investments
Founder
President
```

**Why:**
- Decision-makers only (not analysts, assistants, operations)
- Roles that indicate investment authority
- Titles that appear in FOs and boutique RIAs

---

#### 5. **Location Filter**
```
Los Angeles, CA
```

**Includes LA metro:**
- Los Angeles proper
- Beverly Hills
- Pasadena
- Irvine
- Santa Monica
- Newport Beach
- Westlake Village
- Culver City
- Malibu

---

### Apollo Export Tips

**What you should see after filtering:**
- Company logos on the right: unknown/generic names (Westlake Capital, Meridian Family Office, Pacific Heritage Advisors)
- NOT recognizable brands (if you recognize the name, it's likely too big)
- Small team sizes (1–5 people typically)
- Titles like "Founder," "Partner," "CIO" (not "Wealth Advisor," "Financial Planner")

---

## CRITICAL DISTINCTION: LP Allocator vs. Advisor

**This is where most errors happen.**

### LP Allocator (✅ WANT)
- Deploys its **own capital** into funds
- Has **discretionary AUM** they control
- Form ADV shows "AUM where the adviser has discretionary authority"
- Example: "Westlake Capital manages $500M of family capital; invests in PE, VC"
- Can say: "We committed $2M to Sequoia Fund XV"

### Advisor/RIA Serving Wealthy Clients (❌ OFTEN MISCLASSIFIED)
- Advises clients' capital, doesn't own it
- Can **recommend** alts to clients but doesn't deploy firm capital
- Form ADV shows non-discretionary or client-directed advisory
- Example: "We help clients access venture funds; can syndicate deals to our network"
- Can say: "We recommend private equity for qualified clients" (but don't invest firm capital)

### How to Tell the Difference
| Signal | Allocator | Advisor |
|--------|-----------|---------|
| **Language** | "We invest in...", "Our allocation to...", "We committed..." | "We help clients access...", "We advise on...", "Our clients can..." |
| **Form ADV** | "Discretionary authority" section shows high AUM | "Non-discretionary" or "advisory only" |
| **Business model** | Manage own capital + earn returns | Earn AUM fees by managing client assets |
| **Red flags** | Says they're "a channel to LPs" | Says they help clients find deals |

### How to Validate (For Perplexity Research)

**Look for:**
1. **Form ADV filing** (adviserinfo.sec.gov) → "Discretionary Authority" AUM section
2. **Specific fund commitments** → "We committed $X to Fund Y" (with fund name)
3. **Portfolio company mentions** → Links showing firm invested in/owns stakes
4. **Press releases** → "Fund announces investment by [Firm]" or "[Firm] launches partnership with..."
5. **Direct capital deployment** → "Our portfolio companies" or "Our investments in..."

**Red flags (disqualify):**
- Form ADV shows only "advisory" or "non-discretionary" authority
- All mentions are "we help clients" or "we advise on"
- They're described as "intermediary," "platform," "network," or "alliance"
- They do M&A advisory, accounting, or tax services
- No mention of firm's own capital being deployed

---

## STAGE 2: SCRIPT PRE-FILTERING (Our Secondary Filter)

After exporting from Apollo, our script applies additional filtering logic:

### 2a. **Type Classification** (Using Apollo Data)

We cross-reference three Apollo fields:
1. **Company Type** (custom field: RIA, Family Office, Both)
2. **Industry** (Apollo's classification)
3. **Company Name** (pattern matching)

**Logic:**
```
IF Company Type in [RIA, Family Office, Both]
  → KEEP (high confidence)

ELSE IF Industry in [financial services, investment management]
  AND NOT (venture capital, private equity, growth equity, hedge fund)
  AND has keeper keyword (family office, wealth management, RIA, etc.)
  → KEEP

ELSE IF has keeper keyword AND no disqualifier keyword
  → KEEP

ELSE
  → EXCLUDE
```

**Keeper Keywords (company name matching):**
- family office
- multi-family office
- wealth (management, advisor, planning)
- registered investment advisor
- RIA
- asset management (if small firm)

**Disqualifier Keywords:**
- venture capital
- private equity
- growth equity
- hedge fund
- VC fund

---

### 2b. **Location Filtering**

```
IF City in [Los Angeles, Beverly Hills, Pasadena, Irvine, Santa Monica, Newport Beach, Westlake Village, Culver City]
  OR multi-office firm
  → KEEP

ELSE
  → EXCLUDE
```

---

### 2c. **Contact Quality Filtering**

```
IF contact has no real first/last name
  OR title is "LP" or "Limited Partner"
  → EXCLUDE

ELSE IF title contains good signals (Partner, MD, Principal, CIO, Founder, CEO, Head of)
  → KEEP as high-quality contact

ELSE IF title contains bad signals (Analyst, Assistant, Coordinator, Operations, HR)
  AND no good signals
  → EXCLUDE

ELSE
  → KEEP as acceptable contact
```

---

## FULL FILTERING FLOW (Data to Results)

```
Apollo CSV Export (1,311 firms)
       ↓
   [APOLLO FILTERS]
   - Include keywords: family office, private wealth, etc.
   - Exclude keywords: bank, VC, PE, consulting, etc.
   - Employee count: 1–50
   - Title: Partner, CIO, MD, Principal
   - Location: LA area
       ↓
   Filtered Apollo Export (333 distinct firms)
       ↓
   [SCRIPT PRE-FILTER Stage 1: Type Classification]
   - Company Type = RIA/FO/Both → KEEP
   - Industry = financial services + NO venture signals → KEEP
   - Company name keywords (family office, RIA) → KEEP
   - PE/VC keywords → EXCLUDE
       ↓
   Type-filtered firms (280 candidates)
       ↓
   [SCRIPT PRE-FILTER Stage 2: Location]
   - LA metro or multi-office → KEEP
   - Other → EXCLUDE
       ↓
   Location-filtered firms (150 candidates)
       ↓
   [SCRIPT PRE-FILTER Stage 3: Contact Quality]
   - "LP" or "Limited Partner" → EXCLUDE
   - Partner/MD/CIO title → KEEP as high-quality
   - Analyst/Assistant title → EXCLUDE
       ↓
   Final Pre-filtered Candidates (133 firms)
       ↓
   [PERPLEXITY RESEARCH & SCORING]
   - Research each firm: Type, Alts/Venture appetite, Check size, Sector fit
   - Score 0–100 using rubric
   - Output: A (50-70 contact now) | B (40-49 maybe) | C (<40 skip)
       ↓
   Final Scored List (133 firms)
   - A-tier: 12 prospects
   - B-tier: 12 prospects
   - C-tier: 109 prospects
```

---

## Rationale for Each Filter

### Why Apollo's Include Keywords Are Strict
- **"Family office"** → Only real FOs self-identify this way
- **Large platforms** (Edward Jones, Raymond James) use "wealth management" but have 5,000+ employees
- **Broad terms pull noise** → Every financial company calls itself "investment management"

### Why Employee Count (1–50) Is the Killer Filter
```
Family Office:           2–30 people
Boutique RIA:           10–50 people
Mid-market RIA:         50–200 people
Large RIA platform:    200–500 people
Retail platforms:      500–5,000 people
```
The 1–50 range captures real FOs and boutique RIAs, excludes everything else.

### Why Exclude Large Names
If Apollo shows you "Fidelity" or "Merrill Lynch," it's the retail wealth division, not an LP.
**The goal:** Firms you've never heard of, with 8 employees, in a suite at Wilshire Boulevard.

### Why 8 Parallel Workers (Script)
- 133 firms ÷ 10 per batch = 14 batches
- 14 batches ÷ 8 workers = 2 rounds of parallel processing
- Total runtime: ~4 minutes (vs 15+ sequential)

---

## Output Tiers Explained

### A-Tier (50–70): Contact Now
- **Type:** Explicit RIA, Family Office, or clear Wealth Management
- **Venture/Alts Evidence:** Concrete evidence (Form ADV shows alts, mentioned fund commitments, explicit statement)
- **Check Size:** $500k+ plausible
- **Confidence:** High or Medium
- **Example:** "Meridian Family Office — $2B AUM, manages family capital across growth equity and venture"

### B-Tier (40–49): Maybe
- **Type:** Likely RIA or Wealth Management (evidence thin)
- **Venture/Alts Evidence:** Weak or none (may have capacity but no proven appetite)
- **Check Size:** Uncertain but plausible
- **Confidence:** Low-Medium
- **Example:** "Pacific Capital Advisors — RIA with HNW clients, no explicit alts evidence found"

### C-Tier (<40): Skip
- **Rationale:** Pure public-market wealth manager, retail platform, or unverifiable
- **Example:** "Westshore Advisors — Index-focused, no alternatives; likely retail"

---

## Next Steps

1. **Apply Stage 1 (Apollo) filters** on your original 1,311 CSV
2. **Export the filtered list** from Apollo
3. **Run our script** on the export (Stage 2 filtering + Perplexity research)
4. **Review A-tier results** and begin outreach to Partners/Founders/CIOs

---

## Key Takeaway

> **Double filtering works because:**
> - Apollo's filters remove 80% of noise (large platforms, wrong industries)
> - Our script removes the remaining 15% (name patterns, contact quality, location)
> - Perplexity validates the 5% that remain (research + scoring)
> 
> **Result:** 133 → 24 high-quality prospects you can confidently call.
