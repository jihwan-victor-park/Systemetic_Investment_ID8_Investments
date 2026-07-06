# Deal Intelligence

Two-stage agent research over qualified deals. Stage 1 scores every qualified
deal against the rubric (v2.1: six weighted dimensions, with hard-auto-pass
vs. soft-pass so undisclosed data doesn't sink a score the way a confirmed
weakness would -- see `prompts/rubric.md`). Stage 2 does deep research and
writes a memo, but only for the deals that clear the gate.

```
pull qualified deals (Attio)
   -> stage 1: fit score for every deal           [cheap, Perplexity + rubric]
        -> write fit_score / gate / rationale to Attio
        -> gate: fit_score >= FIT_THRESHOLD
             -> stage 2: deep research + memo       [target deals only, Perplexity + Claude]
                  -> write final_score + memo link to Attio
```

## Run

```bash
python -m deal_intelligence.pipeline --dry-run   # no write-back, prints summary
python -m deal_intelligence.pipeline --stage1    # stage 1 only
python -m deal_intelligence.pipeline             # full run
```

## n8n wiring

n8n owns scheduling and orchestration. It calls a thin `/screen-deals` endpoint
(to be added to `app.py`) which runs `deal_intelligence.pipeline.run` in the
background, the same pattern as `/sync-apollo`. n8n then reads results back from
Attio and can post a summary to Slack.

## Before this runs

1. **Rubric**: done -- `prompts/rubric.md` + `rubric.py`'s `PARAMS` carry the
   real v2.1 rubric (weights must sum to 100; `rubric.validate()` enforces it).
2. **Prompts**: `prompts/stage1_fit.md`, `prompts/stage2_research.md`, and
   `prompts/memo_template.md` are filled in; revisit if the rubric or thesis changes.
3. **Attio fields**: create the write-back fields (fit score, gate, rationale,
   final score, memo url) and set their slugs via the `DI_SLUG_*` env vars in
   `config.py`. Writes are skipped for any slug left unset.
4. **Secrets**: `ATTIO_API_KEY`, `PERPLEXITY_API_KEY`, `ANTHROPIC_API_KEY`.
5. **Confirm** the deal-stage slug and the Qualified value (`DI_STAGE_SLUG`,
   `DI_QUALIFIED_VALUE`).

## Files

| File | Role |
| --- | --- |
| config.py | env, models, threshold, Attio slugs |
| rubric.py | the rubric: parameters, weights, weighted score |
| research.py | Perplexity and Claude HTTP helpers |
| attio_io.py | read qualified deals, write results back |
| stage1_fit.py | preliminary fit, every qualified deal |
| stage2_research.py | deep research and memo, target deals only |
| pipeline.py | orchestration and CLI |
| prompts/ | rubric and prompt templates |
