"""Push stage-1 screening results directly into Firestore, for hub-next (the
dynamic Next.js hub) to read live. No rebuild required, unlike the GitHub
Contents API path in hub_push.py that feeds the old static Docusaurus hub.

Schema mirrors exactly what hub-next/src/lib/companies.js reads:
    companies/{slug}                      -> {name, website, stage}
    companies/{slug}/screens/{YYYY-MM-DD} -> {date, roundStage, fitScore,
        rawScore, verdict, hardAutoPassNote, dimensions, rationale,
        confidence, sources, docxPath}

Text fields (rationale, dimension evidence, hardAutoPassNote) use the same
"[[n]](url)" / "**bold**" mini-markdown that hub-next's InlineMarkdown
component parses -- reuse fit_note's helpers rather than re-deriving the format.

The .docx itself is not stored in Firestore (not a blob store) -- it goes to
Cloud Storage at gs://<DI_DOCX_BUCKET>/research/companies/<slug>.docx, and
docxPath points at hub-next's /api/research/companies/<slug>/docx route, which
streams it from that bucket.
"""
from datetime import date

from google.cloud import firestore, storage

from . import config, rubric
from .fit_note import PARAM_LABELS, _badge_text, _linkify_md, company_id, normalize_domain
from .schemas import DealFit, DealInput

_db = None
_gcs_client = None

# key -> {1: "...", 2: "...", 3: "...", 4: "..."}, the fixed anchor text for
# every subcategory across every dimension. Denormalized onto each pushed
# subcategory doc below so hub-next's hover pop-up needs zero cross-repo
# sync -- it renders whatever's already on the Firestore document, and this
# module (rubric.py) is the only place that text is authored.
_SUB_ANCHORS = {
    s["key"]: s["anchors"]
    for dim in rubric.PARAMS
    for s in dim["subcategories"]
}


def _firestore():
    global _db
    if _db is None:
        _db = firestore.Client(project=config.GCP_PROJECT_ID)
    return _db


def _gcs():
    global _gcs_client
    if _gcs_client is None:
        _gcs_client = storage.Client(project=config.GCP_PROJECT_ID)
    return _gcs_client


def _upload_docx(slug: str, docx_bytes: bytes) -> str | None:
    """Upload to GCS; return the hub-next docx route path, or None if
    DI_DOCX_BUCKET isn't configured (the Firestore write still happens --
    that screen just has no download link until the bucket is set up)."""
    if not config.DI_DOCX_BUCKET:
        return None
    blob = _gcs().bucket(config.DI_DOCX_BUCKET).blob(f"research/companies/{slug}.docx")
    blob.upload_from_string(
        docx_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    return f"/api/research/companies/{slug}/docx"


def push_company_screen_firestore(fit: DealFit, deal: DealInput, slug: str, docx_bytes: bytes,
                                   source: str = "chat") -> dict:
    """Upsert the company doc and today's dated screen. Screen doc id is the
    ISO date, so a same-day re-run overwrites rather than duplicates --
    matching hub_push's same-day-replace rule for the markdown page.

    `source` labels how this screen was triggered ("attio" for the qualified
    backlog pull, "chat" for Research Chat / a per-row Run Analysis rerun) --
    only stamped into `origin` on brand-new companies, same as `stage` below,
    so hub-next's Origin column can show *how a company first showed up*
    rather than how its latest screen happened to run."""
    company_ref = _firestore().collection("companies").document(slug)
    company_payload = {"name": deal.name, "website": normalize_domain(deal.domain) or None}
    # Only stamp a stage on brand-new companies (defaulting to "qualified",
    # where every screened deal has always shown up) -- never on a re-screen
    # of an existing company, so it doesn't silently undo Oscar re-filing it
    # into Watchlist/Pipeline via the hub's Stage dropdown.
    if not company_ref.get().exists:
        company_payload["stage"] = "qualified"
        company_payload["origin"] = {
            "source": source,
            "attioRecordId": deal.record_id if source == "attio" else None,
            "attioStage": None,
            "round": deal.round,
            "hq": deal.hq,
            "leadInvestors": deal.lead_investors,
            "importedAt": firestore.SERVER_TIMESTAMP,
        }
    company_ref.set(company_payload, merge=True)

    docx_path = _upload_docx(slug, docx_bytes)
    cites = fit.citations
    screen_id = date.today().isoformat()
    screen_doc = {
        "date": screen_id,
        "roundStage": deal.round,
        "fitScore": fit.fit_score,
        "rawScore": fit.raw_score,
        "verdict": _badge_text(fit).lower(),
        "hardAutoPassNote": (
            f"Hard auto-pass: {_linkify_md(fit.hard_auto_pass_reason, cites)}"
            if (fit.hard_auto_pass and fit.hard_auto_pass_reason) else None
        ),
        "dimensions": [
            {
                "key": p.key,
                "name": PARAM_LABELS.get(p.key, p.key),
                "score": p.score,
                "evidence": _linkify_md(p.evidence.replace("|", "/").replace("\n", " "), cites),
                # Point-level tier of the three-tier rationale (point -> dimension ->
                # deal). Every dimension, Terms included, has at least one subcategory
                # now. `anchors` is the fixed 1-4 rubric text for that item, copied
                # from rubric.py at push time -- what hub-next's hover pop-up renders.
                "subcategories": [
                    {
                        "key": s.key,
                        "name": s.label,
                        "score": s.score,
                        "finding": _linkify_md(s.finding.replace("|", "/").replace("\n", " "), cites),
                        # Firestore map keys must be strings -- anchors is
                        # keyed 1-4 in rubric.py, stringified here for storage.
                        "anchors": {str(k): v for k, v in _SUB_ANCHORS.get(s.key, {}).items()},
                    }
                    for s in p.subcategories
                ],
            }
            for p in fit.params
        ],
        "rationale": _linkify_md(fit.rationale, cites),
        "confidence": fit.confidence,
        "sources": [{"number": i, "url": url} for i, url in enumerate(cites, 1)],
    }
    if docx_path:
        screen_doc["docxPath"] = docx_path
    company_ref.collection("screens").document(screen_id).set(screen_doc, merge=True)
    return {"slug": slug, "screen_id": screen_id, "docx_uploaded": docx_path is not None}


def push_company_from_attio(deal: DealInput, attio_stage: str | None) -> dict:
    """Metadata-only upsert for the bulk Attio import -- no Stage 1 score, no
    docx, no screens subcollection write, just enough to make the deal show
    up for Oscar to triage. On a brand-new company: lands as stage='new'
    (hub-next's "not yet triaged" bucket) with full origin metadata. On an
    existing company: only refreshes `origin` (Attio is the source of truth
    for round/hq/leadInvestors/attioStage) -- never touches `stage`, `name`,
    or `website`, extending push_company_screen_firestore's same
    don't-clobber-stage rule to this path."""
    slug = company_id(deal)
    company_ref = _firestore().collection("companies").document(slug)
    origin = {
        "source": "attio",
        "attioRecordId": deal.record_id,
        "attioStage": attio_stage,
        "round": deal.round,
        "hq": deal.hq,
        "leadInvestors": deal.lead_investors,
        "importedAt": firestore.SERVER_TIMESTAMP,
    }
    is_new = not company_ref.get().exists
    payload = {"origin": origin}
    if is_new:
        payload["name"] = deal.name
        payload["website"] = normalize_domain(deal.domain) or None
        payload["stage"] = "new"
    company_ref.set(payload, merge=True)
    return {"slug": slug, "created": is_new}
