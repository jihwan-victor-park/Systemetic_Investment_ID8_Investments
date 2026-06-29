# LP Prospect Screener — Perplexity API Setup

## What This Does

Batch-researches all 130+ firms from your Apollo CSV using Perplexity API.
- Researches each firm for: type (FO/RIA/other), venture/alts evidence, check size capacity
- Scores 0–100 using the same rubric as the manual screener
- Outputs single most-senior contact per firm
- Returns scored CSV ready for import

## Setup (5 minutes)

### 1. Get Perplexity API Key

1. Go to https://www.perplexity.ai/api
2. Sign up or log in
3. Go to Settings → API Keys
4. Create new API key (free tier available)
5. Copy the key

### 2. Set Environment Variable

```bash
export PERPLEXITY_API_KEY='pplx_YOUR_KEY_HERE'
```

Or add to your shell profile (~/.zshrc or ~/.bashrc):
```bash
echo "export PERPLEXITY_API_KEY='pplx_YOUR_KEY_HERE'" >> ~/.zshrc
source ~/.zshrc
```

### 3. Install Dependencies (if needed)

```bash
pip install requests
```

## Run the Screener

```bash
python3 perplexity_lp_screener.py
```

**Default paths:**
- Input: `/Users/oscar/Downloads/apollo-contacts-export (3).csv`
- Output: `/Users/oscar/Downloads/lp_prospects_scored.csv`

**Custom paths:**
```bash
python3 perplexity_lp_screener.py <input.csv> <output.csv>
```

## What You'll See

```
📁 Input: /Users/oscar/Downloads/apollo-contacts-export (3).csv
📁 Output: /Users/oscar/Downloads/lp_prospects_scored.csv
🔑 API Key: ✓ set

🔍 Extracting distinct firms...
✓ Found 130 distinct firms in 7 batches

📊 Batch 1/7 (20 firms)
   Firms: Cooke Wealth Management, Brentwood Financial Advisors, ...
   Calling Perplexity (sonar)... ✓ (tokens: 2847)
   ✓ Received 20 results

📊 Batch 2/7 (20 firms)
   ...

✅ Wrote 130 firms to /Users/oscar/Downloads/lp_prospects_scored.csv

📈 Summary:
   A-tier (contact now): 8
   B-tier (maybe): 22
   C-tier (skip): 100
```

## Output CSV Columns

| Column | Purpose |
|--------|---------|
| `firm` | Company name |
| `website` | Website URL |
| `location` | City, State |
| `type` | `family_office`, `RIA`, or `other` |
| `score` | 0–100 score |
| `tier` | A, B, or C |
| `alts_venture_evidence` | What evidence of venture/alts activity was found |
| `estimated_check_capacity` | Can they write $500k+ |
| `rationale` | 2–3 sentences explaining the score |
| `confidence` | `high`, `medium`, or `low` confidence in the research |
| `contact_hint` | Most senior contact: name, title, email |

## Cost Estimate

- **Perplexity "sonar" model:** ~$0.01 per 1000 tokens
- **Per batch:** ~$0.03–$0.05 (depending on complexity)
- **Total for 130 firms (7 batches):** ~$0.25–$0.40

For better accuracy, upgrade to `sonar-pro` (costs ~$0.10/batch, ~$0.70 total).

## Troubleshooting

### `PERPLEXITY_API_KEY not set`
```bash
export PERPLEXITY_API_KEY='pplx_YOUR_KEY'
python3 perplexity_lp_screener.py
```

### JSON parse error
- Perplexity returned non-JSON. Try `sonar-pro` instead of `sonar` for better consistency.
- Edit the script: change `MODEL = "sonar"` to `MODEL = "sonar-pro"`

### Rate limits
Perplexity free tier may have rate limits. If you hit them:
- Wait a few minutes and retry
- Upgrade to paid tier
- Process in smaller batches (edit `batch_size=20` in the script)

## Model Options

| Model | Cost | Speed | Accuracy |
|-------|------|-------|----------|
| `sonar` | Low | Fast | Good |
| `sonar-pro` | Medium | Medium | Better |
| `sonar-reasoning` | Higher | Slower | Best |

Default is `sonar` (fastest, cheapest). Change in script if needed.

## Next Steps

1. Run the script
2. Review output CSV (sort by score descending)
3. Filter A-tier prospects for outreach
4. Import contact list to your CRM with tier/score for context
