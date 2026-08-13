import { NextResponse } from 'next/server';

// The public front door for Attio's native "deal created" workflow (Oscar,
// 2026-08-13: "for Attio to the Hub make it so that there's a workflow in Attio
// (native) it triggers a http request that will deduce the new deal created and
// check if its on hub and add it").
//
// Server-to-server only: excluded from the session-gate middleware (see
// src/middleware.js) so Attio can call it with no browser session, guarded
// instead by a shared secret header -- the same pattern
// /api/admin-market-map/[id] already uses, and the same pattern
// cc-attio-sync's own Attio webhooks use (X-Webhook-Secret).
//
// Why the work happens in the pipeline service rather than here: hub-next has
// no Attio API credential of its own by design (see project memory
// reference_hub_next_no_live_pitchbook_attio), and the import logic --
// re-reading the deal, resolving its domain off the linked Company record,
// upserting by the shared company slug -- already exists there and is shared
// with the bulk import. hub-next contributes the one thing pipeline can't: a
// publicly reachable URL. This org's policy blocks making a Cloud Run service
// public (see cc-attio-sync/gateway/openapi.yaml), so proxying through the app
// that's already public beats standing up a second API Gateway.
export async function POST(request) {
  const configured = process.env.ATTIO_WEBHOOK_SECRET;
  if (!configured) {
    return NextResponse.json({ error: 'attio-webhook-secret-not-configured' }, { status: 500 });
  }
  // Both spellings accepted: Attio's action UI is a free-text header field and
  // the two are trivially confusable, so matching only one turns a typo into a
  // silent 401 on every deal creation.
  const provided = request.headers.get('x-attio-webhook-secret') || request.headers.get('x-webhook-secret');
  if (provided !== configured) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  if (!process.env.PIPELINE_BASE_URL) {
    return NextResponse.json({ error: 'PIPELINE_BASE_URL is not configured' }, { status: 500 });
  }

  // Forwarded verbatim rather than reshaped here -- the pipeline route owns
  // which body shapes it accepts (_extract_attio_record_id), so a mis-wired
  // Attio reference chip produces ONE error message from ONE place instead of
  // two layers each guessing at the payload.
  const body = await request.text();
  const headers = { 'Content-Type': 'application/json' };
  if (process.env.PIPELINE_INTERNAL_SECRET) headers['X-Internal-Secret'] = process.env.PIPELINE_INTERNAL_SECRET;

  let res;
  try {
    res = await fetch(`${process.env.PIPELINE_BASE_URL}/attio-deal-created`, {
      method: 'POST',
      headers,
      body: body || '{}',
    });
  } catch (e) {
    console.error('POST /api/attio/deal-created: pipeline request failed:', e);
    return NextResponse.json({ error: 'pipeline-unreachable' }, { status: 502 });
  }
  const data = await res.json().catch(() => ({ error: 'invalid response from pipeline service' }));
  return NextResponse.json(data, { status: res.status });
}
