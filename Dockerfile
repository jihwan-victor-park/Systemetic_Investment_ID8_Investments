FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080

# --timeout 1800: /screen (n8n's synchronous intake-batch endpoint) runs Stage 1
# deal_intelligence scoring inline, and Stage 1 now calls Perplexity's
# sonar-deep-research at max reasoning effort, which can take several minutes
# per deal -- the old 300s worker timeout would kill a real batch mid-request.
# Pair with `gcloud run deploy --timeout=1800`, since Cloud Run's own request
# timeout would otherwise cut the connection before gunicorn's does.
#
# 1 worker + 8 threads, not 3 workers (changed 2026-08-03). Two reasons, both
# real bugs rather than tuning:
#
# 1. MEMORY. Each worker is a separate process that imports pandas (~71 MiB),
#    openpyxl, google-cloud-firestore (~30 MiB), python-docx and flask -- ~138
#    MiB resident per worker before serving anything, so 3 workers spent ~414
#    MiB of the service's 512 MiB limit on imports alone. Cloud Run OOM-killed
#    the container at 520 MiB mid-request on 2026-08-03 ("Memory limit of 512
#    MiB exceeded"), which n8n saw as a 503 on /process AFTER Stage 1 had
#    already run and billed Perplexity. One worker holds one copy.
#
# 2. CORRECTNESS. _pipeline_state / _pipeline_lock (and _update_state) are
#    module-level dicts, so with N workers there are N independent copies in N
#    processes. The background pipeline thread lives in whichever worker took
#    the POST, but a follow-up GET /process/status round-robins and usually
#    lands on a DIFFERENT worker -- which reports {"status": "idle"} even while
#    the run is in flight. That made the documented "if /process times out,
#    poll /process/status for the rest" recovery path unreliable, and the
#    "already running" 409 guard only guarded one worker. Threads share one
#    process, so both work as written.
#
# gunicorn switches to the gthread worker class automatically when threads > 1.
# Threads are the right shape here because every slow path is I/O-bound
# (Perplexity, Attio, Firestore, GCS) and releases the GIL while waiting.
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "1800", "--chdir", "pipeline", "--bind", "0.0.0.0:8080", "app:app"]
