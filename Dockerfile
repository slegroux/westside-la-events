# Web image: serves the site and nothing else.
#
# This used to be one image doing both jobs, which cost the web server a 906 MB
# pull on every cold start -- 452 MB of Chromium and ~200 MB of Google Cloud SDK
# that a request for a page never touches. Cold TTFB was ~32s.
#
# Splitting is safe because the web app never imports the scrapers: the only
# link was /api/run-scrapers shelling out to run_scrapers.py in a subprocess,
# and that endpoint now lives in the scraper service built from
# Dockerfile.scraper. Keep the two in step when changing shared dependencies.
FROM python:3.11-slim

WORKDIR /app

# curl is kept for container-level healthchecks; everything else the page
# renderer needs comes from pip.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better caching
COPY requirements.txt .

# The shared dependency set. The scraper image installs requirements-scraper.txt
# instead, which starts with "-r requirements.txt" and adds playwright, so the
# two cannot drift apart while the web image stays free of playwright's ~130MB
# bundled Node driver.
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (this changes most frequently, so it's last)
COPY . .

# /app/data is a GCSFuse mount of gs://westside-la-events-data at runtime, so
# this is only the mount point -- anything baked in here is shadowed by it.
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    TZ=America/Los_Angeles \
    # Reduce Python startup time
    PYTHONHASHSEED=0 \
    # The database is read live from the GCSFuse mount, so there is nothing to
    # download at startup. This image has no gsutil to do it with either.
    SKIP_DB_DOWNLOAD=true

EXPOSE 8080

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
