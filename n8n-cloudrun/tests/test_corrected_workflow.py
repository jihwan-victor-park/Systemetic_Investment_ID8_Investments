"""Structural guards on the corrected n8n workflow (ID8_PB-Attio_corrected.json).

An n8n workflow is data, and every defect this file checks for was really
present in the LIVE exported workflow -- an orphaned node, an unconfigured Gmail
node, an expression pointing at a node that no longer exists. n8n reports none
of these at import time: it accepts the JSON, activates, and then silently does
nothing on the broken path. That is exactly how the Jesse digest went missing.

These tests run against the COMMITTED JSON rather than by re-running
build_corrected_workflow.py, because the script's input lives outside the repo
(inherited-workflows/) and the committed artifact is what would actually be
imported into n8n.
"""
import json
import re
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parent.parent / "ID8_PB-Attio_corrected.json"

# The four backend endpoints this workflow is allowed to call. Pinned so a
# future edit cannot quietly retarget a branch at a different route (or at a
# different host) without this test failing.
EXPECTED_ENDPOINTS = {
    "https://id8-137750788450.us-east4.run.app/process",
    "https://id8-137750788450.us-east4.run.app/process-watchlist",
    "https://id8-137750788450.us-east4.run.app/process-top10",
    "https://id8-137750788450.us-east4.run.app/process-jesse",
}


@pytest.fixture(scope="module")
def wf():
    return json.loads(WORKFLOW.read_text())


@pytest.fixture(scope="module")
def names(wf):
    return {n["name"] for n in wf["nodes"]}


def _edges(wf):
    for src, out in wf["connections"].items():
        for branches in out.values():
            for branch in branches or []:
                for conn in branch or []:
                    yield src, conn["node"]


class TestGraphIntegrity:
    def test_every_connection_endpoint_is_a_real_node(self, wf, names):
        bad = [(s, d) for s, d in _edges(wf) if s not in names or d not in names]
        assert bad == [], f"connections referencing missing nodes: {bad}"

    def test_no_orphaned_nodes(self, wf, names):
        """The live workflow's `Send a message2` had no inbound edge, so the
        Jesse daily digest was computed and discarded every day. Any node that
        is not a trigger must be reachable."""
        inbound = {d for _s, d in _edges(wf)}
        triggers = {n["name"] for n in wf["nodes"] if "Trigger" in n["type"]}
        orphans = sorted(names - inbound - triggers)
        assert orphans == [], f"unreachable nodes: {orphans}"

    def test_every_node_expression_references_a_real_node(self, wf, names):
        """`$('Code in JavaScript').item.json.subject` still resolving after the
        Code node was deleted would be an import-time-clean, run-time-fatal
        workflow."""
        referenced = set(re.findall(r"\$\('([^']+)'\)", json.dumps(wf)))
        assert referenced <= names, f"expressions reference missing nodes: {sorted(referenced - names)}"

    def test_imports_inactive(self, wf):
        """Three Drive triggers poll every minute. An import that arrives active
        starts processing drops before anyone has reviewed it."""
        assert wf["active"] is False


class TestEmailNodes:
    def test_every_gmail_node_is_fully_configured(self, wf):
        """`Send a message4` (the Error Trigger's email) shipped with
        parameters == {"options": {}} -- no recipient, no subject, no body. It
        was wired up and completely inert, so no pipeline failure ever paged
        anyone."""
        for node in wf["nodes"]:
            if node["type"] != "n8n-nodes-base.gmail":
                continue
            params = node["parameters"]
            for field in ("sendTo", "subject", "message"):
                assert params.get(field), f"{node['name']} has no {field}"

    def test_every_gmail_node_sends_html(self, wf):
        """The bodies are HTML. Delivered as text/plain they are unreadable --
        MIGRATION_RUNBOOK.md Phase 3 calls this out explicitly."""
        for node in wf["nodes"]:
            if node["type"] == "n8n-nodes-base.gmail":
                assert node["parameters"].get("emailType") == "html", node["name"]

    def test_every_gmail_node_keeps_a_credential_reference(self, wf):
        for node in wf["nodes"]:
            if node["type"] == "n8n-nodes-base.gmail":
                assert node.get("credentials", {}).get("gmailOAuth2", {}).get("name")

    def test_no_references_to_the_dead_render_host(self, wf):
        """Three of the four original templates loaded the logo from
        pb-attio-pipeline.onrender.com -- the Render deployment this service was
        migrated off. A broken image in every live intake email."""
        assert "onrender.com" not in json.dumps(wf)


class TestIntakeBranchesUseTheBackendEmail:
    """pipeline/app.py's _run_pipeline_worker returns email_html/email_subject
    for every flow. The live workflow ignored them and re-built the HTML in
    Code nodes that had drifted -- only the PitchBook template rendered fit
    scores, and none could render a re-seen or filtered deal."""

    BRANCHES = [
        ("Send a message", "HTTP Request"),
        ("Send a message1", "HTTP Request1"),
        ("Send a message3", "HTTP Request3"),
    ]

    @pytest.mark.parametrize("gmail_name,http_name", BRANCHES)
    def test_subject_and_body_come_from_the_http_response(self, wf, gmail_name, http_name):
        node = next(n for n in wf["nodes"] if n["name"] == gmail_name)
        assert node["parameters"]["subject"] == f"={{{{ $('{http_name}').item.json.email_subject }}}}"
        assert node["parameters"]["message"] == f"={{{{ $('{http_name}').item.json.email_html }}}}"

    def test_only_the_jesse_digest_still_builds_html_in_n8n(self, wf):
        """/process-jesse formats ONE row per call, so the daily digest is a
        genuine cross-item aggregation n8n has to do. The three intake branches
        are not, and no longer do."""
        code_nodes = [n["name"] for n in wf["nodes"] if n["type"] == "n8n-nodes-base.code"]
        assert code_nodes == ["Code in JavaScript2"]


class TestSkipGuards:
    @pytest.mark.parametrize("if_name", ["If", "If1", "If4"])
    def test_intake_guard_checks_both_deals_and_email(self, wf, if_name):
        """Two conditions, not one. `deals.length > 0` preserves the original
        "no deals, no email" behaviour (the backend builds email_html even for a
        zero-deal run). `email_html notEmpty` guards the timeout case, where
        _start_pipeline returns the PARTIAL "screening" state with no email
        rendered yet."""
        node = next(n for n in wf["nodes"] if n["name"] == if_name)
        conds = node["parameters"]["conditions"]
        assert conds["combinator"] == "and"
        left = {c["leftValue"] for c in conds["conditions"]}
        assert left == {"={{ $json.deals?.length || 0 }}", "={{ $json.email_html }}"}

    def test_jesse_digest_is_guarded_on_new_names(self, wf):
        node = next(n for n in wf["nodes"] if n["name"] == "If3")
        conds = node["parameters"]["conditions"]["conditions"]
        assert conds[0]["leftValue"] == "={{ $json.newCount || 0 }}"

    def test_jesse_code_node_emits_the_count_the_guard_reads(self, wf):
        node = next(n for n in wf["nodes"] if n["name"] == "Code in JavaScript2")
        assert "newCount: newNames.length" in node["parameters"]["jsCode"]


class TestBackendContract:
    def test_http_nodes_target_exactly_the_expected_endpoints(self, wf):
        urls = {
            n["parameters"]["url"]
            for n in wf["nodes"]
            if n["type"] == "n8n-nodes-base.httpRequest"
        }
        assert urls == EXPECTED_ENDPOINTS

    def test_file_upload_branches_still_post_binary(self, wf):
        """/process, /process-watchlist and /process-top10 read
        request.files['file'] or the raw body. Switching these to JSON would
        break _read_file_bytes silently -- it returns a 400 the workflow does
        not surface."""
        for name in ("HTTP Request", "HTTP Request1", "HTTP Request3"):
            params = next(n for n in wf["nodes"] if n["name"] == name)["parameters"]
            assert params["method"] == "POST"
            assert params["contentType"] == "binaryData"
            assert params["inputDataFieldName"] == "data"

    def test_jesse_branch_still_posts_form_fields(self, wf):
        """/process-jesse reads request.get_json() field-by-field. The parameter
        NAMES are the contract with process_jesse()'s data.get(...) calls."""
        params = next(n for n in wf["nodes"] if n["name"] == "HTTP Request2")["parameters"]
        sent = {p["name"] for p in params["bodyParameters"]["parameters"]}
        assert {"Company", "Company Website", "Round", "Deal Size",
                "Post Valuation", "Revenue", "Date"} <= sent


class TestTriggersUnchanged:
    """The Drive folder ids and the Sheet id ARE the integration. A typo here
    silently watches nothing."""

    def test_watched_drive_folders(self, wf):
        watched = {
            n["parameters"]["folderToWatch"]["value"]: n["parameters"]["folderToWatch"]["cachedResultName"]
            for n in wf["nodes"]
            if n["type"] == "n8n-nodes-base.googleDriveTrigger"
            and n["parameters"].get("triggerOn") == "specificFolder"
        }
        assert watched == {
            "1GVVMI-xX3toVtc-hiypb2TLemZ8uHX8S": "PitchBook Weekly Drop",
            "1sdiMtR7RnM-J5zHVSV5_stykFUK7eyxU": "Watchlist Drop",
            "1MnwePOMH44sMn1522ZC2vOVDVCWeMuDH": "Top 10 VCs Deals",
        }

    def test_jesse_sheet_and_tab(self, wf):
        node = next(n for n in wf["nodes"] if n["name"] == "Get row(s) in sheet")
        assert node["parameters"]["documentId"]["value"] == "1-ebci81-Y-31fI7wQKHXymCfOcPYlXuEm7p8s0ziiXA"
        assert node["parameters"]["sheetName"]["value"] == 848698303

    def test_error_trigger_still_reaches_an_email(self, wf):
        assert ("Error Trigger", "Send a message4") in set(_edges(wf))
