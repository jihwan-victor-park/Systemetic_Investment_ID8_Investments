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

from . import config, radar_access, radar_mandate, radar_state, rubric
from .fit_note import PARAM_LABELS, _badge_text, _linkify_md, company_id, normalize_domain
from .schemas import DealFit, DealInput, DealMemo

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
    screen_id = date.today().isoformat()
    company_payload = {
        "name": deal.name,
        "website": normalize_domain(deal.domain) or None,
        # Denormalized copy of this screen's headline fields, straight onto
        # the company doc -- added 2026-07-28. hub-next's listCompanies()
        # used to run one Firestore query PER company to fetch this from the
        # screens subcollection (a real N+1: 100+ companies meant 100+ round
        # trips on every cache-miss page load, the exact "Hub Perf Fix"
        # pattern documented in project memory). Writing it here once, at the
        # one place a screen is ever created, means the list view never has
        # to ask again. `gate` comes straight from `fit.gate` -- the real
        # boolean the scoring pass computed, not parsed back out of the
        # verdict string the way the old subcollection-read fallback did.
        "latestScreen": {
            "date": screen_id,
            "roundStage": deal.round,
            "fitScore": fit.fit_score,
            "gate": fit.gate,
        },
    }
    # Additive, independent-of-stage tag -- 2026-07-28. A company's `stage`
    # is still the one place it primarily lives (Watchlist/Pipeline/
    # Qualified/Radar/Invested), but Oscar wants a deal to be able to show
    # up in Qualified Deals on the strength of its OWN score clearing the
    # gate, regardless of whatever stage it's actually parked in (e.g. a
    # company sitting in Pipeline that also clears the gate should still
    # show up on Qualified Deals). `tags` is a small array (currently just
    # `qualified`/`radar`, see radar_state.py for the other one) that every
    # stage-table page ORs into its normal `stage`-based filter -- see
    # hub-next/src/app/(hub)/docs/qualified-deals/page.jsx. Uses
    # ArrayUnion so a re-screen that clears the gate again doesn't wipe out
    # a `radar` tag radar_state.py added independently, and a human who
    # manually removed the tag (they don't want it shown there) only gets
    # it re-added by a FRESH gate-clearing screen, not merely by this
    # merge write running again with no new fit result.
    if fit.gate:
        company_payload["tags"] = firestore.ArrayUnion(["qualified"])
    # Same "only when we actually have one" guard as push_company_from_attio --
    # a merge write with an explicit None would overwrite an already-known
    # description with nothing.
    if deal.description:
        company_payload["description"] = deal.description
    is_new = not company_ref.get().exists
    # origin.round/roundDate/roundSize/hq/leadInvestors always refresh, on
    # every screen (new or re-screen) -- same "origin mirrors the latest
    # known source value" convention push_company_from_attio already uses
    # unconditionally, added here 2026-07-28. Without this, a company
    # screened once via the standalone screen_pitchbook.py path (before
    # 2026-07-28, when load_deals() didn't read Deal Date/Size at all) has a
    # permanently blank origin.roundDate/roundSize no matter how many times
    # it gets re-screened later -- re-screening alone can't fix it unless
    # origin actually gets rewritten with the freshly-parsed values.
    # origin.source/attioRecordId/attioStage/importedAt stay sticky --
    # set once at creation only, preserving "how this company first showed
    # up" (the reason this split exists at all, see this function's
    # docstring) rather than being overwritten by whatever screened it most
    # recently.
    origin_patch = {
        "round": deal.round,
        "roundDate": deal.round_date,
        "roundSize": deal.deal_size,
        "hq": deal.hq,
        "leadInvestors": deal.lead_investors,
    }
    if is_new:
        # Only stamp a stage on brand-new companies (defaulting to
        # "qualified", where every screened deal has always shown up) --
        # never on a re-screen of an existing company, so it doesn't
        # silently undo Oscar re-filing it into Watchlist/Pipeline via the
        # hub's Stage dropdown.
        company_payload["stage"] = "qualified"
        # Top-level round/roundDate/roundSize -- same three fields
        # push_company_from_attio has always set on a brand-new company,
        # missing here until 2026-07-28 (this function only ever wrote them
        # into `origin`, never top-level). hub-next's RoundInput/
        # updateCompanyRound make `round` independently hand-editable
        # afterward, same don't-clobber relationship to origin.round as
        # everywhere else -- unlike origin (above), these are NEVER
        # refreshed on a re-screen of an existing company. A company still
        # missing these after a re-screen needs the one-time
        # backfill_company_rounds() pass below, which copies from the
        # now-freshly-refreshed origin.
        company_payload["round"] = deal.round or None
        company_payload["roundDate"] = deal.round_date or None
        company_payload["roundSize"] = deal.deal_size or None
        company_payload["origin"] = {
            "source": source,
            "attioRecordId": deal.record_id if source == "attio" else None,
            "attioStage": None,
            "importedAt": firestore.SERVER_TIMESTAMP,
            **origin_patch,
        }
    else:
        company_payload["origin"] = origin_patch
    company_ref.set(company_payload, merge=True)

    docx_path = _upload_docx(slug, docx_bytes)
    cites = fit.citations
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


def apply_placement(slug: str, tags: list, stage: str = None,
                    top10_firms: list = None) -> dict:
    """Apply an intake run's resolved placement to a company doc.

    `top10_firms` are the TOP10 firms matched on this deal's own cap table
    (pipeline/app.py's per-deal match_top10). Added 2026-08-10: this runs for
    EVERY deal in a run, screened or not, so it's the one place that can record
    Top 10 backing for a company that skips screening entirely. Before this,
    top10VC reached the hub only via push_company_from_attio and a one-time
    backfill, so a Sequoia-led deal arriving through the weekly PitchBook drop
    showed top10VC=false in hub-next's Top 10 VC view.

    Only ever sets top10VC True, never False -- the field means "confirmed Top
    10-backed", and a later run whose investor columns happen to be thinner
    must not retract an earlier confirmed match. Same convention as
    backfill_top10_vc and build_attio_values' Attio-side flag.

    `tags` are the ADDITIVE, non-primary hub stages from
    pipeline/app.py's determine_placement -- e.g. ['radar'] for a Series B whose
    primary is Qualified. Written with ArrayUnion, so this composes with the
    tags radar_state.py and push_company_screen_firestore set independently, and
    a human who unchecked a stage in the hub only gets it back from a fresh
    intake that genuinely resolves to it.

    `stage` is only ever written when the company doc DOESN'T EXIST YET. On an
    existing company the primary is left strictly alone: Oscar re-files deals by
    hand through the hub's stage multiselect, and an import must not silently
    undo that. This mirrors push_company_screen_firestore's own
    only-stamp-stage-on-new rule.

    Added 2026-08-03, because determine_placement's tags were being computed and
    then dropped -- used for the email badge and nothing else, so the dual
    Qualified+Radar placement never actually reached the hub. It matters most for
    a deal that skips screening: a company already screened via the other intake
    source gets no push_company_screen_firestore call at all, so this is the ONLY
    thing that records the second source's placement for it.
    """
    if not slug or (not tags and not stage and not top10_firms):
        return {"slug": slug, "written": False}
    ref = _firestore().collection("companies").document(slug)
    payload = {}
    if tags:
        payload["tags"] = firestore.ArrayUnion(list(tags))
    if top10_firms:
        payload["top10VC"] = True
        # ArrayUnion so a run that saw only some of the firms on the cap table
        # adds to the known set rather than replacing it.
        payload["tier1Firms"] = firestore.ArrayUnion(list(top10_firms))
    if stage and not ref.get().exists:
        payload["stage"] = stage
    if not payload:
        return {"slug": slug, "written": False}
    ref.set(payload, merge=True)
    return {"slug": slug, "written": True, "tags": list(tags or []),
            "stage": payload.get("stage"), "top10_firms": list(top10_firms or [])}


def latest_screen(slug: str) -> dict | None:
    """This company's most recent Stage 1 screen summary, or None if never
    screened. Shape: {date, roundStage, fitScore, gate} (the denormalized
    `latestScreen` map), so a caller can report a prior score without re-running
    research.

    Added 2026-08-03. Nothing anywhere checked this before, which cost real
    money in both directions: /screen-deals re-screened every Qualified deal on
    every run, and the intake pathways had no way to tell "this deal is new to
    THIS export" apart from "this deal has never been screened at all" -- so a
    company arriving via a second intake source either got screened twice or
    (once dedup dropped it) never at all.

    Reads the denormalized `latestScreen` map on the company doc first, since
    that's a single document read and is written by
    push_company_screen_firestore on every screen. Falls back to the newest doc
    in the `screens` subcollection for companies screened before `latestScreen`
    existed (it was added 2026-07-28) -- without that fallback an older company
    would look unscreened and get re-researched needlessly. Screen doc ids are
    ISO dates, so ordering by document id descending is a date sort.
    """
    snap = _firestore().collection("companies").document(slug).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    summary = data.get("latestScreen") or {}
    if summary.get("date"):
        return summary
    for doc in (snap.reference.collection("screens")
                .order_by("__name__", direction=firestore.Query.DESCENDING)
                .limit(1).stream()):
        d = doc.to_dict() or {}
        return {"date": d.get("date") or doc.id, "roundStage": d.get("roundStage"),
                "fitScore": d.get("fitScore"), "gate": d.get("gate")}
    return None


def has_screen(slug: str) -> bool:
    """True when this company already has at least one Stage 1 screen on file.
    Thin wrapper over latest_screen for callers that only need the boolean."""
    return latest_screen(slug) is not None


def push_company_memo_firestore(memo: DealMemo, slug: str) -> dict:
    """Persist a Stage 2 deep-research memo against an existing company doc --
    previously this only ever lived in the ad-hoc chat_jobs doc (pipeline/
    app.py's _run_chat_stage2), gone the moment that job aged out, with no way
    to view it again after leaving the Research Chat page it started from.
    Same same-day-replace convention as push_company_screen_firestore's
    `screens` subcollection: a same-day re-run overwrites rather than
    duplicates. Mirrors that function's schema comment -- hub-next's
    lib/companies.js reads this at companies/{slug}/memos/{YYYY-MM-DD}."""
    company_ref = _firestore().collection("companies").document(slug)
    memo_id = date.today().isoformat()
    memo_doc = {
        "date": memo_id,
        "finalScore": memo.final_score,
        "sections": memo.sections,
        "sources": memo.sources,
    }
    company_ref.collection("memos").document(memo_id).set(memo_doc, merge=True)
    return {"slug": slug, "memo_id": memo_id}


def push_company_from_attio(deal: DealInput, attio_stage: str | None, tier1_index: dict | None = None, partner_index: dict | None = None) -> dict:
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
    keywords against -- radarCategory alone is too sparse.

    `tier1_index`/`partner_index` (both optional): pre-built
    radar_mandate.build_tier1_index()/radar_access.build_partner_index()
    results, for a caller processing many deals in one loop (the bulk Attio
    import) to build ONCE outside the loop and pass through -- avoids
    re-reading the whole topVCs/partnerVCs collections on every single deal.
    A caller with no index handy (a one-off Run Analysis rerun, say) can
    omit either; this function builds them lazily on the rare occasion
    they're actually needed (a company resolving to the Radar stage), never
    unconditionally.
    """
    slug = company_id(deal)
    company_ref = _firestore().collection("companies").document(slug)
    origin = {
        "source": "attio",
        "attioRecordId": deal.record_id,
        "attioStage": attio_stage,
        "round": deal.round,
        "roundDate": deal.round_date,
        "roundSize": deal.deal_size,
        "hq": deal.hq,
        "leadInvestors": deal.lead_investors,
        "importedAt": firestore.SERVER_TIMESTAMP,
    }
    existing_snap = company_ref.get()
    is_new = not existing_snap.exists
    payload = {"origin": origin}
    # Only ever set when Attio actually has one -- a merge write with an
    # explicit None WOULD overwrite an already-known description with
    # nothing, unlike an absent key (which merge=True leaves untouched).
    if deal.description:
        payload["description"] = deal.description
    # Same "refresh on every push, new or existing company alike" rule as
    # description -- a company's cap table can pick up new investors between
    # imports, and there's no hub-next hand-edit path for this to clobber.
    # Feeds hub-next's Partner VC column (companyIndex.js's
    # domainMatchesFromIndex) alongside the existing name-match against a
    # VC's own recorded portfolio. Added 2026-07-28.
    if deal.investor_domains:
        payload["investorDomains"] = deal.investor_domains
    # Only ever write True, never False -- same "confirmed Yes sticks
    # forever" rule as the Attio-side write in pipeline/app.py's
    # build_attio_values/upsert_deal (2026-07-28, see that comment for the
    # full story: this signal was always computed correctly at
    # /process-top10 intake time, just silently dropped before reaching
    # Attio, so top10VC read false for every company sourced from the Top
    # 10 VC PitchBook search until now). Refreshed on every push like
    # `description`, not gated to is_new like round/roundDate/roundSize --
    # an existing company re-imported through the top10 pathway for the
    # first time should still pick up the flag.
    if deal.top10:
        payload["top10VC"] = True
    if is_new:
        payload["name"] = deal.name
        payload["website"] = normalize_domain(deal.domain) or None
        payload["round"] = deal.round or None
        payload["roundDate"] = deal.round_date or None
        payload["roundSize"] = deal.deal_size or None
        payload["stage"] = config.ATTIO_STAGE_MAP.get((attio_stage or "").strip().lower(), "new")
    company_ref.set(payload, merge=True)

    # Radar clock recompute (RADAR_PLAN.md Part I/III/IV/VI) -- only for
    # companies actually resolving to the Radar stage, and only a best-effort
    # side effect: the write above is this function's own source of truth
    # regardless of whether this succeeds, same non-blocking convention
    # companies.js's pushStageToAttio write-back uses on the hub-next side.
    resolved_stage = payload.get("stage") if is_new else (existing_snap.to_dict() or {}).get("stage")
    if resolved_stage == "radar":
        try:
            index = tier1_index if tier1_index is not None else radar_mandate.build_tier1_index(radar_state.list_top_vcs())
            p_index = partner_index if partner_index is not None else radar_access.build_partner_index(radar_state.list_partner_vcs())
            # Re-read rather than reconstruct from `payload`/`existing_snap`
            # branches -- this always reflects exactly what's now persisted
            # (top-level roundDate/roundSize/round are don't-clobber fields
            # on an existing company, so the freshest deal.* values aren't
            # necessarily what's actually on the doc).
            current = company_ref.get().to_dict() or {}
            fields = {
                "name": current.get("name"), "hq": deal.hq, "series": current.get("round"),
                "top10VC": current.get("top10VC", False),
                "roundSize": current.get("roundSize"), "roundDate": current.get("roundDate"),
                "radarCategory": current.get("radarCategory"), "description": current.get("description"),
                "website": current.get("website"),
            }
            radar_state.recompute_and_write(slug, fields, index, "attio-import", partner_index=p_index)
        except Exception as e:
            print(f"push_company_from_attio({slug}): radar recompute failed (non-blocking): {e}")

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
    round/roundDate/roundSize fields were introduced -- copies each from its
    origin.* counterpart (stamped by push_company_from_attio and, as of
    2026-07-28, push_company_screen_firestore too -- see that function's own
    comment on the gap this closes) wherever the top-level field is still
    unset and origin has a value. Each of the three is backfilled
    independently (a company might be missing roundDate but already have a
    hand-corrected round, say) and never overwrites an already-set value, so
    an edit already made from the hub's Series field (or a Radar-clock write
    to roundSize -- there isn't one, roundSize has no hub-editable UI, but
    the principle is the same) is untouched.

    This is what actually fixes a company already sitting in the hub with a
    blank Deal Date -- re-screening it doesn't help, since
    push_company_screen_firestore only ever sets the top-level fields on a
    BRAND-NEW company, never on a re-screen of an existing one."""
    updated_round, updated_date, updated_size, touched = [], [], [], set()
    for doc in _firestore().collection("companies").stream():
        data = doc.to_dict()
        origin = data.get("origin") or {}
        patch = {}
        if not data.get("round") and origin.get("round"):
            patch["round"] = origin["round"]
            updated_round.append(doc.id)
        if not data.get("roundDate") and origin.get("roundDate"):
            patch["roundDate"] = origin["roundDate"]
            updated_date.append(doc.id)
        if not data.get("roundSize") and origin.get("roundSize"):
            patch["roundSize"] = origin["roundSize"]
            updated_size.append(doc.id)
        if patch:
            doc.reference.set(patch, merge=True)
            touched.add(doc.id)
    return {
        "touched": len(touched), "touched_slugs": sorted(touched),
        "updated_round": len(updated_round), "updated_round_date": len(updated_date),
        "updated_round_size": len(updated_size),
    }


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
