"""Transform the LIVE exported n8n workflow into a corrected one.

Run:
    python3 n8n-cloudrun/build_corrected_workflow.py \
        "../inherited-workflows/ID8 PB-Attio (2).json" \
        n8n-cloudrun/ID8_PB-Attio_corrected.json

Why a script and not a hand-edited JSON file: the export is 44 KB of generated
JSON with node ids, positions, credential ids and webhook ids that must survive
untouched so the corrected version IMPORTS OVER the live workflow cleanly rather
than arriving as a stranger. A script makes every change auditable and lets the
transform be re-applied if the live workflow is exported again.

WHAT THIS FIXES (all four are defects in the live workflow, not preferences)

1. The three intake branches build their own email HTML in Code nodes.
   pipeline/app.py's _run_pipeline_worker already returns `email_html`,
   `email_text` and `email_subject`, and its own comment says n8n "now just uses
   {{ $json.email_html }}" -- which never happened. The consequence is not
   cosmetic: the backend email renders fit scores, a separate "already in Attio
   -- updated" section for re-seen deals, and a filtered-deals section. The four
   n8n templates render none of that, because they were written before those
   fields existed and then drifted. Dropping the Code nodes removes ~500 lines
   of duplicated JavaScript and three copies of the same bug.

2. Three of the four templates load the logo from
   https://pb-attio-pipeline.onrender.com/logo -- the DEAD Render host this
   service ran on before Cloud Run. That is a broken image in every live
   PitchBook, Watchlist and Top 10 email. Deleting the templates deletes the
   problem; the backend's own email references the Cloud Run /logo route.

3. `Code in JavaScript2` (the Jesse digest) has NO outgoing connection, so the
   digest email is computed and thrown away every single day. The repo's own
   abandoned webhook variant (ID8_PB-Attio_webhook.json) wires
   Code in JavaScript2 -> If3 -> Send a message2, which is the intended shape;
   this restores it.

4. `Send a message4` (the Error Trigger's email) has parameters {"options": {}}
   -- no recipient, no subject, no body. The error path is connected and
   completely inert, so a failed intake run notifies nobody.

WHAT THIS DELIBERATELY DOES NOT CHANGE

* Recipients stay literal in the Gmail nodes. n8n Variables ($vars) need a
  licensed n8n; this is a self-hosted Cloud Run deployment and may well be
  community edition. A literal address in an n8n node is also exactly where a
  sender/recipient belongs -- the requirement is that it not be hardcoded in the
  Python backend, and it is not.
* Credential references, node ids, positions and webhook ids are untouched.
* The per-row Jesse HTTP loop stays a per-row loop. Batching it needs a new
  backend endpoint, which is a code change, not a workflow change.
* The Drive triggers keep everyMinute polling.
"""
import json
import sys

# ── The skip guard ──────────────────────────────────────────────────────────
# The old Code nodes returned {skip: true} when deals.length === 0, and the IF
# checked `$json.skip != "true"`. Reading the backend response directly needs
# BOTH halves of that guard, because the two failure modes are different:
#
#   deals.length > 0   preserves "a run that surfaced nothing sends no email"
#                      (the backend builds email_html unconditionally, including
#                      for a zero-deal run, so this is not implied by the next
#                      condition).
#   email_html notEmpty guards the TIMEOUT case: if a Stage 1 batch runs past
#                      _start_pipeline's ~1700s budget the response is the
#                      PARTIAL state, whose status is "screening" and which has
#                      no email_html yet. Sending then would mail an empty body.
#
# `?.` plus `|| 0` because a 5xx/error response has no `deals` key at all.
SKIP_GUARD = {
    "options": {
        "caseSensitive": True,
        "leftValue": "",
        "typeValidation": "loose",
        "version": 3,
    },
    "conditions": [
        {
            "id": "guard-has-deals",
            "leftValue": "={{ $json.deals?.length || 0 }}",
            "rightValue": 0,
            "operator": {"type": "number", "operation": "gt"},
        },
        {
            "id": "guard-has-email",
            "leftValue": "={{ $json.email_html }}",
            "rightValue": "",
            "operator": {"type": "string", "operation": "notEmpty", "singleValue": True},
        },
    ],
    "combinator": "and",
}

# Which HTTP Request node each intake branch's IF and Gmail node should read
# from, now that the Code node between them is gone.
INTAKE_BRANCHES = {
    "If": ("HTTP Request", "Send a message", "Code in JavaScript"),
    "If1": ("HTTP Request1", "Send a message1", "Code in JavaScript1"),
    "If4": ("HTTP Request3", "Send a message3", "Code in JavaScript3"),
}

ERROR_SUBJECT = (
    "=ID8 pipeline FAILED - {{ $json.workflow?.name || 'unknown workflow' }}"
    " ({{ $json.execution?.lastNodeExecuted || 'unknown node' }})"
)

# Plain-text-ish HTML: this is an alert, not a report. Every field is guarded
# with `?.`/`||` because the Error Trigger payload shape varies by failure mode
# (a node error, a trigger error and a timeout do not all populate the same
# keys), and an expression that throws inside the error handler would leave the
# failure silent all over again -- the exact bug being fixed.
ERROR_MESSAGE = """=<h2 style="font-family:Helvetica,Arial,sans-serif;">ID8 pipeline execution failed</h2>
<table cellpadding="4" style="font-family:Helvetica,Arial,sans-serif;font-size:14px;">
<tr><td><b>Workflow</b></td><td>{{ $json.workflow?.name || 'unknown' }}</td></tr>
<tr><td><b>Failed node</b></td><td>{{ $json.execution?.lastNodeExecuted || 'unknown' }}</td></tr>
<tr><td><b>Execution</b></td><td>{{ $json.execution?.id || 'n/a' }}</td></tr>
<tr><td><b>Mode</b></td><td>{{ $json.execution?.mode || 'n/a' }}</td></tr>
<tr><td><b>Time</b></td><td>{{ $now.toISO() }}</td></tr>
</table>
<p style="font-family:Helvetica,Arial,sans-serif;font-size:14px;"><b>Error</b><br>
<code>{{ $json.execution?.error?.message || 'no message' }}</code></p>
<p style="font-family:Helvetica,Arial,sans-serif;font-size:13px;">
<a href="{{ $json.execution?.url || '#' }}">Open this execution in n8n</a></p>
<p style="font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#888;">
A Drive drop may not have reached Attio. Check the execution before re-dropping
the file &mdash; /process is not idempotent for Stage 1 cost, though Attio
dedupes the deal itself on company+series.</p>"""

# The Jesse digest currently renders "None" when nothing new arrived, so
# reconnecting it as-is would mail a daily no-op. The repo's own webhook variant
# puts an IF between the Code node and Gmail for exactly this reason. Deleting
# the "If3" node and reconnecting Code in JavaScript2 -> Send a message2
# restores the every-day behaviour if that is preferred.
JESSE_GUARD = {
    "options": {
        "caseSensitive": True,
        "leftValue": "",
        "typeValidation": "loose",
        "version": 3,
    },
    "conditions": [
        {
            "id": "jesse-has-new-names",
            "leftValue": "={{ $json.newCount || 0 }}",
            "rightValue": 0,
            "operator": {"type": "number", "operation": "gt"},
        }
    ],
    "combinator": "and",
}


def transform(wf):
    nodes = {n["name"]: n for n in wf["nodes"]}
    conns = wf["connections"]
    notes = []

    def connect(src, dst):
        conns[src] = {"main": [[{"node": dst, "type": "main", "index": 0}]]}

    # ── 1. Intake branches: drop the Code node, read the backend's email ─────
    for if_name, (http_name, gmail_name, code_name) in INTAKE_BRANCHES.items():
        nodes[if_name]["parameters"]["conditions"] = SKIP_GUARD

        gmail = nodes[gmail_name]
        gmail["parameters"]["subject"] = f"={{{{ $('{http_name}').item.json.email_subject }}}}"
        gmail["parameters"]["message"] = f"={{{{ $('{http_name}').item.json.email_html }}}}"
        # Explicit rather than relying on the node default -- MIGRATION_RUNBOOK
        # Phase 3 calls this out ("Set the email type to HTML, not plain text")
        # and an HTML body delivered as text/plain is unreadable.
        gmail["parameters"]["emailType"] = "html"

        connect(http_name, if_name)          # HTTP -> IF, skipping the Code node
        conns.pop(code_name, None)
        del nodes[code_name]
        notes.append(f"{code_name}: removed; {gmail_name} now reads {http_name}'s email_html")

    # ── 2. Error handler: give it a recipient, a subject and a body ──────────
    # Same recipient as the Watchlist branch (the single-owner alert address).
    # Everything else on this node -- credential, id, position -- is untouched.
    err = nodes["Send a message4"]
    err["parameters"] = {
        "sendTo": "oscar@id8investments.com",
        "subject": ERROR_SUBJECT,
        "message": ERROR_MESSAGE,
        "emailType": "html",
        "options": {},
    }
    notes.append("Send a message4: configured (was {'options': {}} -- inert)")

    # ── 3. Jesse digest: reconnect the orphaned email, behind a new guard ────
    jesse_gmail = nodes["Send a message2"]
    jesse_gmail["parameters"]["emailType"] = "html"

    code2 = nodes["Code in JavaScript2"]
    js = code2["parameters"]["jsCode"]
    # Expose the count the guard reads. The digest already computes newNames;
    # this only surfaces its length alongside the html/subject it already emits.
    assert "return [{ json: { html, subject } }];" in js, "Code in JavaScript2 shape changed"
    js = js.replace(
        "return [{ json: { html, subject } }];",
        "return [{ json: { html, subject, newCount: newNames.length } }];",
    )
    code2["parameters"]["jsCode"] = js

    wf["nodes"].append({
        "parameters": {
            "conditions": JESSE_GUARD,
            "looseTypeValidation": True,
            "options": {},
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.3,
        "position": [2336, 1104],
        "id": "b1f3a0c2-7d55-4e21-9a08-6c2f4e1d9a37",
        "name": "If3",
    })
    connect("Code in JavaScript2", "If3")
    connect("If3", "Send a message2")
    notes.append("Code in JavaScript2 -> If3 -> Send a message2: reconnected (digest was orphaned)")

    # ── 4. Remove the dead static counter ───────────────────────────────────
    # staticData.changeCount is incremented and never read by any node or
    # expression in this workflow. Removing it also removes the one piece of
    # workflow-static state, which n8n resets on workflow edit/reactivation.
    if "Code in JavaScript4" in nodes:
        downstream = conns.pop("Code in JavaScript4", None)
        target = downstream["main"][0][0]["node"] if downstream else "If2"
        connect("Get row(s) in sheet", target)
        wf["nodes"] = [n for n in wf["nodes"] if n["name"] != "Code in JavaScript4"]
        notes.append(f"Code in JavaScript4: removed (dead counter); Get row(s) in sheet -> {target}")

    wf["nodes"] = [n for n in wf["nodes"] if n["name"] in nodes or n["name"] == "If3"]
    return wf, notes


def main():
    src, dst = sys.argv[1], sys.argv[2]
    with open(src) as f:
        wf = json.load(f)

    before = len(wf["nodes"])
    wf, notes = transform(wf)

    # Import as INACTIVE. An import that arrives already active would start
    # polling three Drive folders every minute the moment it lands, before
    # anyone has looked at it.
    wf["active"] = False

    with open(dst, "w") as f:
        json.dump(wf, f, indent=2)
        f.write("\n")

    print(f"{src}\n  -> {dst}")
    print(f"nodes: {before} -> {len(wf['nodes'])}   active: True -> False")
    for n in notes:
        print(f"  * {n}")


if __name__ == "__main__":
    main()
