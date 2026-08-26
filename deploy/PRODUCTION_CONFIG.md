# `id8` production configuration — captured 2026-08-26

Snapshot of the live Cloud Run service, plus the findings that fall out of it.
Source: `gcloud run services describe id8 --region us-east4` at revision
`id8-00338-5px` (generation 339, commit `6085a8b`, last deployed 2026-08-15).

`deploy/deploy-id8.sh` reproduces this configuration. This file explains it.

## How production actually deploys

Cloud Build trigger `0ed43e8f-663f-48b6-af45-18513c562fbd` (global) watches
`ocachin/id8-intelligence` @ `main`:

1. `docker build --no-cache -t $AR/.../id8:$COMMIT_SHA . -f Dockerfile`
2. `docker push`
3. `gcloud run services update id8 --image=... --region=us-east4`

Artifact Registry: `us-east4-docker.pkg.dev/molten-crowbar-498920-q8/cloud-run-source-deploy/id8-intelligence/id8`

**The deploy step swaps the image only.** It passes no `--set-env-vars`, no
`--update-secrets`, no resource flags. That is a genuinely good property — it
means a routine deploy cannot wipe the service's configuration, unlike
`hub-next/cloudbuild.yaml`, whose `--set-env-vars` replaces the whole env set on
every build (that file's own header documents losing `PIPELINE_BASE_URL` that
way). The cost is that the configuration lived only in the live service.

## Live values

| Setting | Value | Notes |
| --- | --- | --- |
| Project / region | `molten-crowbar-498920-q8` / `us-east4` | project number `137750788450` |
| URLs | `id8-137750788450.us-east4.run.app`, `id8-bkq2vtg6qq-uk.a.run.app` | both live; n8n uses the first |
| Memory | **2Gi** | root `Dockerfile`'s comment still says 512 MiB — stale |
| CPU | `1000m`, `cpu-throttling: false`, startup CPU boost | always-allocated CPU |
| Request timeout | `1800s` | matches gunicorn `--timeout 1800`; must stay in sync |
| Concurrency | `80` per instance | |
| Max instances | **3** | see "Known risk" below |
| Min instances | **unset (0)** | scales to zero; every idle-period request pays a cold start |
| Startup probe | tcp:8080, timeout 240s, period 240s, failures 1 | very permissive |
| Ingress | `all` + `invoker-iam-disabled: true` | **publicly invocable, no IAM check** |
| Runtime SA | `137750788450-compute@developer.gserviceaccount.com` | default Compute SA |
| Creator | `oscar@id8investments.com` | |

### Environment

Plain:
- `DI_HUB_BASE_URL=https://molten-crowbar-498920-q8.web.app`
- `DI_DOCX_BUCKET=molten-crowbar-498920-q8-hub-next-docs`
- `FORCE_RESTART=stop-the-backlog-run`

Secret Manager bindings (names only):
- `PERPLEXITY_API_KEY` → `PERPLEXITY_API_KEY:latest`
- `ATTIO_API_KEY` → `ATTIO_API_KEY:latest`
- `GH_TOKEN` → `GH_TOKEN:latest`
- `ATTIO_WEBHOOK_SECRET` → `id8-attio-webhook-secret:latest`

## Findings

### 1. Four secrets the code reads are not bound — all fail silently

| Missing | Consumed by | Effect today |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | `config.py` → Stage 2 memo synthesis, rubric scoring | Stage 2 cannot synthesize memos. Also absent from `_secrets.py`'s Secret Manager map, so that fallback cannot supply it either — it would have to be a direct env binding. |
| `APOLLO_API_KEY` | `apollo_org.py` → Radar headcount | `capital_clock` has no headcount, so runway and every predicted raise date derived from it are unavailable. |
| `OPENAI_API_KEY` | `ai_relevance_embeddings.py` → `portfolio_prefilter` | Embedding prefilter unavailable (raises `AIRelevanceUnavailable`, handled). |
| `INTERNAL_API_SECRET` | `_require_internal_secret()` | Returns `True` unconditionally when unset. |

None of these raise at startup. Each degrades quietly, which is why the gaps
were invisible.

### 2. Every route except one is open to the internet

`ingress: all` + `invoker-iam-disabled: true` means no IAM check, and
`INTERNAL_API_SECRET` is unset, so `_require_internal_secret()` returns `True`
for every caller. `pipeline/app.py`'s own comment already stated this
("this service answers unauthenticated requests from the open internet"); the
live config confirms it.

`/attio-deal-created` is the only genuinely protected route, via
`ATTIO_WEBHOOK_SECRET` — which *is* bound. Unprotected and mutating:
`/update-deal-stage`, `/update-deal-fields`, `/import-attio-deals`,
`/process*`, `/screen-deals`, plus ~11 one-off backfill routes.

Fix: create `id8-internal-api-secret`, bind it, set the matching
`PIPELINE_INTERNAL_SECRET` on `id8-hub-next`. Both must land together — setting
only the backend breaks hub-next's proxy routes.

### 3. Known risk: `max-instances: 3` vs the intake lock

`_pipeline_slot = threading.BoundedSemaphore(1)` is a **per-process** object. It
serializes intake runs inside one container. It cannot see another container.

With `max-instances: 3`:

- Two Drive drops arriving seconds apart (a documented real event — 2026-08-10,
  `/process-top10` at 13:10:43 and `/process` 9s later) can be served by two
  different instances and run **concurrently**, which is exactly what the
  semaphore exists to prevent.
- `GET /process/status` can land on an instance that never saw the POST and will
  answer `{"status": "idle"}` mid-run — the same failure the Dockerfile
  describes fixing by dropping to one gunicorn worker. Collapsing workers fixed
  it within a container; instances reintroduce it across containers.

`concurrency: 80` makes this unlikely at current traffic (Cloud Run adds an
instance under concurrent load, and this service sees very little), which is
consistent with it not having caused a visible incident. It is still a
correctness gap, not a tuning preference.

Two ways to close it, in order of preference:

1. **Move intake job state to Firestore.** The pattern already exists in the
   same file — `/research-chat` uses a `chat_jobs` collection with
   `_start_chat_job`/`_set_chat_job`/`_get_chat_job`. Reusing it for `/process`
   makes status polling instance-independent and makes the admission lock a
   Firestore transaction. Removes the constraint rather than working around it.
2. **Set `--max-instances=1`.** One line, immediately correct, and caps
   throughput at one container. Acceptable for this workload but a real ceiling.

Not changed here — it alters production behavior and is your call.

### 4. Runtime service account

`137750788450-compute@developer.gserviceaccount.com` is the default Compute
service account, used for **both** the Cloud Build deploy step (see
`lastModifier`) and the container runtime. On a project of this vintage it
typically carries project **Editor**, which means:

- The running container can read every secret in the project, not just its four.
- Any push to `main` executes a build with Editor on the whole project.

Preferred end state: a dedicated `id8-runtime@` with `secretmanager.secretAccessor`
scoped to its four secrets, `datastore.user`, and `storage.objectAdmin` on
`molten-crowbar-498920-q8-hub-next-docs`; and a separate `id8-cloudbuild@` with
`artifactregistry.writer`, `run.developer`, `iam.serviceAccountUser` on the
runtime SA, and `logging.logWriter`.

Do this **after** a rollback path is established, not before — changing the
identity mid-takeover risks breaking deploys.

### 5. `--no-cache` on every build

The build step passes `--no-cache`, so every push reinstalls all of
`requirements.txt` (pandas, numpy, google-cloud-*) from scratch. Combined with
the build context problem below, builds are far slower and more expensive than
necessary. Dropping `--no-cache` is safe — `COMMIT_SHA` tags already make images
unique, and Docker layer caching keys on the `COPY requirements.txt` layer,
which changes exactly when the dependencies do.

### 6. Build context (fixed in this change)

The root `Dockerfile` does `COPY . .` and there was **no root `.dockerignore`**,
so all 915 git-tracked files (441.2 MB) went into the backend image — including
`higgsfield/` (160 MB of deck PDFs and screenshots), `hub-next/` (19 MB),
`hub/` (7.3 MB), `design/`, `docs/`, `scripts/`.

The new root `.dockerignore` reduces this to 108 files / 6.0 MB (**-98.6%**).
Verified by importing `pipeline/app.py` and enumerating `sys.modules`: the Flask
app loads 33 `deal_intelligence` modules, none of which read anything outside
`deal_intelligence/*.py` and `deal_intelligence/prompts/`.

`deal_intelligence/data/` is deliberately kept — it is 5.4 MB, and
`backfill_deal_dates.py` / `backfill_hub_deal_dates.py` (Cloud Run Jobs that run
from this image) read `deal-date-corrections-2026-08-14.json` from it.

### 7. Cloud Build trigger has no path filter

The exported trigger config contains no `includedFiles`, so every push to `main`
rebuilds and redeploys the backend — including commits that touch only
`hub-next/`, `docs/`, or `higgsfield/`. `hub-next` is a separate service with its
own Dockerfile and `cloudbuild.yaml`, so those builds are pure waste.

Suggested trigger filter (set in the trigger, not in this repo):

```
includedFiles:
  - pipeline/**
  - deal_intelligence/**
  - requirements.txt
  - Dockerfile
  - Procfile
```

### 8. `FORCE_RESTART=stop-the-backlog-run`

A plain env var whose only purpose is to force a new revision — the value is a
note-to-self about an incident ("stop the backlog run"). Harmless, and
`deploy-id8.sh` deliberately does not reproduce it: `--update-env-vars` leaves
the existing value alone, and re-asserting an incident artifact as intended
configuration would be misleading. Safe to delete from the service whenever
convenient.

### 9. `DI_HUB_BASE_URL` points at Firebase Hosting

`https://molten-crowbar-498920-q8.web.app` is a Firebase Hosting URL, not the
`id8-hub-next` Cloud Run service. Every `hub_url` embedded in a screen result
and in the intake emails is built from this value (`fit_note.hub_url`). Worth
confirming this still resolves to the hub you intend people to land on — the
n8n email templates also fall back to a hardcoded
`https://id8-hub-next-bkq2vtg6qq-uc.a.run.app` when no deal carries a `hub_url`,
so two different hub hostnames are in play.
