/**
 * Google Apps Script — Michael Hughes (mphadvisorsinc@gmail.com) intro sync
 *
 * Bound to Oscar's Gmail account (script.google.com, not this repo's build).
 * Watches for any thread where Michael appears at all (from/to/cc, on any
 * message in the thread) — including us cc'ing him on an outbound email, or
 * forwarding him an existing thread ("hey Michael, meet John" — where the
 * forward itself only has Michael in the `to:` line, and John's address only
 * lives in the earlier messages of that same thread). Once Michael is linked
 * to a thread, every other participant across every message in it (minus
 * @id8investments.com addresses) is treated as introduced to him and POSTed
 * to the Attio webhook as a new prospect, then the thread gets labelled
 * "MH's Contacts" in Gmail. A second pass re-labels every thread involving
 * any already-known MH contact, so the Gmail label stays complete as new
 * messages arrive.
 *
 * Dedup / state lives in a Google Sheet (auto-created on first run, ID stored
 * in the SHEET_ID_PROP script property) so re-runs never re-send a contact
 * already pushed to Attio.
 *
 * SETUP
 *  1. script.google.com → New project → paste this file as Code.gs.
 *  2. Run setupTrigger() once to install the 15-min checkMichaelEmails trigger.
 *  3. If Attio already has existing People records for known MH contacts,
 *     run seedExistingAttioContacts() once first (needs an ATTIO_API_KEY
 *     script property) so they aren't re-sent as "new" prospects.
 *  4. On a second Google account that should share dedup state with the
 *     first, run linkSharedTrackingSheet() once (do NOT run it on the
 *     account that originally created the sheet).
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


function checkMichaelEmails() {
  const sheet = getOrCreateTrackingSheet();
  const sentEmails = loadSentEmails(sheet);

  const now = Date.now();
  const windowStartMs = now - LOOKBACK_DAYS * 24 * 60 * 60 * 1000;
  const michaelLower = MICHAEL_EMAIL.toLowerCase();

  let label = GmailApp.getUserLabelByName(GMAIL_LABEL);
  if (!label) label = GmailApp.createLabel(GMAIL_LABEL);

  const afterDate = Utilities.formatDate(new Date(windowStartMs), Session.getScriptTimeZone(), "yyyy/MM/dd");
  const query = `(from:${MICHAEL_EMAIL} OR to:${MICHAEL_EMAIL} OR cc:${MICHAEL_EMAIL}) after:${afterDate}`;
  const threads = GmailApp.search(query, 0, 50);

  let sent = 0;

  // ── Pass 1: discover new contacts from Michael's threads ──────────────────
  for (const thread of threads) {
    const messages = thread.getMessages();

    const knownNames = new Map();
    for (const m of messages) {
      const fromMap = parseAddressEntries([m.getFrom()]);
      for (const [email, name] of fromMap) {
        if (name && !knownNames.has(email)) knownNames.set(email, name);
      }
    }

    // Does Michael appear anywhere in this thread at all? A forward ("hey
    // Michael, meet John") often lands Michael as a plain `to:` on a message
    // whose own From/To/Cc don't repeat John's address — John only shows up
    // in the earlier messages of the same thread. So detection is thread-wide:
    // if Michael touched the thread anywhere, pool every participant across
    // every message to find who else was on it.
    let michaelInThread = false;
    for (const m of messages) {
      const addrs = parseAddressEntries([m.getFrom(), m.getTo(), m.getCc()]);
      if (addrs.has(michaelLower)) { michaelInThread = true; break; }
    }
    if (!michaelInThread) continue;

    const threadAddresses = new Map(); // lowerEmail -> { name, message }
    for (const message of messages) {
      const addressMap = parseAddressEntries([message.getFrom(), message.getTo(), message.getCc()]);
      for (const [lowerEmail, headerName] of addressMap) {
        if (!threadAddresses.has(lowerEmail)) threadAddresses.set(lowerEmail, { name: headerName, message });
      }
    }

    const hasThirdParty = [...threadAddresses.keys()].some(
      addr => addr !== michaelLower && !addr.endsWith(YOUR_DOMAIN.toLowerCase())
    );
    if (!hasThirdParty) continue;

    thread.addLabel(label);

    for (const [lowerEmail, info] of threadAddresses) {
      if (lowerEmail === michaelLower) continue;
      if (lowerEmail.endsWith(YOUR_DOMAIN.toLowerCase())) continue;
      if (sentEmails.has(lowerEmail)) continue;

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
        UrlFetchApp.fetch(ATTIO_WEBHOOK_URL, {
          method:      "post",
          contentType: "application/json",
          payload:     JSON.stringify(payload),
          muteHttpExceptions: true
        });
        Logger.log(`Sent prospect: ${lowerEmail} as "${name}" (subject: "${message.getSubject()}")`);
        sentEmails.add(lowerEmail);
        sheet.appendRow([lowerEmail, name, new Date()]);
        sent++;
      } catch (e) {
        Logger.log(`Error sending to Attio for ${lowerEmail}: ${e}`);
      }
    }
  }

  // ── Pass 2: label ALL threads involving any known MH contact ──────────────
  // sentEmails now includes both pre-existing and newly discovered contacts.
  // We search in batches of 10 to stay within Gmail query length limits.
  const allContacts = [...sentEmails].filter(e => !e.endsWith(YOUR_DOMAIN.toLowerCase()));
  const BATCH = 10;

  for (let i = 0; i < allContacts.length; i += BATCH) {
    const batch = allContacts.slice(i, i + BATCH);
    const contactQuery = batch.map(e => `(from:${e} OR to:${e} OR cc:${e})`).join(" OR ");
    const contactThreads = GmailApp.search(contactQuery, 0, 100);
    for (const thread of contactThreads) {
      thread.addLabel(label);
    }
  }

  Logger.log(`Done. Scanned ${threads.length} Michael thread(s), sent ${sent} new prospect(s). Labelled threads for ${allContacts.length} known MH contact(s).`);
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


// ===== ONE-TIME: run manually once per Google account, before the trigger
// starts firing. Pulls every existing People record's email out of Attio and
// writes it into the tracking sheet, so checkMichaelEmails never re-sends
// contacts already there. Needs a Script Property named ATTIO_API_KEY
// (Project Settings > Script Properties) - do not paste the key into code.
function seedExistingAttioContacts() {
  const apiKey = PropertiesService.getScriptProperties().getProperty("ATTIO_API_KEY");
  if (!apiKey) throw new Error("Set an ATTIO_API_KEY script property first (Project Settings > Script Properties).");

  const sheet = getOrCreateTrackingSheet();
  const existing = loadSentEmails(sheet);

  let offset = 0;
  const limit = 500;
  let added = 0;

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
        if (lower && !existing.has(lower)) {
          sheet.appendRow([lower, fullName, new Date()]);
          existing.add(lower);
          added++;
        }
      }
    }

    if (page.length < limit) break;
    offset += limit;
  }

  Logger.log(`Seeded ${added} existing Attio contact(s) into the tracking sheet.`);
}


// ===== ONE-TIME: run manually once, ONLY on a second/additional Google
// account that should share the same tracking sheet as the first deployment.
// Do not run this on the account that originally created the sheet.
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


function setupTrigger() {
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === "checkMichaelEmails") ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger("checkMichaelEmails").timeBased().everyMinutes(15).create();
}
