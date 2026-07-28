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
    # Same "only when we actually have one" guard as push_company_from_attio --
    # a merge write with an explicit None would overwrite an already-known
    # description with nothing.
    if deal.description:
        company_payload["description"] = deal.description
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
            "roundDate": deal.round_date,
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
        "gate": fit.gate,
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
    up for Oscar to triage. On a brand-new company: lands in the hub tab that
    matches its Attio stage (config.ATTIO_STAGE_MAP: Watchlist/Pipeline/
    Qualified/Radar/Invested); no match (unset or anything else) explicitly
    sets `stage` to 'new' -- hub-next's internal-only holding bucket with no
    public tab, surfaced in the Admin page's "Needs Triage" table instead of
    silently blending into Qualified Deals (that used to be the fallback;
    Oscar wants unmapped deals visibly flagged for manual assignment, not
    quietly mixed in with everything else). On an existing company: only
    refreshes `origin` (Attio is the source of truth for
    round/roundDate/hq/leadInvestors/attioStage) plus the top-level
    `description` -- never touches `stage`, `name`, `website`, or `round`,
    extending push_company_screen_firestore's same don't-clobber-stage rule
    to this path. `round` is a brand-new company's initial Series value,
    seeded from Attio but independently editable afterward from the hub (see
    hub-next's RoundInput/updateCompanyRound) -- unlike `origin.round`, which
    keeps tracking Attio's own value on every re-import, this top-level copy
    is never overwritten once set. `roundDate` mirrors that same relationship
    (added 2026-07-28, RADAR_PLAN.md Part I -- Radar's capital-clock math
    needs the round's close date). `description` is different: nothing in
    the hub hand-edits it, so unlike round/roundDate it's refreshed on EVERY
    push, new or existing company alike -- an already-imported company (like
    the case that motivated this: a real Top 10 VC deal already sitting in
    Firestore with no description on file) gets backfilled on its next
    import rather than staying blank forever. Feeds the relevance-exclusion
    list (RADAR_PLAN.md §1.6), which needs real description text to match
    keywords against -- radarCategory alone is too sparse."""
    slug = company_id(deal)
    company_ref = _firestore().collection("companies").document(slug)
    origin = {
        "source": "attio",
        "attioRecordId": deal.record_id,
        "attioStage": attio_stage,
        "round": deal.round,
        "roundDate": deal.round_date,
        "hq": deal.hq,
        "leadInvestors": deal.lead_investors,
        "importedAt": firestore.SERVER_TIMESTAMP,
    }
    is_new = not company_ref.get().exists
    payload = {"origin": origin}
    # Only ever set when Attio actually has one -- a merge write with an
    # explicit None WOULD overwrite an already-known description with
    # nothing, unlike an absent key (which merge=True leaves untouched).
    if deal.description:
        payload["description"] = deal.description
    if is_new:
        payload["name"] = deal.name
        payload["website"] = normalize_domain(deal.domain) or None
        payload["round"] = deal.round or None
        payload["roundDate"] = deal.round_date or None
        payload["stage"] = config.ATTIO_STAGE_MAP.get((attio_stage or "").strip().lower(), "new")
    company_ref.set(payload, merge=True)
    return {"slug": slug, "created": is_new}


def backfill_attio_stages() -> dict:
    """One-time correction for companies the bulk Attio import created before
    push_company_from_attio's stage mapping existed -- every one of them was
    forced to stage='new' regardless of its real Attio stage. Finds every
    company still at stage='new' with origin.source=='attio' whose stored
    origin.attioStage now maps to a real bucket (config.ATTIO_STAGE_MAP,
    including Radar and Invested) and moves it there. A company with no
    mapping (no stage recorded at all) is left at 'new' -- that's exactly
    where a genuinely untriaged deal belongs, and it now surfaces in the
    hub's Admin page ("Needs Triage") for manual assignment instead of
    sitting in an orphaned tab.

    Returns a `skip_reasons` breakdown (non_attio_source vs unmapped_stage,
    plus a tally of the raw origin.attioStage strings behind unmapped_stage)
    so a 0-updated run is diagnosable -- e.g. Attio's real stage-field values
    don't textually match config.ATTIO_STAGE_MAP's keys, rather than every
    stuck company genuinely lacking a stage."""
    updated, skipped = [], []
    non_attio_source = 0
    unmapped_stage_tally = {}
    for doc in _firestore().collection("companies").where("stage", "==", "new").stream():
        data = doc.to_dict()
        origin = data.get("origin") or {}
        if origin.get("source") != "attio":
            skipped.append(doc.id)
            non_attio_source += 1
            continue
        raw_stage = (origin.get("attioStage") or "").strip()
        mapped_stage = config.ATTIO_STAGE_MAP.get(raw_stage.lower())
        if mapped_stage:
            doc.reference.set({"stage": mapped_stage}, merge=True)
            updated.append(doc.id)
        else:
            skipped.append(doc.id)
            key = raw_stage or "(blank)"
            unmapped_stage_tally[key] = unmapped_stage_tally.get(key, 0) + 1
    return {
        "updated": len(updated), "skipped": len(skipped), "updated_slugs": updated,
        "skip_reasons": {"non_attio_source": non_attio_source, "unmapped_attio_stage_tally": unmapped_stage_tally},
    }


def backfill_company_rounds() -> dict:
    """One-time backfill for companies that existed before the top-level
    `round` field was introduced -- copies origin.round (stamped by both
    push_company_from_attio and push_company_screen_firestore since before
    this field existed) onto `round` wherever `round` is still unset and
    origin.round has a value. Never overwrites an already-set `round`, so an
    edit already made from the hub's Series field is untouched."""
    updated, skipped = [], []
    for doc in _firestore().collection("companies").stream():
        data = doc.to_dict()
        if data.get("round"):
            skipped.append(doc.id)
            continue
        origin_round = (data.get("origin") or {}).get("round")
        if origin_round:
            doc.reference.set({"round": origin_round}, merge=True)
            updated.append(doc.id)
        else:
            skipped.append(doc.id)
    return {"updated": len(updated), "skipped": len(skipped), "updated_slugs": updated}


def backfill_top10_vc(names: list) -> dict:
    """One-time seed for `top10VC` from a snapshot of Attio's "Top 10 VC"
    Deals-object view (a saved filter, not a Deal attribute or a List --
    there's no API query that reproduces it yet, so this takes the view's
    current membership as plain company names, typed/pasted by hand).

    Matches each name against `companies` by exact (case-insensitive,
    trimmed) name -- company.name already carries any PitchBook category
    suffix verbatim (e.g. "Pocket (Business/Productivity Software)", see
    hub-next's companyStageColumns.jsx), so names copied straight out of
    Attio/PitchBook should match as-is with no stripping needed.

    Only ever sets top10VC=True on a match -- never sets it False on
    anything, so this is purely additive and safe to re-run as the view's
    membership grows. `unmatched` is names with no corresponding company doc
    yet (most likely: that deal hasn't been pulled into the hub at all --
    run /import-attio-deals first, or the two names just don't match
    verbatim character-for-character)."""
    by_name = {}
    for doc in _firestore().collection("companies").stream():
        nm = (doc.to_dict().get("name") or "").strip().lower()
        if nm:
            by_name.setdefault(nm, []).append(doc.reference)

    matched, unmatched = [], []
    for raw_name in names:
        key = (raw_name or "").strip().lower()
        refs = by_name.get(key)
        if not refs:
            unmatched.append(raw_name)
            continue
        for ref in refs:
            ref.set({"top10VC": True}, merge=True)
        matched.append(raw_name)
    return {"matched": len(matched), "unmatched": unmatched, "unmatched_count": len(unmatched)}
