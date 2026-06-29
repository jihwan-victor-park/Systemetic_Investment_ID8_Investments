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
  src/components/SignalField.js
  src/css/custom.css             the design language
  static/img, static/fonts
```

## Adding a project

Add a markdown file under `docs/projects/`, then register it in `sidebars.js` and add a card in `src/pages/index.js`.

## Deploy (Cloud Run + IAP)

The site is private. Deploy behind Cloud Run with IAP scoped to the `@id8investments.com` Workspace domain.

```bash
# one-time: Artifact Registry repo
gcloud artifacts repositories create id8-hub --repository-format=docker --location=us-central1

# build + deploy (private)
gcloud builds submit --config cloudbuild.yaml .

# put IAP in front and grant the org
# (Console: Cloud Run service > Security > IAP, then grant
#  domain:id8investments.com the IAP-secured Web App User role)
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
