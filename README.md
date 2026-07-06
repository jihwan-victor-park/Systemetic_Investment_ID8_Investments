# ID8 Cloud Intelligence

The systems ID8 runs in the cloud, plus the hub that documents them. This is a
monorepo with a few independent parts.

## Layout

| Path | What it is |
| --- | --- |
| `pipeline/` | The Flask service. Syncs PitchBook to Attio and Attio to Apollo. Deployed via the root `Procfile` / `Dockerfile`. Holds its own `Documents/` and `attio_import/` I/O folders. |
| `lp-screener/` | The LP prospect screener. Research plus rubric scoring (standalone CLIs). |
| `deal_intelligence/` | The two-stage deal intelligence layer. Stage 1 scores every qualified deal, stage 2 deep-researches the ones that pass. |
| `hub/` | The Docusaurus site. The internal docs hub and the investor-facing view. |
| `design/` | Generators for the branded guides and the canvas art, plus brand assets and the design philosophy. |
| `n8n-cloudrun/` | n8n orchestration on Cloud Run: workflows, deploy script, migration plan. |
| `cc-attio-sync/` | Standalone Cloud Run webhook: Attio list membership → Constant Contact list sync. |
| `docs/` | Planning and strategy. The build plan and the LP screening guides. |

## Running each part

```bash
# Pipeline service (deps shared at root)
pip install -r requirements.txt
gunicorn --chdir pipeline --bind 0.0.0.0:8080 app:app

# Docs hub
cd hub && npm install && npm start

# Rebuild the branded guides and covers (outputs into hub/static)
cd design && npm install && node build_cover.js && node build_apollo.js && node build_pitchbook.js

# Deal intelligence (after the rubric and prompts are filled in)
python -m deal_intelligence.pipeline --dry-run
```

## Not in Git

Local data and generated artifacts are gitignored: `node_modules/`, `hub/build/`,
`__pycache__/`, the investor data CSVs, the budget xlsx, and the generated
`design/*.html` intermediates. See `.gitignore`.

## Secrets

All secrets come from environment variables: `ATTIO_API_KEY`, `APOLLO_API_KEY`
(master), `PERPLEXITY_API_KEY`, `ANTHROPIC_API_KEY`. Never commit a key.
