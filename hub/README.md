# ID8 Cloud Intelligence Hub

Private Docusaurus site for the systems ID8 runs in the cloud. Branded with the ID8 "Latent Order" design language (Sora and Roboto Serif, charcoal on paper, hairline rules).

## Local development

```bash
cd hub
npm install
npm start          # dev server at http://localhost:3000
npm run build      # static build into ./build
npm run serve      # serve the build at http://localhost:8080
```

## Structure

```
hub/
  docs/
    overview.md                 Capabilities (external pitch)
    projects/pitchbook-attio.md
    projects/apollo-reach-out.md
    projects/intelligence.md     Co-Invest Radar + Thesis Radar
    research/index.md
    admin/index.md
  src/pages/index.js             custom home with signal-field hero
  src/pages/investors.js         the one PUBLIC page — no sign-in required
  src/components/SignalField.js
  src/css/custom.css             the design language
  static/img, static/fonts
  server/                        Express gate + static server (see AUTH_SETUP.md)
```

## Adding a project

Add a markdown file under `docs/projects/`, then register it in `sidebars.js` and add a card in `src/pages/index.js`.

## Deploy (Cloud Run behind a Google sign-in gate, fronted by Firebase Hosting)

Everything is private except `/investors`. The site is served by a small
Express server (`server/`) on Cloud Run — not plain static Hosting — because
that's where the sign-in check happens; see `AUTH_SETUP.md` for why and for
full one-time setup + deploy steps. Condensed:

```bash
# one-time: Artifact Registry repo
gcloud artifacts repositories create id8-hub --repository-format=docker --location=us-central1

# build + deploy the gated Cloud Run service (private)
gcloud builds submit --config cloudbuild.yaml .

# point Firebase Hosting's rewrite at it (see firebase.json)
firebase deploy --only hosting --project molten-crowbar-498920-q8
```

## Weekly rebuild ("alive")

A Cloud Scheduler job triggers a rebuild once a week so data-driven pages refresh on their own.

```bash
gcloud scheduler jobs create http id8-hub-weekly \
  --schedule="0 6 * * 1" \
  --uri="https://cloudbuild.googleapis.com/v1/projects/$PROJECT_ID/triggers/<TRIGGER_ID>:run" \
  --oauth-service-account-email=<SCHEDULER_SA> \
  --http-method=POST
```
