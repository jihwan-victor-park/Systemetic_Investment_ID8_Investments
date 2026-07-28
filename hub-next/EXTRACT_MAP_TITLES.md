# Extract Actual Market Map Titles

This script reads all market-map images from GCS, uses Claude vision to extract the actual map title from each image, and outputs a CSV mapping current database titles to the real titles.

## Setup

### 1. Get Firebase Admin key
Download from GCP Console → Firestore → Settings → Service Accounts → Generate new private key (JSON)

```bash
# Save it in the repo root
mv ~/Downloads/molten-crowbar-498920-q8-*.json ./firebase-key.json
```

### 2. Install dependencies
```bash
npm install firebase-admin @google-cloud/storage @anthropic-ai/sdk
```

### 3. Set environment variables
```bash
export FIREBASE_ADMIN_KEY=$(pwd)/firebase-key.json
export ANTHROPIC_API_KEY=sk-...  # Your Claude API key
export GCP_PROJECT_ID=molten-crowbar-498920-q8  # Optional, auto-detected from key
```

## Run

```bash
node scripts/extract-map-titles.mjs > market-map-titles.csv
```

This will:
- Query all ~80+ market-map entries from Firestore
- Download each image from GCS
- Send to Claude Haiku (cheapest model) to extract the map title
- Output a CSV with `current_title,actual_title`

**Cost estimate**: ~$0.15–0.30 (Haiku vision is ~$0.80 per million input tokens, images are small)

**Time**: ~5–10 minutes (rate-limited to 100ms per entry to avoid API throttling)

## Output

```csv
current_title,actual_title
"The AI Agent Market Map","AI Agent Market Map"
"State of AI Infra","AI Infrastructure Market Map"
...
```

Then you can use that CSV to bulk-rename entries in your admin interface or via a follow-up script.
