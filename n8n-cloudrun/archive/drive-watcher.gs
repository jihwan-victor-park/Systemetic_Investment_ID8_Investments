/**
 * ⚠️ ABANDONED (Jul 2026) — see ../archive/WEBHOOK_SETUP.md for why this was
 * reverted, and ../deploy.sh's header comment for the current architecture
 * (native Drive/Sheets Trigger polling nodes, n8n kept warm with
 * --min-instances=1). Not deployed. Kept for reference only.
 *
 * Google Apps Script — Drive folder watcher + Sheet change watcher for n8n
 *
 * Replaces all four Google Drive Trigger nodes in the n8n workflow. Runs free
 * on Google's servers. POSTs to n8n Webhook nodes only when something new
 * actually appears, so Cloud Run n8n can scale to zero between events.
 *
 * n8n's Cloud Run service is IAM-restricted (org network policy blocks public
 * access), so every call needs a valid Cloud Run identity token. This script
 * mints one itself by impersonating a dedicated service account — see
 * N8N_INVOKER_SA below and the one-time GCP setup in the repo's chat history /
 * README. No key file is stored anywhere; impersonation uses your own Google
 * identity (ScriptApp.getOAuthToken()), which is why appsscript.json needs the
 * cloud-platform OAuth scope added.
 *
 * SETUP
 *  1. script.google.com → New project → paste this file as Code.gs.
 *  2. Also replace the manifest (View → Show manifest file) with this repo's
 *     appsscript.json, so the cloud-platform scope is granted.
 *  3. Confirm N8N_BASE and N8N_INVOKER_SA below match your deployment.
 *  4. Run installTriggers() once and approve the permission prompts.
 *  5. Done — checkFolders() fires every 5 min; jesseTrigger() fires on sheet edits.
 */

// ── CONFIG ────────────────────────────────────────────────────────────────────

const N8N_BASE = 'https://n8n-bkq2vtg6qq-uk.a.run.app'; // set for the live n8n service

// Service account this script impersonates to mint a Cloud Run identity token.
// Must already have roles/run.invoker on the n8n service, and your own account
// must have roles/iam.serviceAccountTokenCreator on this service account.
const N8N_INVOKER_SA = 'n8n-invoker@molten-crowbar-498920-q8.iam.gserviceaccount.com';

const FOLDER_WATCHERS = [
  {
    name: 'PitchBook Weekly Drop',
    folderId: '1GVVMI-xX3toVtc-hiypb2TLemZ8uHX8S',
    webhookPath: '/webhook/pitchbook-drop',
  },
  {
    name: 'Watchlist Drop',
    folderId: '1sdiMtR7RnM-J5zHVSV5_stykFUK7eyxU',
    webhookPath: '/webhook/watchlist-drop',
  },
  {
    name: 'Top 10 VCs Deals',
    folderId: '1MnwePOMH44sMn1522ZC2vOVDVCWeMuDH',
    webhookPath: '/webhook/top10-drop',
  },
];

// Jesse's Deals: watches the spreadsheet for edits, then n8n reads the rows itself.
const JESSE_SHEET_ID   = '1-ebci81-Y-31fI7wQKHXymCfOcPYlXuEm7p8s0ziiXA';
const JESSE_WEBHOOK    = '/webhook/jesse-deals';

const CHECK_EVERY_MINUTES = 5;

// ── FOLDER WATCHERS ───────────────────────────────────────────────────────────

function checkFolders() {
  const props = PropertiesService.getScriptProperties();

  for (const w of FOLDER_WATCHERS) {
    const seenKey  = 'seen_' + w.folderId;
    const rawSeen  = props.getProperty(seenKey);
    const seen     = new Set(JSON.parse(rawSeen || '[]'));
    const firstRun = !rawSeen;

    const folder   = DriveApp.getFolderById(w.folderId);
    const files    = folder.getFiles();
    const current  = [];

    while (files.hasNext()) {
      const f  = files.next();
      const id = f.getId();
      current.push(id);

      if (!seen.has(id)) {
        if (!firstRun) {
          notifyN8n(w.name, w.webhookPath, {
            fileId:      id,
            fileName:    f.getName(),
            mimeType:    f.getMimeType(),
            folder:      w.name,
            createdTime: f.getDateCreated().toISOString(),
          });
        }
        seen.add(id);
      }
    }

    // Cap the persisted list to avoid hitting Apps Script property size limits.
    props.setProperty(seenKey, JSON.stringify(current.slice(-500)));
  }
}

// ── JESSE'S DEALS WATCHER ─────────────────────────────────────────────────────

/**
 * Fires on any edit to the Jesse's Deals spreadsheet.
 * Sends a lightweight signal to n8n; the workflow reads the sheet rows itself.
 */
function jesseTrigger() {
  notifyN8n('Jesse\'s Deals', JESSE_WEBHOOK, { source: 'sheet-change' });
}

// ── AUTH ──────────────────────────────────────────────────────────────────────

/**
 * Mints a Cloud Run identity token for N8N_BASE by impersonating
 * N8N_INVOKER_SA via the IAM Credentials API, using this script's own Google
 * identity (ScriptApp.getOAuthToken()) to authenticate the impersonation call.
 * Fetched fresh per notifyN8n() call — cheap, and avoids any caching/expiry
 * bookkeeping across separate trigger invocations.
 */
function getIdTokenForN8n_() {
  const url = 'https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/'
    + N8N_INVOKER_SA + ':generateIdToken';
  const res = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() },
    payload: JSON.stringify({ audience: N8N_BASE, includeEmail: true }),
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 200) {
    throw new Error('Failed to mint Cloud Run identity token (' + res.getResponseCode() + '): ' + res.getContentText());
  }
  return JSON.parse(res.getContentText()).token;
}

// ── SHARED HELPERS ─────────────────────────────────────────────────────────────

function notifyN8n(name, webhookPath, payload) {
  const url = N8N_BASE.replace(/\/+$/, '') + webhookPath;
  const idToken = getIdTokenForN8n_();
  const options = {
    method:           'post',
    contentType:      'application/json',
    headers:          { Authorization: 'Bearer ' + idToken },
    payload:          JSON.stringify(payload),
    muteHttpExceptions: true,
  };

  const maxAttempts = 6; // ~30 s of retries covers Cloud Run cold start
  for (let i = 1; i <= maxAttempts; i++) {
    const res  = UrlFetchApp.fetch(url, options);
    const code = res.getResponseCode();
    if (code >= 200 && code < 300) {
      console.log('[' + name + '] notified n8n OK (' + (payload.fileName || payload.source) + ')');
      return;
    }
    console.warn('[' + name + '] attempt ' + i + ' → HTTP ' + code + ', retrying…');
    Utilities.sleep(5000);
  }
  throw new Error('[' + name + '] n8n webhook failed after ' + maxAttempts + ' attempts: ' + url);
}

// ── TRIGGER INSTALLATION ──────────────────────────────────────────────────────

/**
 * Run ONCE (or re-run to reset). Installs:
 *  - checkFolders() every 5 min (time-based)
 *  - jesseTrigger() on edits to the Jesse's Deals spreadsheet
 */
function installTriggers() {
  // Remove any existing triggers we own to avoid duplicates.
  const ours = ['checkFolders', 'jesseTrigger'];
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (ours.includes(t.getHandlerFunction())) ScriptApp.deleteTrigger(t);
  });

  ScriptApp.newTrigger('checkFolders')
    .timeBased()
    .everyMinutes(CHECK_EVERY_MINUTES)
    .create();

  ScriptApp.newTrigger('jesseTrigger')
    .forSpreadsheet(JESSE_SHEET_ID)
    .onChange()
    .create();

  console.log('Installed: checkFolders every ' + CHECK_EVERY_MINUTES + ' min + jesseTrigger on sheet change.');
}
