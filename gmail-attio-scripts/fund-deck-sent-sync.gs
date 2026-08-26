/**
 * Google Apps Script -- Fund deck "sent to" sync
 *
 * Recovered from the live Apps Script project 2026-08-26 during the backend
 * handover. It had NO copy in this repository, unlike its sibling
 * michael-hughes-intro-sync.gs -- committed here so the repo is the complete
 * record of what runs against ID8's Google Workspace.
 *
 * WHAT IT DOES
 * Scans this account's Sent mail for messages WE sent that contain the fund
 * deck's DocSend link, pulls every external recipient off them (To + Cc + Bcc --
 * Bcc is readable because these are our own sent messages), and POSTs each one
 * to an Attio webhook as a prospect. Dedup state is a tab in a control
 * spreadsheet, so a recipient is only ever pushed once.
 *
 * TRIGGER: setupFundDeckTrigger() installs checkFundDeckSent() daily at 08:00.
 * Like every installable Apps Script trigger it runs as, and is visible only
 * to, the account that created it.
 *
 * KNOWN ISSUES (documented, deliberately NOT changed during the handover --
 * this file is committed as a faithful copy of what is running today):
 *
 *  1. NO SCRIPT LOCK. michael-hughes-intro-sync.gs holds a
 *     LockService.getScriptLock() across its whole body, and its comment
 *     explains exactly why: the dedup is a read-then-write (loadSentEmails
 *     snapshots the sheet up front, rows are appended only as each webhook
 *     succeeds), so two accounts running concurrently both see a contact as
 *     unsent, both POST it, and both append a row -- a duplicate prospect in
 *     Attio. This script has the identical shape against a shared sheet and no
 *     lock. Safe only while exactly ONE account has the trigger installed.
 *
 *  2. DECK_LINK is a single hardcoded DocSend URL. Publish a new deck version
 *     -- a new DocSend link -- and this silently matches nothing. The log reads
 *     "Found 0 new recipient(s)", which is indistinguishable from a quiet week.
 *
 *  3. getTrackingSheet() throws if the tab is missing, where its sibling's
 *     getOrCreateTrackingSheet() self-heals. Renaming the tab breaks the job.
 *
 * WHAT IT GETS RIGHT (do not "simplify" these -- each is a fix for a real bug,
 * the same ones michael-hughes-intro-sync.gs carries):
 *  - the response code is checked before dedup, so a rejected webhook is
 *    retried next run instead of being silently blacklisted forever;
 *  - each thread is wrapped in its own try/catch, so one malformed thread
 *    cannot abort the rest of the page;
 *  - reconcileRecentFundDeckSends() un-sticks rows written under the old
 *    mark-as-sent-regardless bug.
 *
 * Control spreadsheet: https://docs.google.com/spreadsheets/d/1wTksRQnPuO47rZHial_fYwzT6okmjJ_7s0yDBtf00sc/edit
 * Script property required: ATTIO_API_KEY (used by fetchAllAttioPeople only).
 */

// ===== CONFIG =====
const FUND_DECK_WEBHOOK_URL =
  'https://hooks.attio.com/w/52d86a28-2b36-4fbb-bb91-af9b31cfe092/4e7f5336-c57b-4db3-96b4-cc7a49c1dbd7';
const YOUR_DOMAIN = '@id8investments.com';
const DECK_LINK = 'docsend.com/view/7hity73ucfz4qhra';
const BACKFILL_MONTHS = 6;
const ONGOING_LOOKBACK_DAYS = 14;
const SHEET_NAME = 'Fund Deck Sent';
const CONTROL_SHEET_ID = '1wTksRQnPuO47rZHial_fYwzT6okmjJ_7s0yDBtf00sc';
const DRY_RUN = false;

function backfillFundDeckSent() {
  const windowStartMs = Date.now() - BACKFILL_MONTHS * 30 * 24 * 60 * 60 * 1000;
  processSentDeckEmails(windowStartMs);
}

function checkFundDeckSent() {
  const windowStartMs =
    Date.now() - ONGOING_LOOKBACK_DAYS * 24 * 60 * 60 * 1000;
  processSentDeckEmails(windowStartMs);
}

function processSentDeckEmails(windowStartMs) {
  const sheet = getTrackingSheet();
  const sentEmails = loadSentEmails(sheet);
  const consideredThisRun = new Set();

  const afterDate = Utilities.formatDate(
    new Date(windowStartMs),
    Session.getScriptTimeZone(),
    'yyyy/MM/dd',
  );
  const query = `in:sent after:${afterDate}`;

  const pageSize = 100;
  let start = 0;
  let found = 0;
  let sent = 0;
  let rejected = 0;

  while (true) {
    const threads = GmailApp.search(query, start, pageSize);
    if (threads.length === 0) break;

    for (const thread of threads) {
      // A single bad/oversized thread used to be able to throw here and kill
      // every remaining thread in the page with zero trace. Log and move on.
      try {
        const messages = thread.getMessages();
        const recipients = new Map();

        for (const message of messages) {
          if (message.getDate().getTime() < windowStartMs) continue;

          // only process messages sent by us
          const fromMap = parseAddressEntries([message.getFrom()]);
          const isFromUs = [...fromMap.keys()].some((addr) =>
            addr.endsWith(YOUR_DOMAIN.toLowerCase()),
          );
          if (!isFromUs) continue;

          // only process messages that actually contain the deck link
          if (
            !message.getBody().toLowerCase().includes(DECK_LINK.toLowerCase())
          )
            continue;

          const addressMap = parseAddressEntries([
            message.getTo(),
            message.getCc(),
            message.getBcc(),
          ]);
          for (const [lowerEmail, headerName] of addressMap) {
            if (lowerEmail.endsWith(YOUR_DOMAIN.toLowerCase())) continue;
            if (
              !recipients.has(lowerEmail) ||
              (!recipients.get(lowerEmail) && headerName)
            ) {
              recipients.set(lowerEmail, headerName);
            }
          }
        }

        for (const [lowerEmail, headerName] of recipients) {
          if (sentEmails.has(lowerEmail)) continue;
          if (consideredThisRun.has(lowerEmail)) continue;
          consideredThisRun.add(lowerEmail);
          found++;

          const name = headerName || extractName(lowerEmail);

          if (DRY_RUN) {
            Logger.log(
              `[DRY RUN] Would send: ${lowerEmail} as "${name}" (thread: "${thread.getFirstMessageSubject()}")`,
            );
            continue;
          }

          const payload = {
            email: lowerEmail,
            name: name,
            subject: thread.getFirstMessageSubject(),
            date: new Date().toISOString(),
          };

          try {
            const resp = UrlFetchApp.fetch(FUND_DECK_WEBHOOK_URL, {
              method: 'post',
              contentType: 'application/json',
              payload: JSON.stringify(payload),
              muteHttpExceptions: true,
            });
            const code = resp.getResponseCode();
            if (code >= 200 && code < 300) {
              Logger.log(`Sent: ${lowerEmail} as "${name}"`);
              sentEmails.add(lowerEmail);
              sheet.appendRow([lowerEmail, name, new Date()]);
              sent++;
            } else {
              // Do NOT dedupe on failure — muteHttpExceptions means a 4xx/5xx
              // from Attio never throws, so without this check the old code
              // logged "Sent" and marked it done regardless of what Attio
              // actually said, permanently blacklisting it from retry.
              Logger.log(
                `Attio webhook rejected ${lowerEmail}: HTTP ${code} — ${resp.getContentText()}`,
              );
              rejected++;
            }
          } catch (e) {
            Logger.log(`Error sending ${lowerEmail}: ${e}`);
          }
        }
      } catch (e) {
        Logger.log(
          `Error processing thread "${thread.getFirstMessageSubject()}": ${e}`,
        );
      }
    }

    if (threads.length < pageSize) break;
    start += pageSize;
  }

  Logger.log(
    `Done. Found ${found} new recipient(s)${DRY_RUN ? ' (dry run - nothing sent)' : `, sent ${sent}, ${rejected} rejected by Attio`}.`,
  );
}

function getTrackingSheet() {
  const ss = SpreadsheetApp.openById(CONTROL_SHEET_ID);
  const sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet)
    throw new Error(`Tab "${SHEET_NAME}" not found in control spreadsheet.`);
  return sheet;
}

function loadSentEmails(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return new Set();
  const values = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
  return new Set(
    values.map((r) => String(r[0]).trim().toLowerCase()).filter(Boolean),
  );
}

// Returns a Map of lowercased email -> full_name for every People record
// currently in Attio. Needs a Script Property named ATTIO_API_KEY (Project
// Settings > Script Properties) — do not paste the key into code.
function fetchAllAttioPeople() {
  const apiKey =
    PropertiesService.getScriptProperties().getProperty('ATTIO_API_KEY');
  if (!apiKey)
    throw new Error(
      'Set an ATTIO_API_KEY script property first (Project Settings > Script Properties).',
    );

  const result = new Map();
  let offset = 0;
  const limit = 500;

  while (true) {
    const resp = UrlFetchApp.fetch(
      'https://api.attio.com/v2/objects/people/records/query',
      {
        method: 'post',
        contentType: 'application/json',
        headers: { Authorization: `Bearer ${apiKey}` },
        payload: JSON.stringify({ limit: limit, offset: offset }),
        muteHttpExceptions: true,
      },
    );

    const page = JSON.parse(resp.getContentText()).data;

    for (const record of page) {
      const emailEntries =
        (record.values && record.values.email_addresses) || [];
      const fullName =
        record.values && record.values.name && record.values.name[0]
          ? record.values.name[0].full_name
          : '';

      for (const e of emailEntries) {
        const lower = (e.email_address || '').trim().toLowerCase();
        if (lower) result.set(lower, fullName);
      }
    }

    if (page.length < limit) break;
    offset += limit;
  }

  return result;
}

// ===== RUN THIS NOW to fix the last few days: the webhook call above used to
// mark a recipient "sent" the moment UrlFetchApp.fetch() returned, without
// checking whether Attio actually accepted it (muteHttpExceptions swallows
// HTTP errors instead of throwing). That's fixed above, but tracking-sheet
// rows written under the old bug are still stuck marked "sent" even though
// Attio never got them. This checks every row from the last `days` days
// against Attio's real People records and deletes the row if it's not
// actually there — so the next checkFundDeckSent() run resends it for real.
function reconcileRecentFundDeckSends(days) {
  days = days || 14;
  const sheet = getTrackingSheet();
  const attioEmails = fetchAllAttioPeople();
  const cutoff = new Date(Date.now() - days * 24 * 60 * 60 * 1000);

  const lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    Logger.log('Tracking sheet is empty — nothing to reconcile.');
    return;
  }

  const rows = sheet.getRange(2, 1, lastRow - 1, 3).getValues(); // email, name, sent_at
  let removed = 0;

  // Walk bottom-up so deleteRow() doesn't shift indices of rows not yet checked.
  for (let i = rows.length - 1; i >= 0; i--) {
    const [email, name, sentAt] = rows[i];
    const lower = String(email).trim().toLowerCase();
    if (!lower || !(sentAt instanceof Date) || sentAt < cutoff) continue;

    if (!attioEmails.has(lower)) {
      Logger.log(
        `Un-sticking ${lower} (marked sent ${sentAt.toISOString()} but not found in Attio) — will be retried.`,
      );
      sheet.deleteRow(i + 2); // +2: 1-indexed sheet rows, plus header row
      removed++;
    }
  }

  Logger.log(
    `Reconcile done. Checked rows from the last ${days} day(s), un-stuck ${removed} contact(s) that never actually reached Attio.`,
  );
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
      let name = '';
      let email = '';
      if (angle) {
        name = angle[1].trim();
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
  const local = email.split('@')[0];
  return local
    .replace(/[._\-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function setupFundDeckTrigger() {
  ScriptApp.getProjectTriggers().forEach((t) => {
    if (t.getHandlerFunction() === 'checkFundDeckSent')
      ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('checkFundDeckSent')
    .timeBased()
    .everyDays(1)
    .atHour(8)
    .create();
}
