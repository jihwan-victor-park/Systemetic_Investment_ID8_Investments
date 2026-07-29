/**
 * Google Apps Script — Michael Hughes (mphadvisorsinc@gmail.com) intro sync
 *
 * Runs against a Gmail account (script.google.com, not this repo's build).
 * Watches for any thread where Michael appears at all (from/to/cc, on any
 * message in the thread) — including us cc'ing him on an outbound email, or
 * forwarding him an existing thread ("hey Michael, meet John" — where the
 * forward itself only has Michael in the `to:` line, and John's address only
 * lives in the earlier messages of that same thread). Once Michael is linked
 * to a thread, every other participant across every message in it (minus
 * @id8investments.com addresses) is treated as introduced to him and POSTed
 * to the Attio webhook as a new prospect, then the thread gets labelled
 * "MH's Contacts" in Gmail. A second pass labels every thread involving
 * any already-known MH contact, so the Gmail label stays complete as new
 * messages arrive.
 *
 * Dedup / state lives in a Google Sheet (auto-created on first run, ID stored
 * in the SHEET_ID_PROP script property) so re-runs never re-send a contact
 * already pushed to Attio. Because several accounts can be scanning their own
 * mailboxes into that one shared sheet, checkMichaelEmails holds a script lock
 * for its whole body — see the comment there for why that's load-bearing.
 *
 * SETUP (multi-account)
 *  1. ONE Apps Script project, shared with every account whose mailbox should
 *     be scanned. Do NOT paste a separate copy per account: the copies drift
 *     apart, and a script lock only spans a single project, so separate copies
 *     can't serialize their writes to the shared tracking sheet.
 *  2. Then, in EACH account:
 *       a. Open the shared project and run checkMichaelEmails once manually.
 *          Authorization is per-user, and a trigger added by an account that
 *          never completed its own OAuth consent can fire and do nothing.
 *       b. Add its own time-based trigger. Installable triggers always run as
 *          whoever created them, and GmailApp only ever reads that account's
 *          own mailbox — so covering N inboxes genuinely needs N triggers.
 *          Watch the /u/N/ in the script.google.com URL: creating a trigger
 *          while the editor is signed in as the wrong account silently
 *          schedules it against the wrong mailbox. Symptom is every
 *          Time-Driven run logging "Scanned 0 Michael thread(s)" while manual
 *          Editor runs find plenty — hence the "Running as:" log line below.
 *       c. Stagger the accounts' schedules so they don't all contend on the lock.
 *  3. If Attio already has People records for known MH contacts, run
 *     seedExistingAttioContacts() once (needs an ATTIO_API_KEY script
 *     property) so they aren't re-sent as "new" prospects.
 *  4. linkSharedTrackingSheet() is ONLY for an account running a separate
 *     project copy. In the single-shared-project setup above, script
 *     properties — and therefore the tracking sheet and the Attio API key —
 *     are already shared by every account automatically.
 *  5. If checkMichaelEmails has been running but recent contacts are missing
 *     from Attio, run reconcileRecentSends(days) — it un-sticks any
 *     tracking-sheet row from the last N days that was falsely marked "sent"
 *     by the pre-fix webhook-failure bug, so the next run retries them.
 *
 * Tracking sheet: https://docs.google.com/spreadsheets/d/1Ybos-Kz39Sbml2SrjaUUylo15pbXlNMBVfPRkZGg4nM/edit
 */

// ===== CONFIG =====
const ATTIO_WEBHOOK_URL  = "https://hooks.attio.com/w/52d86a28-2b36-4fbb-bb91-af9b31cfe092/ae28d761-6c1a-4ed7-bdae-08e1e867f542";
const MICHAEL_EMAIL      = "mphadvisorsinc@gmail.com";
const YOUR_DOMAIN        = "@id8investments.com";
const GMAIL_LABEL        = "MH's Contacts";
const LOOKBACK_DAYS      = 7;
const SHEET_ID_PROP      = "sentEmailsSheetId";
const SHEET_NAME         = "Sent to Attio";
const LOCK_WAIT_MS       = 30000;


function checkMichaelEmails() {
  // Several accounts can run this against their own mailboxes while sharing
  // one tracking sheet, and the dedup is a read-then-write: loadSentEmails()
  // snapshots the sheet up front, but rows aren't appended until each webhook
  // succeeds. Two accounts overlapping would both see a contact as unsent,
  // both POST it, and both append a row — a duplicate prospect in Attio. A
  // script lock is the fix specifically because it serializes "regardless of
  // the identity of the user" (unlike a user lock, which is per-account and
  // would not help here at all). Skipping when the lock is busy is safe: the
  // next scheduled run picks the work up.
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(LOCK_WAIT_MS)) {
    Logger.log("Another account's run is already in progress — skipping this cycle.");
    return;
  }

  try {
    // Which account is this actually running as? A trigger created while the
    // editor was signed in as the wrong Google account searches that account's
    // (empty) mailbox instead, and the only visible symptom is a scan count of
    // 0 with no error. Log it so a Time-Driven run can be compared against a
    // manual Editor run at a glance.
    Logger.log(`Running as: ${Session.getEffectiveUser().getEmail()}`);

    const sheet = getOrCreateTrackingSheet();
    const sentEmails = loadSentEmails(sheet);

    const now = Date.now();
    const windowStartMs = now - LOOKBACK_DAYS * 24 * 60 * 60 * 1000;
    const michaelLower = MICHAEL_EMAIL.toLowerCase();

    let label = GmailApp.getUserLabelByName(GMAIL_LABEL);
    if (!label) label = GmailApp.createLabel(GMAIL_LABEL);

    const afterDate = Utilities.formatDate(new Date(windowStartMs), Session.getScriptTimeZone(), "yyyy/MM/dd");
    const query = `(from:${MICHAEL_EMAIL} OR to:${MICHAEL_EMAIL} OR cc:${MICHAEL_EMAIL}) after:${afterDate}`;
    // 50 was too tight — if Michael touches more than 50 threads in the lookback
    // window, older-but-still-recent threads fall outside the batch and their
    // contacts are never even evaluated. 300 comfortably covers real volume.
    const threads = GmailApp.search(query, 0, 300);

    let sent = 0;
    let skippedNoThirdParty = 0;

    // ── Pass 1: discover new contacts from Michael's threads ──────────────────
    for (const thread of threads) {
      try {
        const messages = thread.getMessages();
        const subjectForLog = thread.getFirstMessageSubject();

        const knownNames = new Map();
        for (const m of messages) {
          const fromMap = parseAddressEntries([m.getFrom()]);
          for (const [email, name] of fromMap) {
            if (name && !knownNames.has(email)) knownNames.set(email, name);
          }
        }

        // NOTE: we do NOT re-verify "is Michael actually in this thread" via our
        // own regex parser here. GmailApp.search() already guarantees it (that's
        // literally the query) — Gmail's own header indexing is more tolerant of
        // real-world header formats than a hand-rolled regex. A prior version of
        // this script re-derived Michael's presence with parseAddressEntries and
        // `continue`d the whole thread if that regex-based re-check came back
        // empty — so any header format the regex choked on (unusual display-name
        // quoting, multiple addresses on one line, etc.) silently dropped a real,
        // already-confirmed-by-Gmail thread with zero log trace. Trust the search.
        //
        // We still pool every participant across every message (not just the
        // matched message) so a forward like "hey Michael, meet John" — where
        // Michael only appears on one message and John only on an earlier one in
        // the same thread — still finds John.
        const threadAddresses = new Map(); // lowerEmail -> { name, message }
        for (const message of messages) {
          const addressMap = parseAddressEntries([message.getFrom(), message.getTo(), message.getCc()]);
          for (const [lowerEmail, headerName] of addressMap) {
            if (!threadAddresses.has(lowerEmail)) threadAddresses.set(lowerEmail, { name: headerName, message });
          }
        }

        if (!threadAddresses.has(michaelLower)) {
          // Gmail matched this thread on from/to/cc:michael, but our own header
          // parser didn't find him in any message — a real parser gap. Don't
          // skip silently; log it so a bad header format shows up instead of
          // vanishing.
          Logger.log(`WARNING: thread "${subjectForLog}" matched the Michael search but parseAddressEntries never found ${michaelLower} in any message header — check header formatting.`);
        }

        const thirdPartyAddrs = [...threadAddresses.keys()].filter(
          addr => addr !== michaelLower && !addr.endsWith(YOUR_DOMAIN.toLowerCase())
        );
        if (thirdPartyAddrs.length === 0) {
          skippedNoThirdParty++;
          continue;
        }

        thread.addLabel(label);

        for (const lowerEmail of thirdPartyAddrs) {
          if (sentEmails.has(lowerEmail)) continue;

          const info = threadAddresses.get(lowerEmail);
          const message = info.message;
          const name = knownNames.get(lowerEmail) || info.name || extractName(lowerEmail);

          const payload = {
            email:   lowerEmail,
            name:    name,
            subject: message.getSubject(),
            date:    message.getDate().toISOString(),
            michael: MICHAEL_EMAIL
          };

          try {
            const resp = UrlFetchApp.fetch(ATTIO_WEBHOOK_URL, {
              method:      "post",
              contentType: "application/json",
              payload:     JSON.stringify(payload),
              muteHttpExceptions: true
            });
            const code = resp.getResponseCode();
            if (code >= 200 && code < 300) {
              Logger.log(`Sent prospect: ${lowerEmail} as "${name}" (subject: "${message.getSubject()}")`);
              sentEmails.add(lowerEmail);
              sheet.appendRow([lowerEmail, name, new Date()]);
              sent++;
            } else {
              // Do NOT dedupe on failure — leaving it out of sentEmails means the
              // next run retries it instead of silently losing the contact forever.
              Logger.log(`Attio webhook rejected ${lowerEmail}: HTTP ${code} — ${resp.getContentText()}`);
            }
          } catch (e) {
            Logger.log(`Error sending to Attio for ${lowerEmail}: ${e}`);
          }
        }
      } catch (e) {
        // One malformed/oversized thread used to be able to throw here and abort
        // every remaining thread in the batch with no trace. Log and move on.
        Logger.log(`Error processing thread "${thread.getFirstMessageSubject()}": ${e}`);
      }
    }

    // ── Pass 2: label ALL threads involving any known MH contact ──────────────
    // sentEmails now includes both pre-existing and newly discovered contacts.
    // We search in batches of 10 to stay within Gmail query length limits.
    //
    // The `-label:` term is what keeps this affordable. Without it, every run
    // re-searched and re-labelled every thread of every known contact — with 26
    // contacts that's up to 300 redundant addLabel writes per run, and it grows
    // linearly with the contact list. Apps Script allows 20,000 Gmail
    // read/writes per day on consumer accounts (50,000 on Workspace), which a
    // 15-minute trigger would blow through on pass 2 alone. Excluding
    // already-labelled threads means steady-state runs do almost no work.
    const allContacts = [...sentEmails].filter(e => !e.endsWith(YOUR_DOMAIN.toLowerCase()));
    const BATCH = 10;
    let labelled = 0;

    for (let i = 0; i < allContacts.length; i += BATCH) {
      const batch = allContacts.slice(i, i + BATCH);
      const participants = batch.map(e => `(from:${e} OR to:${e} OR cc:${e})`).join(" OR ");
      const contactQuery = `-label:"${GMAIL_LABEL}" (${participants})`;
      const contactThreads = GmailApp.search(contactQuery, 0, 100);
      for (const thread of contactThreads) {
        thread.addLabel(label);
        labelled++;
      }
    }

    Logger.log(`Done. Scanned ${threads.length} Michael thread(s) (${skippedNoThirdParty} had no third party), sent ${sent} new prospect(s). Newly labelled ${labelled} thread(s) across ${allContacts.length} known MH contact(s).`);
  } finally {
    lock.releaseLock();
  }
}


function getOrCreateTrackingSheet() {
  const props = PropertiesService.getScriptProperties();
  let id = props.getProperty(SHEET_ID_PROP);
  let ss = null;

  if (id) {
    try { ss = SpreadsheetApp.openById(id); } catch (e) { ss = null; }
  }
  if (!ss) {
    ss = SpreadsheetApp.create("ID8 Webhook - Sent Prospects");
    props.setProperty(SHEET_ID_PROP, ss.getId());
    Logger.log(`Created tracking sheet: ${ss.getUrl()}`);
  }

  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.getSheets()[0];
    sheet.setName(SHEET_NAME);
    sheet.appendRow(["email", "name", "sent_at"]);
  }
  return sheet;
}

function loadSentEmails(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return new Set();
  const values = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
  return new Set(values.map(r => String(r[0]).trim().toLowerCase()).filter(Boolean));
}


// ===== ONE-TIME: run manually once, before the trigger starts firing. Pulls
// every existing People record's email out of Attio and writes it into the
// tracking sheet, so checkMichaelEmails never re-sends contacts already there.
// Needs a Script Property named ATTIO_API_KEY (Project Settings > Script
// Properties) - do not paste the key into code. In a single shared project one
// account running this covers everyone, since the sheet is shared.
function seedExistingAttioContacts() {
  const sheet = getOrCreateTrackingSheet();
  const existing = loadSentEmails(sheet);
  const attioRecords = fetchAllAttioPeople();
  let added = 0;

  for (const [lower, fullName] of attioRecords) {
    if (!existing.has(lower)) {
      sheet.appendRow([lower, fullName, new Date()]);
      existing.add(lower);
      added++;
    }
  }

  Logger.log(`Seeded ${added} existing Attio contact(s) into the tracking sheet.`);
}


// Returns a Map of lowercased email -> full_name for every People record
// currently in Attio. Shared by seedExistingAttioContacts (initial seed) and
// reconcileRecentSends (undoing false "sent" rows caused by a webhook that
// failed but got dedup'd as if it succeeded — see checkMichaelEmails).
function fetchAllAttioPeople() {
  const apiKey = PropertiesService.getScriptProperties().getProperty("ATTIO_API_KEY");
  if (!apiKey) throw new Error("Set an ATTIO_API_KEY script property first (Project Settings > Script Properties).");

  const result = new Map();
  let offset = 0;
  const limit = 500;

  while (true) {
    const resp = UrlFetchApp.fetch("https://api.attio.com/v2/objects/people/records/query", {
      method: "post",
      contentType: "application/json",
      headers: { Authorization: `Bearer ${apiKey}` },
      payload: JSON.stringify({ limit: limit, offset: offset }),
      muteHttpExceptions: true
    });

    const page = JSON.parse(resp.getContentText()).data;

    for (const record of page) {
      const emailEntries = (record.values && record.values.email_addresses) || [];
      const fullName = record.values && record.values.name && record.values.name[0]
        ? record.values.name[0].full_name : "";

      for (const e of emailEntries) {
        const lower = (e.email_address || "").trim().toLowerCase();
        if (lower) result.set(lower, fullName);
      }
    }

    if (page.length < limit) break;
    offset += limit;
  }

  return result;
}


// ===== Recovery helper. checkMichaelEmails used to have a bug where a failed
// Attio webhook call (muteHttpExceptions swallowed the HTTP error, and the code
// never checked the response code) still got marked as "sent" in the tracking
// sheet — so those contacts were silently blacklisted from ever being retried,
// even though Attio never actually received them. That bug is fixed above (the
// fetch is checked for a 2xx before dedup), but rows already written under the
// old bug are still stuck. This looks at every row sent in the last `days`
// days, checks whether Attio actually has that email, and deletes the row if
// not — so the next checkMichaelEmails() run picks it up and resends it for
// real. Needs the same ATTIO_API_KEY script property as seedExistingAttioContacts.
function reconcileRecentSends(days) {
  days = days || 3;
  const sheet = getOrCreateTrackingSheet();
  const attioEmails = fetchAllAttioPeople();
  const cutoff = new Date(Date.now() - days * 24 * 60 * 60 * 1000);

  const lastRow = sheet.getLastRow();
  if (lastRow < 2) { Logger.log("Tracking sheet is empty — nothing to reconcile."); return; }

  const rows = sheet.getRange(2, 1, lastRow - 1, 3).getValues(); // email, name, sent_at
  let removed = 0;

  // Walk bottom-up so deleteRow() doesn't shift the indices of rows we haven't checked yet.
  for (let i = rows.length - 1; i >= 0; i--) {
    const [email, name, sentAt] = rows[i];
    const lower = String(email).trim().toLowerCase();
    if (!lower || !(sentAt instanceof Date) || sentAt < cutoff) continue;

    if (!attioEmails.has(lower)) {
      Logger.log(`Un-sticking ${lower} (marked sent ${sentAt.toISOString()} but not found in Attio) — will be retried.`);
      sheet.deleteRow(i + 2); // +2: 1-indexed sheet rows, plus header row
      removed++;
    }
  }

  Logger.log(`Reconcile done. Checked rows from the last ${days} day(s), un-stuck ${removed} contact(s) that never actually reached Attio.`);
}


// ===== ONE-TIME: only needed by an account running its OWN SEPARATE copy of
// this project, to point it at the same tracking sheet as the first
// deployment. If every account shares one project (the recommended setup),
// script properties are already shared and this is unnecessary. Do not run it
// on the account that originally created the sheet.
function linkSharedTrackingSheet() {
  PropertiesService.getScriptProperties().setProperty(
    SHEET_ID_PROP,
    "1Ybos-Kz39Sbml2SrjaUUylo15pbXlNMBVfPRkZGg4nM"
  );
  Logger.log("Now pointing at the shared tracking sheet.");
}


function parseAddressEntries(rawStrings) {
  const map = new Map();
  for (const raw of rawStrings) {
    if (!raw) continue;
    const tokens = raw.match(/"[^"]*"\s*<[^>]+>|[^,]+/g) || [];
    for (const token of tokens) {
      const trimmed = token.trim();
      if (!trimmed) continue;
      const angle = trimmed.match(/^"?([^"<]*)"?\s*<([^>]+)>$/);
      let name = "";
      let email = "";
      if (angle) {
        name  = angle[1].trim();
        email = angle[2].trim();
      } else {
        const bare = trimmed.match(/[\w.+\-]+@[\w.\-]+\.[a-zA-Z]{2,}/);
        if (!bare) continue;
        email = bare[0];
      }
      const lower = email.toLowerCase();
      if (!map.has(lower) || (!map.get(lower) && name)) {
        map.set(lower, name);
      }
    }
  }
  return map;
}

function extractName(email) {
  const local = email.split("@")[0];
  return local
    .replace(/[._\-]+/g, " ")
    .replace(/\b\w/g, c => c.toUpperCase());
}


// ===== Installs the 15-minute trigger for THE ACCOUNT THAT RUNS IT, and only
// that account — a trigger belongs to whoever created it, and one account
// cannot see (or delete) triggers installed by another. The delete loop below
// likewise only clears this account's own triggers, so running this will NOT
// remove a stale trigger left behind by a different account; that has to be
// deleted from the account that made it.
function setupTrigger() {
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === "checkMichaelEmails") ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger("checkMichaelEmails").timeBased().everyMinutes(15).create();
}
