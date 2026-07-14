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
CMD ["gunicorn", "--workers", "3", "--timeout", "1800", "--chdir", "pipeline", "--bind", "0.0.0.0:8080", "app:app"]
