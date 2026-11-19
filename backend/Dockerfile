# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=180 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements.txt .

# The pip cache survives failed builds, so a retry resumes instead of re-downloading everything.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Playwright's bundled Node driver needs libatomic on arm64 (Apple Silicon) slim images.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libatomic1 \
 && rm -rf /var/lib/apt/lists/*

# Separate layer: a Chromium download failure doesn't redo the pip install.
RUN playwright install --with-deps chromium

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]