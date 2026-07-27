> **⚠️ Abandoned (Jul 2026):** This was tried and reverted after repeated IAM
> token / webhook-path drift issues in production. `drive-watcher.gs` is no
> longer deployed. Production now uses the native Google Drive/Sheets Trigger
> polling nodes this doc replaces, which requires n8n to run `--min-instances=1`
> (see `deploy.sh`'s header comment for the full history). Kept here for
> reference only — don't follow these steps to "fix" the cost, it's the reason
> n8n has to be more expensive, not less.

# Converting the workflow from polling → webhook (so Cloud Run can stay free)

Goal: replace the two **Google Drive Trigger** nodes (which poll every minute and
force n8n to stay always-on) with **Webhook** nodes that fire only when a file
actually drops. A free Google Apps Script (`drive-watcher.gs`) does the watching.

Result: n8n runs with `--min-instances=0` and wakes only on real events
(~weekly), staying within the Cloud Run free tier.

---

## Part 1 — Change the workflow in n8n

Do this in the n8n editor (keeps your credentials intact). Repeat for both flows.

### Flow 1: PitchBook deals

1. **Delete** the `Google Drive Trigger` node.
2. Add a **Webhook** node in its place:
   - HTTP Method: `POST`
   - Path: `pitchbook-drop`
   - Respond: **Immediately** (Apps Script gets a fast 200; n8n keeps processing).
3. Open the **Download file** node and change the File ID expression from
   `={{ $json.id }}` to:
   ```
   ={{ $json.body.fileId }}
   ```
4. Connect **Webhook → Download file** (same as before).

### Flow 2: Watchlist

Same steps, but set the Webhook **Path** to `watchlist-drop`, and wire it to
`Download file1`.

### Get the URLs

After saving and **activating** the workflow, each Webhook node shows its
**Production URL**, e.g.:

```
https://n8n-xxxxx.us-central1.run.app/webhook/pitchbook-drop
https://n8n-xxxxx.us-central1.run.app/webhook/watchlist-drop
```

> Use the **Production** URL (not the Test URL). Test URLs only work while the
> editor's "Listen for test event" is active.

---

## Part 2 — Set up the free watcher

1. Open <https://script.google.com> → **New project**.
2. Paste in `drive-watcher.gs`.
3. Set each `webhookUrl` to the Production URLs from Part 1.
4. Run `installTrigger()` once. Approve the Drive permission prompt.
   - Run it as the Google account that owns the Drive folders (so it can read them).
5. That's it — it checks every 5 minutes and pings n8n only on new files.

To test: drop a file into the PitchBook folder, wait up to 5 min, and watch the
n8n **Executions** tab. The first wake-up after idle takes ~20–40s (Cloud Run
cold start) — the script retries through that automatically.

---

## Why this stays free

| Piece | Cost |
|---|---|
| Apps Script time trigger (the "polling") | Free (Google quota) |
| n8n on Cloud Run, `min-instances=0` | Free tier — only billed while actually running (~weekly, seconds at a time) |
| Postgres | Free if Neon; ~£8/mo if Cloud SQL |

The expensive thing (a 24/7 instance) is gone: the only always-running component
is Apps Script, which Google runs for free.

---

## Gotchas

- **Use `--min-instances=0`** on the Cloud Run deploy (the scale-to-zero value),
  not `1`. That's the difference between free and ~$50/mo.
- **Cold-start latency:** first event after idle waits for n8n to boot. Fine for
  weekly drops; the watcher retries so nothing is lost.
- **Webhook must be registered:** the workflow has to be **active** for the
  Production webhook URL to respond. If you deactivate it, events are dropped.
- **First run is a baseline:** `drive-watcher.gs` records existing files on its
  first run and won't replay them — only files added afterward trigger n8n.
- **Keep the encryption key** (`N8N_ENCRYPTION_KEY`) constant, as before.
