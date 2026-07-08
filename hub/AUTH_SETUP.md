# Hub auth setup

The hub used to be a fully public Firebase Hosting static site. It now runs
behind a small Express server (`server/`) on Cloud Run, fronted by Firebase
Hosting via a rewrite. Every route requires a Google sign-in restricted to
`@id8investments.com`, **except `/investors`**, which stays public.

See the comment at the top of `server/index.js` for why the gate is built as
an allow-list derived from `build/investors/index.html`'s own asset tags,
rather than a blanket "allow /assets/**" rule — the short version: Docusaurus
ships each doc page's content as its own chunk under `/assets/js/`, alongside
genuinely shared framework code, so a blanket rule would leak gated content
through the "shared" assets directory.

## One-time setup (Firebase Console)

1. **Authentication → Sign-in method** → enable **Google**.
2. **Authentication → Settings → Authorized domains** — the Cloud Run /
   Hosting domain should already be listed once you deploy; if not, add it.
3. **Project settings → General → Your apps** — add a **Web app** if one
   doesn't exist yet. Copy its `apiKey` (this is not secret, it's meant to be
   public — the actual access control happens server-side) and confirm
   `authDomain`/`projectId` in `server/login.html` match your project.
4. Set it as an env var on the Cloud Run service (one-time, or whenever it's
   rotated) rather than committing it to the file:
   ```bash
   gcloud run services update id8-cloud-intelligence \
     --region=us-central1 \
     --update-env-vars=FIREBASE_WEB_API_KEY=<the apiKey>
   ```
   `server/index.js` reads `FIREBASE_WEB_API_KEY` at startup and refuses to
   boot if it's unset — `login.html` never has the real key baked into it.

## Grant Firebase Hosting permission to call the private Cloud Run service

The Cloud Run service should be deployed with `--no-allow-unauthenticated` —
the real security boundary is the app-level Google-account check, but there's
no reason to also let anyone hit the raw `*.run.app` URL directly. Firebase's
Hosting service agent needs explicit invoker access:

```bash
PROJECT_NUMBER=$(gcloud projects describe molten-crowbar-498920-q8 --format='value(projectNumber)')

gcloud run services add-iam-policy-binding id8-cloud-intelligence \
  --region=us-central1 \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-firebasehosting.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

## Deploy

```bash
# 1. Build + deploy the Cloud Run service (from hub/)
gcloud builds submit --config cloudbuild.yaml .
# cloudbuild.yaml already deploys with --no-allow-unauthenticated.
# Confirm _REGION/_SERVICE substitutions match what's in firebase.json's
# rewrite (currently: id8-cloud-intelligence / us-central1) if you change them.

# 2. Point Hosting at it
firebase deploy --only hosting --project molten-crowbar-498920-q8
```

Both must be in the **same GCP project** — Firebase Hosting can only rewrite
to a Cloud Run service that lives in the project the Firebase site belongs to
(`molten-crowbar-498920-q8`), not the separate `id8-investments` project the
Flask pipeline uses.

## Verify

```bash
# Public page: should be 200, no redirect
curl -sI https://molten-crowbar-498920-q8.web.app/investors | head -1

# Gated page: should be a 302 to /login
curl -sI https://molten-crowbar-498920-q8.web.app/docs/research/companies/warp | head -1

# Gated document download: should also redirect, not serve the docx
curl -sI https://molten-crowbar-498920-q8.web.app/research/companies/warp.docx | head -1
```

Then open `/investors` in a browser (should load with no prompt) and `/`
(should bounce to `/login`, and a `@id8investments.com` Google account should
land back on the page you started at after signing in).

## Notes

- Session cookies last 5 days (`SESSION_MAX_AGE_MS` in `server/index.js`).
  There's no revocation UI wired up here — if you ever need to force
  everyone off (e.g. someone leaves the team), use
  `admin.auth().revokeRefreshTokens(uid)` for that user from a one-off
  script, or rotate/disable their Google Workspace account, which achieves
  the same thing.
- If `createSessionCookie`/`verifyIdToken` fail with a permissions error on
  Cloud Run, the default compute service account may need the
  "Firebase Authentication Admin" (`roles/firebaseauth.admin`) role.
- Adding a new fully public page later: it needs the same treatment as
  `/investors` — add its route to `PUBLIC_ROUTE_PATTERNS` in
  `server/index.js` and make sure `publicAssetPathsFromPage` covers its
  built HTML too (or generalize that function to accept multiple pages).
